"""Snapshot stream for /ws/telemetry."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from nexus_server.drivestop import DrivestopStore

SCHEMA_VERSION = 1


class TelemetryMessage(BaseModel):
    schemaVersion: int
    sequence: int
    serverTimestamp: str
    rosAvailable: bool
    whsAvailable: bool
    drivestop: Optional[bool]


class TelemetryHub:
    def __init__(self, store: DrivestopStore, hz: float = 5.0) -> None:
        if hz <= 0:
            raise ValueError("telemetry rate must be positive")
        self._store = store
        self._interval = 1.0 / hz
        self._sequence = 0
        self._clients: set[object] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def snapshot(self) -> TelemetryMessage:
        observation = self._store.read()
        self._sequence += 1
        return TelemetryMessage(
            schemaVersion=SCHEMA_VERSION,
            sequence=self._sequence,
            serverTimestamp=datetime.now(timezone.utc).isoformat(),
            rosAvailable=observation.ros_available,
            whsAvailable=observation.whs_available,
            drivestop=observation.drivestop,
        )

    async def connect(self, websocket: object) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        await websocket.send_json(self.snapshot().model_dump())

    def disconnect(self, websocket: object) -> None:
        self._clients.discard(websocket)

    async def broadcast(self) -> None:
        if not self._clients:
            return
        payload = self.snapshot().model_dump()
        for websocket in list(self._clients):
            try:
                await websocket.send_json(payload)
            except Exception:
                self._clients.discard(websocket)

    async def run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                await self.broadcast()
        except asyncio.CancelledError:
            return
