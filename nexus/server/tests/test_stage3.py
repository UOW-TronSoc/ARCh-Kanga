import asyncio

from fastapi.testclient import TestClient

from nexus_server.app import create_app
from nexus_server.control import TAKEN, UNCONFIRMED, ControlHub
from nexus_server.drivestop import DrivestopStore
from nexus_server.ros_runtime import StaticRosRuntime
from nexus_server.session import COOKIE_NAME, session_cookie_ok


class FakeSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


class FakeWhs:
    def __init__(self, store: DrivestopStore) -> None:
        self.store = store
        self.calls: list[bool] = []
        self.fail = False

    async def set_drivestop(self, stop: bool) -> tuple[bool, str]:
        self.calls.append(stop)
        if self.fail:
            return False, UNCONFIRMED
        self.store.set_ros_available(True)
        self.store.observe(stop, publisher_count=1)
        return True, "ok"

    async def set_closed_loop(self, enable: bool) -> tuple[bool, str]:
        self.store.observe_mode(enable, publisher_count=1)
        return True, "ok"

    async def clear_errors(self) -> tuple[bool, str]:
        return True, "simulation has no persistent drive errors"


def _hub(stopped: bool = True):
    store = DrivestopStore()
    store.set_ros_available(True)
    store.observe(stopped, publisher_count=1)
    whs = FakeWhs(store)
    return ControlHub(store, whs), store, whs


def test_unclaimed_take_preserves_drivestop_and_starts_disarmed_of_release():
    async def scenario() -> None:
        hub, store, whs = _hub(stopped=False)
        tab = FakeSocket()
        await hub.connect(tab)
        assert tab.messages[-1]["role"] == "observer"
        await hub.handle(tab, {"type": "take"})
        assert hub.holder is tab
        assert store.read().drivestop is False
        assert whs.calls == []
        await hub.handle(tab, {"type": "assert"})
        await hub.handle(tab, {"type": "release"})
        assert whs.calls == [True, False]

    asyncio.run(scenario())


def test_observer_can_assert_and_only_the_holder_can_release():
    async def scenario() -> None:
        hub, store, whs = _hub(stopped=False)
        holder, observer = FakeSocket(), FakeSocket()
        await hub.connect(holder)
        await hub.connect(observer)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(observer, {"type": "release"})
        assert whs.calls == []
        await hub.handle(observer, {"type": "assert"})
        assert store.read().drivestop is True
        assert whs.calls == [True]
        await hub.handle(observer, {"type": "release"})
        assert whs.calls == [True]
        await hub.handle(holder, {"type": "release"})
        assert whs.calls == [True, False]

    asyncio.run(scenario())


def test_duplicate_release_clicks_send_one_request():
    async def scenario() -> None:
        hub, _store, whs = _hub(stopped=True)
        holder = FakeSocket()
        await hub.connect(holder)
        await hub.handle(holder, {"type": "take"})
        await hub.handle(holder, {"type": "release"})
        await hub.handle(holder, {"type": "release"})
        assert whs.calls == [False]

    asyncio.run(scenario())


def test_stale_release_during_takeover_cannot_clear_the_stop():
    async def scenario() -> None:
        hub, store, whs = _hub(stopped=False)
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        await hub.handle(second, {"type": "take"})
        assert store.read().drivestop is True
        assert hub.holder is second
        assert first.messages[-1]["notice"] == TAKEN
        assert first.messages[-1]["role"] == "observer"
        await hub.handle(first, {"type": "release"})
        assert store.read().drivestop is True
        assert False not in whs.calls

    asyncio.run(scenario())


def test_failed_takeover_leaves_control_unclaimed():
    async def scenario() -> None:
        hub, store, whs = _hub(stopped=False)
        whs.fail = True
        first, second = FakeSocket(), FakeSocket()
        await hub.connect(first)
        await hub.connect(second)
        await hub.handle(first, {"type": "take"})
        await hub.handle(second, {"type": "take"})
        assert hub.holder is None
        assert second.messages[-1]["error"] == UNCONFIRMED
        assert second.messages[-1]["role"] == "observer"
        assert store.read().drivestop is False

    asyncio.run(scenario())


def test_disconnect_returns_the_tab_to_observer_on_reconnect():
    async def scenario() -> None:
        hub, _store, _whs = _hub(stopped=True)
        tab = FakeSocket()
        await hub.connect(tab)
        await hub.handle(tab, {"type": "take"})
        hub.disconnect(tab)
        assert hub.holder is None
        again = FakeSocket()
        await hub.connect(again)
        assert again.messages[-1]["role"] == "observer"

    asyncio.run(scenario())


def test_pin_cookie_is_a_browser_session_and_gates_sockets(tmp_path):
    secret = "test-secret"
    app = create_app(
        runtime=StaticRosRuntime(True),
        require_pin=True,
        session_secret=secret,
        pin_verifier=lambda pin: (pin == "123456", None if pin == "123456" else "Incorrect PIN"),
        whs=FakeWhs(DrivestopStore()),
    )
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        rejected = client.post("/api/session", json={"pin": "000000"})
        assert rejected.status_code == 401
        assert rejected.json()["detail"] == "Incorrect PIN"

        with client.websocket_connect("/ws/telemetry") as websocket:
            closed = websocket.receive()
        assert closed["type"] == "websocket.close"
        assert closed["code"] == 1008

        opened = client.post("/api/session", json={"pin": "123456"})
        assert opened.status_code == 200
        cookie = opened.cookies.get(COOKIE_NAME) or client.cookies.get(COOKIE_NAME)
        assert cookie
        assert session_cookie_ok(cookie, secret)
        assert "max-age" not in opened.headers.get("set-cookie", "").lower()
        assert client.get("/api/session").json()["authenticated"] is True

        with client.websocket_connect("/ws/control") as websocket:
            state = websocket.receive_json()
        assert state["role"] == "observer"
