#!/usr/bin/env python3
"""Offline tests for the Kanga commissioning command wrapper."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
DESCRIPTION = PACKAGE.parent / "kanga_core_description"
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(DESCRIPTION))

import commission_wheels  # noqa: E402


class TestCommissionWheels(unittest.TestCase):
    def test_wheel_selection_preserves_order_and_removes_duplicates(self):
        self.assertEqual(
            commission_wheels.parse_wheels("fr, fl,fr, bl"),
            ["fr", "fl", "bl"],
        )

    def test_calibration_of_multiple_wheels_is_rejected_before_loading_config(self):
        with self.assertRaises(SystemExit):
            commission_wheels.main(["--wheels", "all", "--calibrate"])

    def test_confirmation_without_calibration_is_rejected(self):
        with self.assertRaises(SystemExit):
            commission_wheels.main(
                ["--wheels", "fl", "--off-ground-confirmed"]
            )

    def test_preconfirmed_bench_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            commission_wheels.main(
                [
                    "--wheels",
                    "fl",
                    "--calibrate",
                    "--off-ground-confirmed",
                    "--bench",
                ]
            )

    def test_interactive_calibration_does_not_claim_prior_confirmation(self):
        with patch.object(
            commission_wheels.subprocess,
            "call",
            return_value=0,
        ) as subprocess_call:
            result = commission_wheels.run_commission(
                can_interface="can_core",
                config=Path("/tmp/wheel_fl.py"),
                wheel_namespace="/wheel_fl",
                calibrate=True,
                save=False,
                off_ground_confirmed=False,
            )

        self.assertEqual(result, 0)
        command = subprocess_call.call_args.args[0]
        self.assertIn("--calibrate", command)
        self.assertNotIn("--off-ground-confirmed", command)
        self.assertNotIn("--save", command)

    def test_orchestrated_calibration_forwards_confirmation_and_save(self):
        with patch.object(
            commission_wheels.subprocess,
            "run",
        ) as subprocess_run:
            subprocess_run.return_value.returncode = 0
            result = commission_wheels.run_commission(
                can_interface="can_core",
                config=Path("/tmp/wheel_fl.py"),
                wheel_namespace="/wheel_fl",
                calibrate=True,
                save=True,
                off_ground_confirmed=True,
            )

        self.assertEqual(result, 0)
        command = subprocess_run.call_args.args[0]
        self.assertEqual(command[command.index("--ns") + 1], "/wheel_fl")
        self.assertIn("--calibrate", command)
        self.assertIn("--save", command)
        self.assertNotIn("--off-ground-confirmed", command)
        self.assertEqual(subprocess_run.call_args.kwargs["input"], "yes\n")
        self.assertTrue(subprocess_run.call_args.kwargs["text"])
        self.assertFalse(subprocess_run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
