import asyncio

from nexus_server.control import TRANSFER_BUSY, ControlHub
from nexus_server.drive_motion import MotionPublisher
from nexus_server.drive_motion import speed_factor
from nexus_server.drivestop import DrivestopStore
from test_stage3 import FakeSocket, FakeWhs


def _ready(stopped: bool = False, closed_loop: bool | None = False):
    store = DrivestopStore()
    store.set_ros_available(True)
    store.observe(stopped, publisher_count=1)
    if closed_loop is None:
        store.set_mode_publisher_count(0)
    else:
        store.observe_mode(closed_loop, publisher_count=1)
    frames: list[tuple[float, float]] = []
    motion = MotionPublisher()
    motion.set_sink(lambda linear, yaw: frames.append((linear, yaw)))
    hub = ControlHub(store, FakeWhs(store), confirm_timeout=0.05, motion=motion)
    hub.command_log = frames  # type: ignore[attr-defined]
    return hub, store


def test_speed_curve_reaches_full_at_ninety_percent():
    assert speed_factor(0) == 0
    assert speed_factor(45) == 0.5
    assert speed_factor(90) == 1
    assert speed_factor(100) == 1


def test_arm_from_idle_waits_for_observed_closed_loop_and_publishes_no_motion():
    async def scenario() -> None:
        hub, store = _ready(stopped=False, closed_loop=False)
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "arm"})
        assert hub._armed is holder
        assert store.read().closed_loop is True
        assert hub.command_log == []

    asyncio.run(scenario())


def test_observer_cannot_arm_or_change_mode():
    async def scenario() -> None:
        hub, store = _ready(stopped=False, closed_loop=False)
        observer = FakeSocket()
        await hub.connect(observer)
        await hub.handle(observer, {"type": "arm"})
        await hub.handle(observer, {"type": "mode", "enable": True})
        assert hub._armed is None
        assert store.read().closed_loop is False
        assert hub.command_log == []

    asyncio.run(scenario())


def test_unknown_mode_blocks_arming():
    async def scenario() -> None:
        hub, _store = _ready(stopped=False, closed_loop=None)
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "arm"})
        assert hub._armed is None
        assert holder.messages[-1]["error"] == "Drivetrain is not ready to arm"

    asyncio.run(scenario())


def test_release_alone_does_not_arm():
    async def scenario() -> None:
        hub, _store = _ready(stopped=True, closed_loop=False)
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "release"})
        assert hub._armed is None

    asyncio.run(scenario())


def test_cached_stop_without_a_fresh_whs_sample_does_not_hand_off_control():
    async def scenario() -> None:
        hub, store = _ready(stopped=True, closed_loop=False)
        hub._whs.fail = True
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        await hub.handle(second, {"type": "take"})
        assert hub.holder is None
        assert store.read().drivestop is True

    asyncio.run(scenario())


def test_delayed_mode_response_cannot_arm_a_former_holder():
    async def scenario() -> None:
        hub, store = _ready(stopped=False, closed_loop=False)
        started = asyncio.Event()

        async def slow(enable: bool):
            started.set()
            await asyncio.sleep(0.05)
            store.observe_mode(enable, publisher_count=1)
            return True, "ok"

        hub._whs.set_closed_loop = slow
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        arming = asyncio.create_task(hub.handle(first, {"type": "arm"}))
        await started.wait()
        await hub.handle(first, {"type": "disarm"})
        await arming
        assert hub._armed is None
        assert hub.command_log == []

    asyncio.run(scenario())


def test_one_transfer_is_confirmed_for_the_requester_that_stays_connected():
    async def scenario() -> None:
        hub, store = _ready(stopped=False, closed_loop=True)
        started = asyncio.Event()
        release = asyncio.Event()

        calls = 0

        async def slow(stop: bool):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await release.wait()
            store.observe(stop, publisher_count=1)
            return True, "ok"

        hub._whs.set_drivestop = slow
        first, second, third = FakeSocket(), FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.connect(third)
        await hub.handle(first, {"type": "take"})
        transfer = asyncio.create_task(hub.handle(second, {"type": "take"}))
        await started.wait()
        assert hub.holder is None
        assert first.messages[-1]["notice"] == "Control taken elsewhere"
        await hub.handle(third, {"type": "take"})
        assert third.messages[-1]["error"] == TRANSFER_BUSY
        await hub.handle(third, {"type": "assert"})
        release.set()
        await transfer
        assert hub.holder is second
        assert second.messages[-1]["role"] == "holder"
        assert hub._armed is None

    asyncio.run(scenario())


def test_requester_disconnect_and_whs_failure_leave_control_unowned():
    async def disconnects() -> None:
        hub, _store = _ready(stopped=False, closed_loop=True)
        started = asyncio.Event()

        async def slow(stop: bool):
            del stop
            started.set()
            await asyncio.sleep(0.05)
            return True, "ok"

        hub._whs.set_drivestop = slow
        holder, requester = FakeSocket(), FakeSocket()
        await hub.connect(holder)
        await hub.connect(requester)
        await hub.handle(holder, {"type": "take"})
        transfer = asyncio.create_task(hub.handle(requester, {"type": "take"}))
        await started.wait()
        hub.disconnect(requester)
        await transfer
        assert hub.holder is None
        assert hub._transfer_socket is None

    async def fails() -> None:
        hub, _store = _ready(stopped=False, closed_loop=True)
        hub._whs.fail = True
        holder, requester, later = FakeSocket(), FakeSocket(), FakeSocket()
        await hub.connect(holder)
        await hub.connect(requester)
        await hub.connect(later)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(requester, {"type": "take"})
        assert hub.holder is None
        assert requester.messages[-1]["error"] == "Stop could not be confirmed"
        await hub.handle(later, {"type": "take"})
        assert hub.holder is later

    asyncio.run(disconnects())
    asyncio.run(fails())


def test_takeover_while_arming_cancels_the_arm_and_does_not_drive():
    async def scenario() -> None:
        hub, _store = _ready(stopped=False, closed_loop=True)
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        await hub.handle(first, {"type": "arm"})
        assert hub._armed is first
        await hub.handle(second, {"type": "take"})
        assert hub.holder is second
        assert hub._armed is None
        assert hub.command_log == []

    asyncio.run(scenario())
