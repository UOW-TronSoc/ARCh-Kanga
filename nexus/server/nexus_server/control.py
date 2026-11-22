"""Per-socket control ownership. Telemetry stays on its own socket."""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Protocol

from nexus_server.drive_motion import MotionPublisher, finite_drive
from nexus_server.drivestop import DrivestopStore

TAKEN = "Control taken elsewhere"
UNCONFIRMED = "Stop could not be confirmed"
TRANSFER_BUSY = "Transfer already in progress"


class WhsClient(Protocol):
    async def set_drivestop(self, stop: bool) -> tuple[bool, str]:
        """Request a drivestop change. True means WHS accepted it."""


class ControlHub:
    def __init__(
        self,
        store: DrivestopStore,
        whs: WhsClient,
        confirm_timeout: float = 2.0,
        motion: Optional[MotionPublisher] = None,
    ) -> None:
        self._store = store
        self._whs = whs
        self._confirm_timeout = confirm_timeout
        self._motion = motion or MotionPublisher()
        self._motion.set_watchdog_handler(self._expire_from_ros)
        self._transfer_id = 0
        self._transfer_socket: Optional[object] = None
        self._lock = asyncio.Lock()
        self._holder: Optional[object] = None
        self._armed: Optional[object] = None
        self._arm_generation = 0
        self._clients: set[object] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def holder(self) -> Optional[object]:
        return self._holder

    async def connect(self, websocket: object) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        await self._send(websocket)

    def disconnect(self, websocket: object) -> None:
        self._clients.discard(websocket)
        if self._transfer_socket is websocket:
            self._transfer_socket = None
            self._transfer_id += 1
        if self._armed is websocket or self._holder is websocket:
            self._arm_generation += 1
            self._armed = None
            self._motion.zero_if_active()
        if self._holder is websocket:
            self._holder = None

    async def handle(self, websocket: object, message: dict) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        kind = message.get("type")
        if kind == "drive":
            await self._drive(websocket, message)
        elif kind == "assert":
            await self._assert_stop(websocket)
        elif kind == "release":
            await self._release(websocket)
        elif kind == "take":
            await self._take(websocket)
        elif kind == "arm":
            await self._arm(websocket)
        elif kind == "disarm":
            await self._disarm(websocket)
        elif kind == "mode":
            await self._set_mode(websocket, bool(message.get("enable")))
        elif kind == "clear_errors":
            await self._clear_errors(websocket)

    async def _take(self, websocket: object) -> None:
        async with self._lock:
            if self._holder is websocket:
                await self._send(websocket)
                return
            if self._transfer_socket is not None:
                await self._send(websocket, error=TRANSFER_BUSY)
                return
            previous = self._holder
            if previous is None:
                self._holder = websocket
                await self._send(websocket)
                return
            self._transfer_id += 1
            token = self._transfer_id
            self._transfer_socket = websocket
            self._arm_generation += 1
            self._armed = None
            self._motion.zero_if_active()
            self._holder = None
            await self._send(previous, notice=TAKEN)
            generation = self._store.read().drivestop_generation
        ok, detail = await self._whs.set_drivestop(True)
        confirmed = await self._wait_until_stopped(generation) if ok else False
        async with self._lock:
            if self._transfer_id != token:
                return
            self._transfer_socket = None
            if websocket not in self._clients:
                return
            if ok and confirmed:
                self._holder = websocket
                await self._send(websocket)
                return
            self._holder = None
            await self._send(websocket, error=detail or UNCONFIRMED)

    async def _release(self, websocket: object) -> None:
        async with self._lock:
            if self._holder is not websocket or self._store.read().drivestop is False:
                return
        ok, detail = await self._whs.set_drivestop(False)
        async with self._lock:
            if self._holder is not websocket:
                return
            if not ok:
                await self._send(websocket, error=detail or UNCONFIRMED)

    async def _assert_stop(self, websocket: object) -> None:
        async with self._lock:
            self._arm_generation += 1
            if self._armed is not None:
                self._armed = None
                self._motion.zero_if_active()
        ok, detail = await self._whs.set_drivestop(True)
        async with self._lock:
            if not ok:
                await self._send(websocket, error=detail or UNCONFIRMED)
            else:
                await self._send(websocket)

    async def _arm(self, websocket: object) -> None:
        async with self._lock:
            if self._holder is not websocket:
                await self._send(websocket, error="Only the holder can arm")
                return
            generation = self._arm_generation
            if not self._ready_to_arm():
                await self._send(websocket, error="Drivetrain is not ready to arm")
                return
            observed = self._store.read()
            need_mode = observed.closed_loop is not True
            started = observed.mode_generation
        if need_mode:
            ok, detail = await self._whs.set_closed_loop(True)
            confirmed = await self._wait_for_mode(True, started) if ok else False
            async with self._lock:
                if self._holder is not websocket or self._arm_generation != generation:
                    return
                if not ok or not confirmed or not self._ready_to_arm():
                    await self._send(websocket, error=detail or "Closed loop was not confirmed")
                    return
        async with self._lock:
            if self._holder is not websocket or self._arm_generation != generation or not self._ready_to_arm():
                return
            self._armed = websocket
            await self._send(websocket)

    async def _disarm(self, websocket: object) -> None:
        async with self._lock:
            if self._holder is not websocket and self._armed is not websocket:
                return
            self._arm_generation += 1
            if self._armed is websocket:
                self._armed = None
                self._motion.zero_if_active()
            await self._send(websocket)

    async def _set_mode(self, websocket: object, enable: bool) -> None:
        async with self._lock:
            if self._holder is not websocket:
                await self._send(websocket, error="Only the holder can change drivetrain mode")
                return
            if not enable:
                self._arm_generation += 1
                if self._armed is websocket:
                    self._armed = None
                    self._motion.zero_if_active()
        ok, detail = await self._whs.set_closed_loop(enable)
        async with self._lock:
            if self._holder is not websocket:
                return
            if not ok:
                await self._send(websocket, error=detail or "Closed loop was not confirmed")
                return
            await self._send(websocket)

    async def _clear_errors(self, websocket: object) -> None:
        async with self._lock:
            if self._holder is not websocket:
                await self._send(websocket, error="Only the holder can clear errors")
                return
        ok, detail = await self._whs.clear_errors()
        async with self._lock:
            if self._holder is not websocket:
                return
            if not ok:
                await self._send(websocket, error=detail or "Clear errors was not acknowledged")
                return
            await self._send(websocket, notice=detail or "Errors cleared")

    async def _drive(self, websocket: object, message: dict) -> None:
        if not finite_drive(message.get("x"), message.get("yaw"), message.get("scale")):
            return
        observed = self._store.read()
        allowed = (
            websocket is self._holder
            and websocket is self._armed
            and observed.whs_available
            and observed.drivestop is False
            and observed.mode_available
            and observed.closed_loop is True
        )
        if not allowed:
            return
        self._motion.command(float(message["x"]), float(message["yaw"]), float(message["scale"]))

    def _ready_to_arm(self) -> bool:
        observed = self._store.read()
        return (
            observed.whs_available
            and observed.drivestop is False
            and observed.mode_available
            and observed.closed_loop is not None
        )

    def _expire_from_ros(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self._expire()))

    async def _expire(self) -> None:
        async with self._lock:
            self._arm_generation += 1
            holder = self._armed or self._holder
            self._armed = None
            if holder is not None:
                await self._send(holder)

    async def _wait_until_stopped(self, generation: int) -> bool:
        deadline = time.monotonic() + self._confirm_timeout
        while time.monotonic() < deadline:
            observed = self._store.read()
            if (
                observed.whs_available
                and observed.drivestop is True
                and observed.drivestop_generation > generation
            ):
                return True
            await asyncio.sleep(0.02)
        return False

    async def _wait_for_mode(self, closed_loop: bool, generation: int) -> bool:
        deadline = time.monotonic() + self._confirm_timeout
        while time.monotonic() < deadline:
            observed = self._store.read()
            if (
                observed.mode_available
                and observed.closed_loop is closed_loop
                and observed.mode_generation > generation
            ):
                return True
            await asyncio.sleep(0.02)
        return False

    async def _send(self, websocket: object, notice: Optional[str] = None, error: Optional[str] = None) -> None:
        if websocket not in self._clients and websocket is not self._holder:
            return
        role = "holder" if websocket is self._holder else "observer"
        try:
            await websocket.send_json({
                "type": "state",
                "role": role,
                "armed": websocket is self._armed,
                "notice": notice,
                "error": error,
            })
        except Exception:
            self.disconnect(websocket)
