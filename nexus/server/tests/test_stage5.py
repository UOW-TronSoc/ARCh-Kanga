import asyncio

from nexus_server.control import ControlHub
from nexus_server.drive_motion import MAX_LINEAR_MPS, MotionPublisher
from nexus_server.drivestop import DrivestopStore
from test_stage3 import FakeSocket, FakeWhs


def _driving_hub():
    store = DrivestopStore()
    store.set_ros_available(True)
    store.observe(False, publisher_count=1)
    store.observe_mode(True, publisher_count=1)
    frames: list[tuple[float, float]] = []
    motion = MotionPublisher()
    motion.set_sink(lambda linear, yaw: frames.append((linear, yaw)))
    motion.command_log = frames  # type: ignore[attr-defined]
    hub = ControlHub(store, FakeWhs(store), motion=motion)
    return hub, motion


def test_motion_scales_once_and_rejects_invalid_frames_without_a_watchdog_refresh():
    async def scenario() -> None:
        hub, motion = _driving_hub()
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "arm"})
        await hub.handle(holder, {"type": "drive", "x": 1, "yaw": 0, "scale": 90})
        await hub.handle(holder, {"type": "drive", "x": float("nan"), "yaw": 0, "scale": 90})
        motion.tick()
        assert motion.command_log == [(MAX_LINEAR_MPS, 0.0)]
        await hub.handle(holder, {"type": "drive", "x": 1, "yaw": 0, "scale": 100})
        motion.tick()
        assert motion.command_log[-1] == (MAX_LINEAR_MPS, 0.0)

    asyncio.run(scenario())


def test_takeover_while_moving_publishes_zero_before_the_stop_request():
    async def scenario() -> None:
        hub, motion = _driving_hub()
        calls = []
        original = hub._whs.set_drivestop

        async def wrapped(stop: bool):
            calls.append(("service", list(motion.command_log)))
            return await original(stop)

        hub._whs.set_drivestop = wrapped
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        await hub.handle(first, {"type": "arm"})
        await hub.handle(first, {"type": "drive", "x": 1, "yaw": 0, "scale": 45})
        motion.tick()
        await hub.handle(second, {"type": "take"})
        assert calls[0][1][-1] == (0.0, 0.0)
        assert hub._armed is None
        assert hub.holder is second

    asyncio.run(scenario())


def test_inflight_tick_cannot_publish_a_command_after_stop():
    import threading
    import time

    recorded: list[tuple[float, float]] = []
    entered = threading.Event()
    release = threading.Event()

    def sink(linear: float, yaw: float) -> None:
        recorded.append((linear, yaw))
        if linear != 0.0 and not entered.is_set():
            entered.set()
            release.wait(2)

    motion = MotionPublisher()
    motion.set_sink(sink)
    motion.command(1, 0, 90)
    worker = threading.Thread(target=motion.tick)
    worker.start()
    assert entered.wait(2)
    stopper = threading.Thread(target=motion.zero_if_active)
    stopper.start()
    time.sleep(0.05)
    assert stopper.is_alive()
    release.set()
    worker.join(2)
    stopper.join(2)
    assert recorded[-1] == (0.0, 0.0)
    first_zero = recorded.index((0.0, 0.0))
    assert recorded[first_zero:] == [(0.0, 0.0)]
    before = len(recorded)
    motion.tick()
    assert len(recorded) == before


def test_watchdog_publishes_zero_and_requires_rearm():
    async def scenario() -> None:
        hub, motion = _driving_hub()
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "arm"})
        await hub.handle(holder, {"type": "drive", "x": 1, "yaw": 0, "scale": 90})
        motion.tick()
        motion._stamp = motion._stamp - 1
        motion.tick()
        await asyncio.sleep(0.02)
        assert motion.command_log[-1] == (0.0, 0.0)
        assert hub._armed is None
        await hub.handle(holder, {"type": "drive", "x": 1, "yaw": 0, "scale": 90})
        before = len(motion.command_log)
        motion.tick()
        assert len(motion.command_log) == before

    asyncio.run(scenario())
