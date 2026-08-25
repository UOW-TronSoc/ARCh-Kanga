"""Load editable motor limits without changing the physical drivetrain profile.

The drivetrain profile describes fixed hardware geometry and capability.  The
operator-facing motor-limit file is deliberately separate: it may lower the
velocity and acceleration used by the controller, drive clamp, and ODrive
commissioning, but it may never raise either value above the selected physical
profile.

This module is the single validation boundary for those editable values.  All
physical consumers should use ``load_effective_drivetrain_configuration`` so
they receive the same checked parameter dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml

from .drivetrain_profile import DrivetrainProfile, load_drivetrain_profile


DEFAULT_MOTOR_LIMITS = "core"

_VELOCITY_FIELD = "motor_velocity_limit_tps"
_ACCELERATION_FIELD = "motor_acceleration_limit_tps_s"
_EXPECTED_FIELDS = {_VELOCITY_FIELD, _ACCELERATION_FIELD}


class MotorLimitsError(ValueError):
    """Raised when editable limits are missing, malformed, or unsafe."""


@dataclass(frozen=True)
class MotorLimits:
    """Validated operating values and their immutable hardware ceilings."""

    source_path: Path
    motor_velocity_limit_tps: float
    motor_acceleration_limit_tps_s: float
    hard_motor_velocity_limit_tps: float
    hard_motor_acceleration_limit_tps_s: float


@dataclass(frozen=True)
class EffectiveDrivetrainConfiguration:
    """Physical profile plus the validated operating values used at launch.

    ``parameters`` is a copy of the profile parameter dictionary.  Only the
    two editable motor limits and their derived wheel-joint limits differ from
    the immutable physical profile.
    """

    profile: DrivetrainProfile
    motor_limits: MotorLimits
    parameters: dict[str, Any]


def _resolve_motor_limits_path(reference: str | Path) -> Path:
    """Resolve an explicit YAML path or an installed motor-limit name."""
    candidate = Path(reference)
    if candidate.is_file():
        return candidate.resolve()
    if candidate.parent != Path(".") or candidate.suffix:
        raise MotorLimitsError(f"motor-limit config not found: {reference}")

    # Explicit paths keep offline tests independent of a sourced ROS install.
    from ament_index_python.packages import get_package_share_directory

    share = Path(get_package_share_directory("kanga_core_description"))
    installed = share / "config" / "motor_limits" / f"{candidate.name}.yaml"
    if not installed.is_file():
        raise MotorLimitsError(
            f"unknown motor-limit config {candidate.name!r}: {installed} not found"
        )
    return installed


def _positive_number(mapping: dict[str, Any], field: str) -> float:
    """Read one required finite, positive number from a YAML mapping."""
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MotorLimitsError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise MotorLimitsError(f"{field} must be finite and > 0")
    return result


def load_motor_limits(
    reference: str | Path,
    hard_profile: DrivetrainProfile,
) -> MotorLimits:
    """Load editable limits and validate them against ``hard_profile``.

    The YAML intentionally contains only the two editable values.  Rejecting
    unknown keys catches spelling mistakes instead of silently ignoring an
    operator's intended setting.
    """
    path = _resolve_motor_limits_path(reference)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise MotorLimitsError(f"cannot read motor-limit config {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise MotorLimitsError("motor-limit config must be a YAML mapping")

    unknown_fields = set(raw) - _EXPECTED_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise MotorLimitsError(f"unknown motor-limit field(s): {names}")

    velocity = _positive_number(raw, _VELOCITY_FIELD)
    acceleration = _positive_number(raw, _ACCELERATION_FIELD)
    hard_velocity = float(hard_profile.parameters[_VELOCITY_FIELD])
    hard_acceleration = float(hard_profile.parameters[_ACCELERATION_FIELD])

    if velocity > hard_velocity:
        raise MotorLimitsError(
            f"{_VELOCITY_FIELD}={velocity:g} exceeds the "
            f"{hard_profile.profile_id} hard limit of {hard_velocity:g}"
        )
    if acceleration > hard_acceleration:
        raise MotorLimitsError(
            f"{_ACCELERATION_FIELD}={acceleration:g} exceeds the "
            f"{hard_profile.profile_id} hard limit of {hard_acceleration:g}"
        )

    return MotorLimits(
        source_path=path,
        motor_velocity_limit_tps=velocity,
        motor_acceleration_limit_tps_s=acceleration,
        hard_motor_velocity_limit_tps=hard_velocity,
        hard_motor_acceleration_limit_tps_s=hard_acceleration,
    )


def load_effective_drivetrain_configuration(
    profile_reference: str | Path,
    motor_limits_reference: str | Path = DEFAULT_MOTOR_LIMITS,
) -> EffectiveDrivetrainConfiguration:
    """Return one validated parameter set for physical runtime consumers."""
    profile = load_drivetrain_profile(profile_reference)
    motor_limits = load_motor_limits(motor_limits_reference, profile)

    # Copy before applying editable values.  The original profile object stays
    # unchanged and remains useful as the source of immutable hard maxima.
    parameters = dict(profile.parameters)
    parameters[_VELOCITY_FIELD] = motor_limits.motor_velocity_limit_tps
    parameters[_ACCELERATION_FIELD] = motor_limits.motor_acceleration_limit_tps_s

    gear_ratio = float(parameters["motor_revolutions_per_wheel_revolution"])
    parameters["max_wheel_joint_velocity_rad_s"] = (
        motor_limits.motor_velocity_limit_tps * 2.0 * math.pi / gear_ratio
    )
    parameters["max_wheel_joint_acceleration_rad_s2"] = (
        motor_limits.motor_acceleration_limit_tps_s * 2.0 * math.pi / gear_ratio
    )

    return EffectiveDrivetrainConfiguration(
        profile=profile,
        motor_limits=motor_limits,
        parameters=parameters,
    )
