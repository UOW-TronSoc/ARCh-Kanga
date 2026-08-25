import math
from pathlib import Path

import pytest

from kanga_core_description.drivetrain_profile import load_drivetrain_profile
from kanga_core_description.motor_limits import (
    MotorLimitsError,
    load_effective_drivetrain_configuration,
    load_motor_limits,
)


PACKAGE = Path(__file__).resolve().parents[1]
PROFILE = PACKAGE / "config" / "drivetrains" / "drivetrain_2025.yaml"
ACTIVE_LIMITS = PACKAGE / "config" / "motor_limits" / "core.yaml"


def _write_limits(tmp_path: Path, velocity: str, acceleration: str) -> Path:
    """Write one small limit file for validation tests."""
    path = tmp_path / "limits.yaml"
    path.write_text(
        "motor_velocity_limit_tps: "
        f"{velocity}\n"
        "motor_acceleration_limit_tps_s: "
        f"{acceleration}\n",
        encoding="utf-8",
    )
    return path


def test_active_limits_match_the_initial_profile_caps():
    profile = load_drivetrain_profile(PROFILE)
    limits = load_motor_limits(ACTIVE_LIMITS, profile)

    assert limits.motor_velocity_limit_tps == pytest.approx(22.0)
    assert limits.motor_acceleration_limit_tps_s == pytest.approx(80.0)
    assert limits.hard_motor_velocity_limit_tps == pytest.approx(22.0)
    assert limits.hard_motor_acceleration_limit_tps_s == pytest.approx(80.0)


def test_lower_limits_replace_runtime_and_derived_values(tmp_path):
    limits_path = _write_limits(tmp_path, velocity="11.0", acceleration="40.0")
    effective = load_effective_drivetrain_configuration(PROFILE, limits_path)

    assert effective.parameters["motor_velocity_limit_tps"] == pytest.approx(11.0)
    assert effective.parameters["motor_acceleration_limit_tps_s"] == pytest.approx(40.0)
    assert effective.parameters["max_wheel_joint_velocity_rad_s"] == pytest.approx(
        11.0 * 2.0 * math.pi / 50.0
    )
    assert effective.parameters[
        "max_wheel_joint_acceleration_rad_s2"
    ] == pytest.approx(40.0 * 2.0 * math.pi / 50.0)

    # Applying soft limits must never mutate the hard profile dictionary.
    assert effective.profile.parameters["motor_velocity_limit_tps"] == pytest.approx(22.0)
    assert effective.profile.parameters[
        "motor_acceleration_limit_tps_s"
    ] == pytest.approx(80.0)


@pytest.mark.parametrize(
    ("velocity", "acceleration", "message"),
    [
        ("22.1", "80.0", "exceeds the drivetrain_2025 hard limit of 22"),
        ("22.0", "80.1", "exceeds the drivetrain_2025 hard limit of 80"),
        ("0", "80.0", "must be finite and > 0"),
        (".nan", "80.0", "must be finite and > 0"),
    ],
)
def test_invalid_or_above_profile_limits_are_rejected(
    tmp_path,
    velocity,
    acceleration,
    message,
):
    profile = load_drivetrain_profile(PROFILE)
    limits_path = _write_limits(tmp_path, velocity, acceleration)

    with pytest.raises(MotorLimitsError, match=message):
        load_motor_limits(limits_path, profile)


def test_unknown_fields_are_rejected_as_likely_typos(tmp_path):
    profile = load_drivetrain_profile(PROFILE)
    limits_path = _write_limits(tmp_path, velocity="10.0", acceleration="20.0")
    limits_path.write_text(
        limits_path.read_text(encoding="utf-8") + "motor_velcity_limit_tps: 5\n",
        encoding="utf-8",
    )

    with pytest.raises(MotorLimitsError, match="unknown motor-limit field"):
        load_motor_limits(limits_path, profile)
