#!/usr/bin/env python3

"""
Offline consistency checks for the core drive motor specification.

The launch table is the readable source for launch-time motor identity. Fibre
files still need to contain a CAN node ID because that value is written into
each physical ODrive. These tests make that necessary duplication explicit and
fail if the launch table, commissioning order, or checked-in configs drift.
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
DESCRIPTION = PACKAGE.parent / "kanga_core_description"
LAUNCH_FILE = PACKAGE / "launch" / "drive.launch.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(DESCRIPTION))

from config_merge import WHEEL_IDS  # noqa: E402


def load_drive_launch_module():
    """Load drive.launch.py so its motor table can be checked offline."""
    module_spec = importlib.util.spec_from_file_location(
        "kanga_core_drive_launch",
        LAUNCH_FILE,
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Could not load launch file: {LAUNCH_FILE}")

    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


DRIVE_LAUNCH = load_drive_launch_module()
CORE_DRIVE_MOTORS = DRIVE_LAUNCH.CORE_DRIVE_MOTORS


class TestDriveMotorSpecs(unittest.TestCase):
    def test_table_order_matches_the_command_and_commissioning_order(self):
        self.assertEqual(tuple(CORE_DRIVE_MOTORS), WHEEL_IDS)

    def test_each_launch_identity_is_unique(self):
        for field in ("namespace", "joint_name", "node_id"):
            values = [motor[field] for motor in CORE_DRIVE_MOTORS.values()]
            self.assertEqual(
                len(values),
                len(set(values)),
                f"CORE_DRIVE_MOTORS contains duplicate {field} values",
            )

    def test_names_and_directions_describe_the_expected_wheels(self):
        for wheel_id, motor in CORE_DRIVE_MOTORS.items():
            self.assertEqual(motor["namespace"], f"wheel_{wheel_id}")
            self.assertEqual(motor["joint_name"], f"wheel_{wheel_id}_joint")
            self.assertIsInstance(motor["invert_direction"], bool)

        self.assertTrue(CORE_DRIVE_MOTORS["fl"]["invert_direction"])
        self.assertTrue(CORE_DRIVE_MOTORS["bl"]["invert_direction"])
        self.assertFalse(CORE_DRIVE_MOTORS["br"]["invert_direction"])
        self.assertFalse(CORE_DRIVE_MOTORS["fr"]["invert_direction"])

    def test_node_ids_match_active_and_default_fibre_configs(self):
        config_directories = (
            PACKAGE / "config" / "motors",
            PACKAGE / "config" / "defaults" / "motors",
        )
        node_id_assignment = re.compile(
            r"^\s*odrv\.axis0\.config\.can\.node_id\s*=\s*(\d+)\s*$",
            re.MULTILINE,
        )

        for wheel_id, motor in CORE_DRIVE_MOTORS.items():
            for config_directory in config_directories:
                config_path = (
                    config_directory / f"wheel_{wheel_id}_motor_config.py"
                )
                matches = node_id_assignment.findall(
                    config_path.read_text(encoding="utf-8")
                )
                self.assertEqual(
                    matches,
                    [str(motor["node_id"])],
                    f"CAN node ID in {config_path} does not match the launch table",
                )


if __name__ == "__main__":
    unittest.main()
