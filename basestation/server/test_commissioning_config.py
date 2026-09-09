"""Offline tests for the protected commissioning catalog and file storage."""

from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path

from .commissioning_catalog import build_commissioning_catalog
from .commissioning_config import (
    CommissioningConfigStore,
    MotorConfigValidator,
)
from .commissioning_errors import (
    CommissioningRevisionConflict,
    CommissioningUnavailable,
    CommissioningValidationError,
)


REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG_FILES = (
    "src/kanga_core/kanga_core_drive/config/motors/shared_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/motors/wheel_fl_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/motors/wheel_bl_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/motors/wheel_br_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/motors/wheel_fr_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/defaults/motors/shared_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/defaults/motors/wheel_fl_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/defaults/motors/wheel_bl_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/defaults/motors/wheel_br_motor_config.py",
    "src/kanga_core/kanga_core_drive/config/defaults/motors/wheel_fr_motor_config.py",
    "src/kanga_core/kanga_core_description/config/motor_limits/core.yaml",
    "src/kanga_core/kanga_core_description/config/defaults/motor_limits/core.yaml",
    "src/kanga_core/kanga_core_description/config/drivetrains/drivetrain_2025.yaml",
)


def copy_config_workspace(destination: Path) -> None:
    """Copy only the files Step 3 may read or replace into a temporary root."""
    for relative_name in CONFIG_FILES:
        source = REPOSITORY / relative_name
        target = destination / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class CommissioningConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        copy_config_workspace(self.workspace)
        self.catalog = build_commissioning_catalog(self.workspace)
        self.store = CommissioningConfigStore(self.catalog)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_catalog_exposes_fixed_core_order_without_paths(self) -> None:
        public_catalog = self.catalog.public_dict()
        core, arm, payload = public_catalog["subsystems"]

        self.assertEqual([core["id"], arm["id"], payload["id"]], ["core", "arm", "payload"])
        self.assertEqual(
            [motor["id"] for motor in core["motors"]],
            ["fl", "bl", "br", "fr"],
        )
        self.assertEqual(
            [motor["node_id"] for motor in core["motors"]],
            [1, 2, 3, 4],
        )
        self.assertNotIn(str(self.workspace), str(public_catalog))
        self.assertFalse(arm["available"])
        self.assertFalse(payload["available"])

    def test_catalog_identity_matches_the_drive_launch_motor_table(self) -> None:
        launch_path = (
            REPOSITORY
            / "src"
            / "kanga_core"
            / "kanga_core_drive"
            / "launch"
            / "drive.launch.py"
        )
        launch_tree = ast.parse(launch_path.read_text(encoding="utf-8"))
        launch_table = None
        for statement in launch_tree.body:
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "CORE_DRIVE_MOTORS"
            ):
                launch_table = ast.literal_eval(statement.value)
                break
        self.assertIsNotNone(launch_table)

        core = self.catalog.subsystem("core")
        self.assertEqual(tuple(launch_table), tuple(m.motor_id for m in core.motors))
        for motor in core.motors:
            self.assertEqual(
                launch_table[motor.motor_id]["namespace"],
                motor.namespace,
            )
            self.assertEqual(
                launch_table[motor.motor_id]["node_id"],
                motor.node_id,
            )

    def test_checked_in_motor_configs_pass_the_declarative_validator(self) -> None:
        validator = MotorConfigValidator()
        core = self.catalog.subsystem("core")
        validator.validate_shared(core.active_shared_config.read_text(encoding="utf-8"))
        validator.validate_shared(core.default_shared_config.read_text(encoding="utf-8"))
        for motor in core.motors:
            for path in (motor.active_config, motor.default_config):
                serial = validator.validate_individual(
                    path.read_text(encoding="utf-8"),
                    motor.node_id,
                )
                self.assertTrue(serial)

    def test_shared_read_returns_complete_active_and_default_files(self) -> None:
        document = self.store.read_motor_config("core", "shared")
        self.assertIn("vel_limit_tolerance", document["content"])
        self.assertIn("spinout_mechanical_power_bandwidth", document["content"])
        self.assertIn("default_content", document)
        self.assertEqual(len(document["revision"]), 64)

    def test_valid_shared_write_is_atomic_and_rejects_stale_revision(self) -> None:
        original = self.store.read_motor_config("core", "shared")
        changed_content = original["content"] + "\nodrv.config.enable_uart_b = False\n"
        saved = self.store.write_motor_config(
            "core",
            "shared",
            changed_content,
            original["revision"],
        )
        self.assertEqual(saved["content"], changed_content)
        self.assertNotEqual(saved["revision"], original["revision"])

        with self.assertRaises(CommissioningRevisionConflict):
            self.store.write_motor_config(
                "core",
                "shared",
                original["content"],
                original["revision"],
            )

        active_path = self.catalog.subsystem("core").active_shared_config
        self.assertEqual(active_path.read_text(encoding="utf-8"), changed_content)
        self.assertEqual(list(active_path.parent.glob(".*.tmp")), [])

    def test_shared_validator_rejects_executable_or_protected_content(self) -> None:
        validator = MotorConfigValidator()
        invalid_documents = (
            "import os\n",
            "odrv.save_configuration()\n",
            "for value in [1]:\n    odrv.config.enable_uart_a = False\n",
            "MOTOR_VELOCITY_LIMIT_TPS = 99\n",
            "odrv.axis0.controller.config.vel_limit = 99\n",
            "odrv.axis0.controller.config.vel_ramp_rate = 99\n",
            "SERIAL_NUMBER = 'not-shared'\n",
            "SERIAL_NUMBER = MotorType.PMSM_CURRENT_CONTROL\n",
            "odrv.axis0.config.can.node_id = 1\n",
            "odrv.axis0.config.can.node_id = math.inf\n",
        )
        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(CommissioningValidationError):
                    validator.validate_shared(content)

        # This is a declarative assignment using an enum exposed by the pinned
        # ODrive library, so it remains valid even though it is not used today.
        validator.validate_shared(
            "odrv.axis0.motor.motor_thermistor.config.mode = "
            "ThermistorMode.PTC\n"
        )

    def test_individual_write_requires_fixed_identity_and_unique_serial(self) -> None:
        fl_document = self.store.read_motor_config("core", "fl")
        cases = (
            (
                fl_document["content"].replace("node_id = 1", "node_id = 9"),
                "node_id",
            ),
            (
                fl_document["content"].replace(
                    'SERIAL_NUMBER = "394D353B3231"\n',
                    "",
                ),
                "SERIAL_NUMBER",
            ),
            (
                fl_document["content"].replace(
                    'SERIAL_NUMBER = "394D353B3231"',
                    'SERIAL_NUMBER = "396934453331"',
                ),
                "duplicates bl",
            ),
            (
                fl_document["content"].replace(
                    'SERIAL_NUMBER = "394D353B3231"',
                    'SERIAL_NUMBER = make_serial()',
                ),
                "values must be literals",
            ),
        )
        for content, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with self.assertRaisesRegex(
                    CommissioningValidationError,
                    expected_message,
                ):
                    self.store.write_motor_config(
                        "core",
                        "fl",
                        content,
                        fl_document["revision"],
                    )

    def test_soft_limits_report_hard_caps_and_accept_lower_values(self) -> None:
        original = self.store.read_soft_limits("core")
        self.assertEqual(original["hard_maxima"]["motor_velocity_limit_tps"], 22.0)
        lower = (
            "motor_velocity_limit_tps: 18.0\n"
            "motor_acceleration_limit_tps_s: 60.0\n"
        )
        saved = self.store.write_soft_limits(
            "core",
            lower,
            original["revision"],
        )
        self.assertEqual(saved["values"]["motor_velocity_limit_tps"], 18.0)
        self.assertTrue(saved["relaunch_required"])

    def test_soft_limits_reject_unknown_or_above_profile_values(self) -> None:
        original = self.store.read_soft_limits("core")
        invalid_documents = (
            "motor_velocity_limit_tps: 23\nmotor_acceleration_limit_tps_s: 80\n",
            "motor_velocity_limit_tps: 22\nmotor_acceleration_limit_tps_s: 81\n",
            "motor_velocity_limit_tps: 22\nmotor_acceleration_limit_tps_s: 80\nextra: 1\n",
            "motor_velocity_limit_tps: .inf\nmotor_acceleration_limit_tps_s: 80\n",
        )
        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(CommissioningValidationError):
                    self.store.write_soft_limits(
                        "core",
                        content,
                        original["revision"],
                    )

    def test_unavailable_subsystem_cannot_resolve_config(self) -> None:
        with self.assertRaises(CommissioningUnavailable):
            self.store.read_motor_config("arm", "shared")


if __name__ == "__main__":
    unittest.main()
