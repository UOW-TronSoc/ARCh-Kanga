from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus_server.app import create_app
from nexus_server.health import build_health
from nexus_server.ros_runtime import RosRuntime, RosStatus, StaticRosRuntime


def test_health_splits_the_web_server_from_ros():
    down = build_health(RosStatus(False, "ImportError: rclpy"))
    assert down.backend == "available"
    assert down.status == "degraded"
    assert down.ros.initialized is False

    up = build_health(RosStatus(True))
    assert up.status == "ok"
    assert up.ros.initialized is True
    assert up.backend == "available"


def test_health_endpoint_answers_when_ros_did_not_start():
    app = create_app(runtime=StaticRosRuntime(False, "rclpy unavailable"))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "available"
    assert body["status"] == "degraded"
    assert body["ros"]["initialized"] is False


def test_frontend_routes_do_not_hide_health(tmp_path: Path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>nexus</title>")
    app = create_app(runtime=StaticRosRuntime(True), static_dir=static_dir)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert "html" not in health.headers["content-type"]

        page = client.get("/rover")
        assert page.status_code == 200
        assert "nexus" in page.text

        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/ws/missing") as websocket:
                websocket.receive_text()
        assert closed.value.code == 1008


def test_ros_runtime_records_initialisation_failure(monkeypatch):
    runtime = RosRuntime()

    def fail() -> None:
        raise ImportError("no module named rclpy")

    monkeypatch.setattr(runtime, "_start_rclpy", fail)
    runtime.start()
    status = runtime.status()
    assert status.initialized is False
    assert status.error is not None
    assert "ImportError" in status.error
    runtime.stop()
