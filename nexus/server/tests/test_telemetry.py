import asyncio

from fastapi.testclient import TestClient

from nexus_server.app import create_app
from nexus_server.drivestop import DrivestopStore
from nexus_server.drivestop_ros import (
    DRIVESTOP_DEPTH,
    DRIVESTOP_DURABILITY,
    DRIVESTOP_HISTORY,
    DRIVESTOP_RELIABILITY,
    DRIVESTOP_TOPIC,
)
from nexus_server.ros_runtime import StaticRosRuntime
from nexus_server.telemetry import TelemetryHub


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


def test_subscription_uses_the_whs_latch_qos():
    assert DRIVESTOP_TOPIC == "/drivestop"
    assert (DRIVESTOP_HISTORY, DRIVESTOP_DEPTH, DRIVESTOP_RELIABILITY, DRIVESTOP_DURABILITY) == (
        "keep_last",
        1,
        "reliable",
        "transient_local",
    )


def test_publisher_loss_does_not_clear_the_latched_value():
    store = DrivestopStore()
    store.observe(True, 1)
    store.set_publisher_count(0)
    observation = store.read()
    assert observation.drivestop is True
    assert observation.whs_available is False


def test_one_observation_is_sent_to_every_browser():
    async def scenario() -> None:
        store = DrivestopStore()
        store.set_ros_available(True)
        hub = TelemetryHub(store, hz=5)
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        assert first.messages[0]["drivestop"] is None
        assert first.messages[0]["schemaVersion"] == 1
        store.observe(False, 1)
        await hub.connect(second)
        await hub.broadcast()
        assert first.messages[-1] == second.messages[-1]
        assert first.messages[-1]["drivestop"] is False
        assert first.messages[-1]["whsAvailable"] is True
        hub.disconnect(second)
        store.observe(True, 1)
        await hub.broadcast()
        assert first.messages[-1]["drivestop"] is True
        assert second.messages[-1]["drivestop"] is False
        assert hub.client_count == 1

    asyncio.run(scenario())


def test_wheel_samples_go_stale_without_stopping_the_rest_of_telemetry():
    store = DrivestopStore()
    store.set_ros_available(True)
    store.observe(False, 1)
    hub = TelemetryHub(store, hz=5)
    assert hub.snapshot().wheelsFreshness == "unavailable"
    assert hub.snapshot().wheels == []
    store.observe_wheels([("wheel_fl_joint", 1.5)])
    fresh = hub.snapshot()
    assert fresh.wheelsFreshness == "fresh"
    assert fresh.wheels[0].velocity == 1.5
    assert fresh.drivestop is False
    store.age_wheels(1.1)
    stale = hub.snapshot()
    assert stale.wheelsFreshness == "stale"
    assert stale.wheels[0].velocity == 1.5
    assert stale.whsAvailable is True
    store.observe_wheels([("wheel_fl_joint", 0.2)])
    assert hub.snapshot().wheelsFreshness == "fresh"


def test_websocket_sends_the_current_sample_immediately():
    store = DrivestopStore()
    store.set_ros_available(True)
    store.observe(True, 1)
    app = create_app(runtime=StaticRosRuntime(True), drivestop=store, telemetry_hz=50)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry") as websocket:
            message = websocket.receive_json()
    assert message["drivestop"] is True
    assert message["whsAvailable"] is True
    assert message["rosAvailable"] is True
    assert message["sequence"] >= 1
