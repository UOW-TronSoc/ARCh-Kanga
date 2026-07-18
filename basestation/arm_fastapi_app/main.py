"""Stub arm FastAPI on port 8001."""

from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI(title="basestation-arm-fastapi-stub", version="0.0.0")


@app.get("/health")
def health() -> dict:
    error = None
    rclpy_importable = False
    try:
        import rclpy  # noqa: F401

        rclpy_importable = True
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    return {
        "status": "ok" if error is None else "degraded",
        "service": "basestation-arm-fastapi",
        "role": "stub",
        "rclpy_importable": rclpy_importable,
        "error": error,
        "workspace_sourced": os.path.isdir("/workspace/install"),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "0"),
    }
