"""Call /whs_node/set_drivestop on the ROS executor thread."""

from __future__ import annotations

import asyncio
import queue
from typing import Optional

from nexus_server.ros_runtime import RosRuntime


class RosWhs:
    def __init__(self, runtime: RosRuntime) -> None:
        self._runtime = runtime
        self._client = None
        self._closed_loop = None
        self._clear_errors = None
        self._pending: queue.Queue = queue.Queue()

    def attach(self, node: object) -> None:
        from std_srvs.srv import SetBool

        from std_srvs.srv import Trigger

        self._client = node.create_client(SetBool, "/whs_node/set_drivestop")
        self._closed_loop = node.create_client(SetBool, "/core/drive_manager/set_closed_loop")
        self._clear_errors = node.create_client(Trigger, "/core/drive_manager/clear_errors")
        node.create_timer(0.05, self._drain)

    def _drain(self) -> None:
        while True:
            try:
                item = self._pending.get_nowait()
            except queue.Empty:
                return
            kind = item[0]
            if kind == "bool":
                _, client, value, loop, future = item
                self._begin_bool(client, value, loop, future)
            else:
                _, client, loop, future = item
                self._begin_trigger(client, loop, future)

    def _begin_bool(self, client: object, stop: bool, loop: asyncio.AbstractEventLoop, future: asyncio.Future) -> None:
        from std_srvs.srv import SetBool

        if client is None or not client.service_is_ready():
            loop.call_soon_threadsafe(future.set_result, (False, "ROS service is not available"))
            return
        request = SetBool.Request()
        request.data = stop
        ros_future = client.call_async(request)

        def done(completed) -> None:
            try:
                response = completed.result()
                result = (bool(response.success), str(response.message or ""))
            except Exception as exc:  # noqa: BLE001 - report the service failure
                result = (False, str(exc))
            loop.call_soon_threadsafe(lambda result=result: future.done() or future.set_result(result))

        ros_future.add_done_callback(done)

    def _begin_trigger(self, client: object, loop: asyncio.AbstractEventLoop, future: asyncio.Future) -> None:
        from std_srvs.srv import Trigger

        if client is None or not client.service_is_ready():
            loop.call_soon_threadsafe(future.set_result, (False, "ROS service is not available"))
            return
        ros_future = client.call_async(Trigger.Request())

        def done(completed) -> None:
            try:
                response = completed.result()
                result = (bool(response.success), str(response.message or ""))
            except Exception as exc:  # noqa: BLE001
                result = (False, str(exc))
            loop.call_soon_threadsafe(lambda result=result: future.done() or future.set_result(result))

        ros_future.add_done_callback(done)

    async def set_drivestop(self, stop: bool) -> tuple[bool, str]:
        return await self._call_bool("/whs_node/set_drivestop", stop, self._client)

    async def set_closed_loop(self, enable: bool) -> tuple[bool, str]:
        return await self._call_bool("/core/drive_manager/set_closed_loop", enable, self._closed_loop)

    async def clear_errors(self) -> tuple[bool, str]:
        if not self._runtime.status().initialized:
            return False, "ROS is not initialised"
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending.put(("trigger", self._clear_errors, loop, future))
        return await self._wait(future)

    async def _call_bool(self, topic: str, value: bool, client: object) -> tuple[bool, str]:
        del topic
        if not self._runtime.status().initialized:
            return False, "ROS is not initialised"
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending.put(("bool", client, bool(value), loop, future))
        return await self._wait(future)

    async def _wait(self, future: asyncio.Future) -> tuple[bool, str]:
        try:
            return await asyncio.wait_for(future, timeout=2.0)
        except asyncio.TimeoutError:
            return False, "ROS service response timed out"
