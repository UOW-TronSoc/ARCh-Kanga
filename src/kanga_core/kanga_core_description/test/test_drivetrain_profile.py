import math
from pathlib import Path

import pytest

from kanga_core_description.drivetrain_profile import (
    DrivetrainProfileError,
    load_drivetrain_profile,
)


PROFILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "drivetrains"
    / "drivetrain_2025.yaml"
)


def test_2025_profile_derived_values():
    profile = load_drivetrain_profile(PROFILE)
    params = profile.parameters
    assert profile.profile_id == "drivetrain_2025"
    assert profile.display_name == "2025 drivetrain design"
    assert params["effective_wheel_radius_m"] == pytest.approx(0.115)
    assert params["half_length"] == pytest.approx(0.435)
    assert params["half_width"] == pytest.approx(0.355)
    assert params["max_wheel_joint_velocity_rad_s"] == pytest.approx(
        22.0 * 2.0 * math.pi / 50.0
    )
    assert params["max_wheel_joint_acceleration_rad_s2"] == pytest.approx(
        80.0 * 2.0 * math.pi / 50.0
    )
    assert params["limited_holonomic"] is True


def test_one_shared_dictionary_contains_raw_and_derived_values():
    profile = load_drivetrain_profile(PROFILE)
    params = profile.parameters
    assert params["wheel_diameter_m"] == pytest.approx(0.230)
    assert params["wheel_width_m"] == pytest.approx(0.180)
    assert params["grouser_angle_deg"] == pytest.approx(51.0)
    assert params["motor_revolutions_per_wheel_revolution"] == pytest.approx(50.0)
    assert params["motor_velocity_limit_tps"] == pytest.approx(22.0)
    assert params["motor_acceleration_limit_tps_s"] == pytest.approx(80.0)
    assert params["suspension_linkage_l1_mm"] == pytest.approx(545.5)
    assert params["suspension_linkage_l2_mm"] == pytest.approx(287.75)
    assert params["suspension_linkage_l3_mm"] == pytest.approx(194.7375)
    assert params["suspension_theta_at_beta_zero_deg"] == pytest.approx(30.0)


def test_new_parameter_group_is_forwarded_without_loader_changes(tmp_path):
    profile_file = tmp_path / "future.yaml"
    profile_file.write_text(
        PROFILE.read_text(encoding="utf-8")
        .replace("profile_id: drivetrain_2025", "profile_id: future")
        + "\nfuture_hardware:\n  suspension_revision: 2\n",
        encoding="utf-8",
    )
    profile = load_drivetrain_profile(profile_file)
    assert profile.parameters["suspension_revision"] == 2


def test_invalid_envelope_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """\
schema_version: 1
profile_id: bad
display_name: bad
drivetrain:
  motor_revolutions_per_wheel_revolution: 50
  motor_acceleration_limit_tps_s: 80
  motor_velocity_limit_tps: 22
wheel_geometry:
  wheel_diameter_m: 0.23
  wheel_width_m: 0.18
  overall_wheel_envelope_length_m: 0.20
  overall_wheel_envelope_width_m: 0.89
  grouser_angle_deg: 51
suspension_geometry:
  suspension_linkage_l1_mm: 545.5
  suspension_linkage_l2_mm: 287.75
  suspension_linkage_l3_mm: 194.7375
  suspension_theta_at_beta_zero_deg: 30
capabilities:
  limited_holonomic: true
""",
        encoding="utf-8",
    )
    with pytest.raises(DrivetrainProfileError, match="length must exceed"):
        load_drivetrain_profile(bad)
