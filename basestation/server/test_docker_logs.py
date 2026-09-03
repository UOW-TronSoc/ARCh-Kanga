"""Unit tests for docker PID-1 log parse and rings (no Docker daemon)."""

from __future__ import annotations

import time
import unittest

from .docker_logs import (
    DockerLogStore,
    parse_docker_log_line,
    resolve_onboard_name,
)
from .rosout_buffer import ROS_LOG_ERROR, ROS_LOG_INFO, ROS_LOG_WARN


class ParseDockerLogLineTests(unittest.TestCase):
    def test_timestamped_rcl_error_kept(self) -> None:
        line = (
            "2026-09-03T01:02:03.123456789Z "
            "[ERROR] [1750000000.1] [core.wheel_fl.can_node]: "
            "Failed to initialize socket can interface: can_core"
        )
        parsed = parse_docker_log_line(line, "kanga-onboard")
        self.assertTrue(parsed["stamp"].startswith("2026-09-03T01:02:03"))
        self.assertEqual(parsed["level"], ROS_LOG_ERROR)
        self.assertEqual(parsed["level_name"], "ERROR")
        self.assertEqual(parsed["name"], "core.wheel_fl.can_node")
        self.assertIn("can_core", parsed["msg"])

    def test_rcl_info_is_kept(self) -> None:
        line = (
            "2026-09-03T01:02:03.0Z "
            "[INFO] [1750000000.1] [launch]: process started"
        )
        parsed = parse_docker_log_line(line, "kanga-onboard")
        self.assertEqual(parsed["level"], ROS_LOG_INFO)
        self.assertEqual(parsed["level_name"], "INFO")
        self.assertIn("process started", parsed["msg"])

    def test_process_has_died_is_info_without_rcl_tag(self) -> None:
        line = (
            "2026-09-03T01:02:03.0Z "
            "[custom_odrive_node-6] process has died [pid 12, exit code 255]"
        )
        parsed = parse_docker_log_line(line, "kanga-onboard")
        self.assertEqual(parsed["level"], ROS_LOG_INFO)
        self.assertEqual(parsed["name"], "kanga-onboard")
        self.assertIn("process has died", parsed["msg"])

    def test_warning_maps_to_warn(self) -> None:
        parsed = parse_docker_log_line(
            "2026-09-03T01:02:03Z [WARNING] [1.0] [n]: hot",
            "kanga-dev",
        )
        self.assertEqual(parsed["level"], ROS_LOG_WARN)
        self.assertEqual(parsed["level_name"], "WARN")


class ResolveOnboardTests(unittest.TestCase):
    def test_prefers_kanga_onboard_when_both_exist(self) -> None:
        present = {"kanga-dev", "kanga-onboard"}
        self.assertEqual(
            resolve_onboard_name(lambda name: name in present),
            "kanga-onboard",
        )

    def test_falls_back_to_kanga_dev(self) -> None:
        self.assertEqual(
            resolve_onboard_name(lambda name: name == "kanga-dev"),
            "kanga-dev",
        )


class DockerLogStoreTests(unittest.TestCase):
    def test_missing_container_does_not_raise(self) -> None:
        class FakeContainers:
            def get(self, name: str):
                raise RuntimeError(f"404 Client Error for {name}: Not Found")

        class FakeClient:
            containers = FakeContainers()

        store = DockerLogStore(
            client_factory=lambda: FakeClient(),
            retry_seconds=0.05,
        )
        store.start()
        try:
            deadline = time.time() + 1.0
            status = ""
            while time.time() < deadline:
                status = store.snapshot("onboard")["status"]
                if "missing" in status or "follow failed" in status:
                    break
                time.sleep(0.02)
            self.assertTrue(
                "missing" in status or "follow failed" in status,
                msg=status,
            )
            self.assertEqual(store.snapshot("onboard")["records"], [])
        finally:
            store.stop()

    def test_clear_one_leaf_leaves_the_other(self) -> None:
        store = DockerLogStore(client_factory=lambda: (_ for _ in ()).throw(RuntimeError("no docker")))
        store.append_line(
            "basestation",
            "2026-09-03T01:02:03Z uvicorn started",
            "basestation-server",
        )
        store.append_line(
            "onboard",
            "2026-09-03T01:02:03Z [ERROR] [1.0] [n]: fault",
            "kanga-onboard",
        )
        store.clear("onboard")
        self.assertEqual(store.snapshot("onboard")["records"], [])
        self.assertEqual(len(store.snapshot("basestation")["records"]), 1)


if __name__ == "__main__":
    unittest.main()
