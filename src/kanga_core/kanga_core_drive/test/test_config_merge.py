#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from config_merge import (  # noqa: E402
    WHEEL_IDS,
    merge_motor_configs,
    motor_config_path,
)


class TestConfigMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motors = Path(__file__).resolve().parents[1] / "config" / "motors"

    def test_wheel_ids(self):
        self.assertEqual(WHEEL_IDS, ("fl", "bl", "br", "fr"))

    def test_merge_contains_shared_bus_config_and_wheel_identity(self):
        shared = self.motors / "shared_motor_config.py"
        wheel = motor_config_path(self.motors, "fl")
        text = merge_motor_configs(shared, wheel)
        self.assertIn("watchdog_timeout = 5", text)
        self.assertIn('SERIAL_NUMBER = "394D353B3231"', text)
        self.assertIn("node_id = 1", text)
        self.assertIn("baud_rate = 250000", text)
        self.assertIn("heartbeat_msg_rate_ms = 20", text)
        self.assertIn("encoder_msg_rate_ms = 10", text)
        self.assertIn("iq_msg_rate_ms = 100", text)
        self.assertIn("torques_msg_rate_ms = 100", text)
        self.assertIn("spinout_mechanical_power_bandwidth = 20", text)
        self.assertIn("spinout_electrical_power_bandwidth = 20", text)
        self.assertIn("spinout_mechanical_power_threshold = -10", text)
        self.assertIn("spinout_electrical_power_threshold = 10", text)
        # Shared block before per-wheel overlay assignment
        self.assertLess(
            text.find("baud_rate = 250000"),
            text.find('SERIAL_NUMBER = "394D353B3231"'),
        )

    def test_all_wheels_have_serial(self):
        shared = self.motors / "shared_motor_config.py"
        for wid in WHEEL_IDS:
            merged = merge_motor_configs(shared, motor_config_path(self.motors, wid))
            self.assertIn("SERIAL_NUMBER", merged)
            self.assertIn("node_id", merged)


if __name__ == "__main__":
    unittest.main()
