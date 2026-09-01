"""Unit tests for /rosout ring serialization (no rclpy)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from .rosout_buffer import (
    ROS_LOG_DEBUG,
    ROS_LOG_ERROR,
    ROS_LOG_FATAL,
    ROS_LOG_INFO,
    ROS_LOG_WARN,
    RosoutBuffer,
    http_level_value,
    record_from_ros_log,
    ros_level_name,
)


class RosoutBufferTests(unittest.TestCase):
    def test_level_names_match_rcl_constants(self) -> None:
        self.assertEqual(ros_level_name(ROS_LOG_DEBUG), "DEBUG")
        self.assertEqual(ros_level_name(ROS_LOG_INFO), "INFO")
        self.assertEqual(ros_level_name(ROS_LOG_WARN), "WARN")
        self.assertEqual(ros_level_name(ROS_LOG_ERROR), "ERROR")
        self.assertEqual(ros_level_name(ROS_LOG_FATAL), "FATAL")
        self.assertEqual(ros_level_name(25), "INFO")
        self.assertEqual(ros_level_name(35), "WARN")
        self.assertEqual(http_level_value("WARNING"), ROS_LOG_WARN)
        self.assertEqual(http_level_value("CRITICAL"), ROS_LOG_FATAL)

    def test_fake_log_serializes_level_name_and_message(self) -> None:
        msg = SimpleNamespace(
            stamp=SimpleNamespace(sec=1_700_000_000, nanosec=500_000_000),
            level=ROS_LOG_ERROR,
            name="/wheel_bl/can_node",
            msg="Failed to initialize socket can interface: can_core",
        )
        record = record_from_ros_log(1, msg)
        self.assertEqual(record["seq"], 1)
        self.assertEqual(record["level"], ROS_LOG_ERROR)
        self.assertEqual(record["level_name"], "ERROR")
        self.assertEqual(record["name"], "/wheel_bl/can_node")
        self.assertIn("can_core", record["msg"])
        self.assertTrue(record["stamp"].startswith("2023-"))

    def test_ring_drops_oldest_and_snapshots_in_order(self) -> None:
        buffer = RosoutBuffer(max_records=2)
        buffer.append_fields(level=ROS_LOG_INFO, name="/a", msg="one")
        buffer.append_fields(level=ROS_LOG_WARN, name="/b", msg="two")
        buffer.append_fields(level=ROS_LOG_ERROR, name="/c", msg="three")
        snap = buffer.snapshot()
        self.assertEqual([item["msg"] for item in snap], ["two", "three"])
        self.assertEqual([item["seq"] for item in snap], [2, 3])


if __name__ == "__main__":
    unittest.main()
