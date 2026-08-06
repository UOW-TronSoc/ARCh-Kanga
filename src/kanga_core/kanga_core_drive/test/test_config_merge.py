#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
DESCRIPTION = Path(__file__).resolve().parents[2] / "kanga_core_description"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(DESCRIPTION))

from config_merge import (  # noqa: E402
    WHEEL_IDS,
    merge_motor_configs,
    motor_config_path,
)
from kanga_core_description.drivetrain_profile import (  # noqa: E402
    load_drivetrain_profile,
)


class TestConfigMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motors = Path(__file__).resolve().parents[1] / "config" / "motors"
        profile_path = (
            DESCRIPTION / "config" / "drivetrains" / "drivetrain_2025.yaml"
        )
        cls.profile = load_drivetrain_profile(profile_path)

    def test_wheel_ids(self):
        self.assertEqual(WHEEL_IDS, ("fl", "bl", "br", "fr"))

    def test_merge_contains_shared_bus_config_and_wheel_identity(self):
        shared = self.motors / "shared_motor_config.py"
        wheel = motor_config_path(self.motors, "fl")
        text = merge_motor_configs(
            shared,
            wheel,
            self.profile.parameters["motor_velocity_limit_tps"],
            self.profile.parameters["motor_acceleration_limit_tps_s"],
        )
        self.assertIn("MOTOR_VELOCITY_LIMIT_TPS = 22.0", text)
        self.assertIn("MOTOR_ACCELERATION_LIMIT_TPS_S = 80.0", text)
        self.assertIn("vel_limit = MOTOR_VELOCITY_LIMIT_TPS", text)
        self.assertIn(
            "vel_ramp_rate = MOTOR_ACCELERATION_LIMIT_TPS_S", text
        )
        self.assertIn('SERIAL_NUMBER = "394D353B3231"', text)
        self.assertIn("node_id = 1", text)
        self.assertIn("baud_rate = 250000", text)
        self.assertIn("heartbeat_msg_rate_ms = 20", text)
        self.assertIn("encoder_msg_rate_ms = 10", text)
        self.assertIn("iq_msg_rate_ms = 100", text)
        self.assertIn("torques_msg_rate_ms = 100", text)
        self.assertIn("spinout_mechanical_power_bandwidth = 20", text)
        self.assertIn("spinout_electrical_power_bandwidth = 20", text)
        self.assertIn("spinout_mechanical_power_threshold = -30", text)
        self.assertIn("spinout_electrical_power_threshold = 30", text)
        # Shared block before per-wheel overlay assignment
        self.assertLess(
            text.find("baud_rate = 250000"),
            text.find('SERIAL_NUMBER = "394D353B3231"'),
        )

    def test_all_wheels_have_serial(self):
        shared = self.motors / "shared_motor_config.py"
        for wheel_id in WHEEL_IDS:
            merged = merge_motor_configs(
                shared,
                motor_config_path(self.motors, wheel_id),
                self.profile.parameters["motor_velocity_limit_tps"],
                self.profile.parameters["motor_acceleration_limit_tps_s"],
            )
            self.assertIn("SERIAL_NUMBER", merged)
            self.assertIn("node_id", merged)

    def test_motor_velocity_limit_has_one_profile_source(self):
        shared_text = (self.motors / "shared_motor_config.py").read_text(
            encoding="utf-8"
        )
        wheel = motor_config_path(self.motors, "fl")
        merged = merge_motor_configs(
            self.motors / "shared_motor_config.py",
            wheel,
            self.profile.parameters["motor_velocity_limit_tps"],
            self.profile.parameters["motor_acceleration_limit_tps_s"],
        )
        self.assertNotIn("MOTOR_VELOCITY_LIMIT_TPS = 22", shared_text)
        self.assertIn("MOTOR_VELOCITY_LIMIT_TPS = 22.0", merged)

    def test_motor_acceleration_limit_has_one_profile_source(self):
        shared_text = (self.motors / "shared_motor_config.py").read_text(
            encoding="utf-8"
        )
        merged = merge_motor_configs(
            self.motors / "shared_motor_config.py",
            motor_config_path(self.motors, "fl"),
            self.profile.parameters["motor_velocity_limit_tps"],
            self.profile.parameters["motor_acceleration_limit_tps_s"],
        )
        self.assertNotIn("MOTOR_ACCELERATION_LIMIT_TPS_S = 80", shared_text)
        self.assertIn("MOTOR_ACCELERATION_LIMIT_TPS_S = 80.0", merged)

    def test_profile_supplies_drive_reduction(self):
        self.assertEqual(
            self.profile.parameters["motor_revolutions_per_wheel_revolution"],
            50.0,
        )


if __name__ == "__main__":
    unittest.main()
