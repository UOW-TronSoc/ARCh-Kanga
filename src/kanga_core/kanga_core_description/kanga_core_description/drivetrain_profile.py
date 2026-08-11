"""Load one drivetrain YAML into one shared ROS-parameter dictionary.

Most values are copied through automatically. Only values that are genuinely
derived (wheel centres, radius, and joint velocity limit) are calculated here.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml


DEFAULT_DRIVETRAIN_PROFILE = "drivetrain_2025"


class DrivetrainProfileError(ValueError):
    """Raised when a drivetrain profile is missing or physically invalid."""


# Require a YAML value to be a key/value mapping.
def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DrivetrainProfileError(f"{field} must be a mapping")
    return value


# Read and validate a required non-empty text value.
def _text(mapping: dict[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DrivetrainProfileError(f"{field} must be a non-empty string")
    return value.strip()


# Read and validate a required positive numeric value.
def _positive_number(mapping: dict[str, Any], field: str) -> float:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DrivetrainProfileError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise DrivetrainProfileError(f"{field} must be finite and > 0")
    return result


# Read and validate a required boolean value.
def _boolean(mapping: dict[str, Any], field: str) -> bool:
    value = mapping.get(field)
    if not isinstance(value, bool):
        raise DrivetrainProfileError(f"{field} must be true or false")
    return value


@dataclass(frozen=True)
class DrivetrainProfile:
    """Profile metadata plus the shared parameters passed to consumer nodes."""

    profile_id: str
    display_name: str
    parameters: dict[str, Any]


# Resolve either an explicit YAML path or an installed profile name.
def _resolve_profile_path(profile: str | Path) -> Path:
    candidate = Path(profile)
    if candidate.is_file():
        return candidate.resolve()
    if candidate.parent != Path(".") or candidate.suffix:
        raise DrivetrainProfileError(f"drivetrain profile not found: {profile}")

    # Keep explicit-path loading usable in offline tests that do not source ROS.
    from ament_index_python.packages import get_package_share_directory

    share = Path(get_package_share_directory("kanga_core_description"))
    installed = share / "config" / "drivetrains" / f"{candidate.name}.yaml"
    if not installed.is_file():
        raise DrivetrainProfileError(
            f"unknown drivetrain profile {candidate.name!r}: {installed} not found"
        )
    return installed


# Load, flatten, validate, and derive the shared drivetrain parameters.
def load_drivetrain_profile(profile: str | Path) -> DrivetrainProfile:
    """Load a profile id/path and return one shared parameter dictionary.

    Every value inside a top-level parameter group (for example `drivetrain` or
    `wheel_geometry`) is copied into `parameters`. Adding an ordinary parameter
    to the YAML therefore does not require modifying this loader.
    """
    path = _resolve_profile_path(profile)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DrivetrainProfileError(f"cannot read drivetrain profile {path}: {exc}") from exc

    root = _mapping(raw, "profile")
    schema_version = root.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise DrivetrainProfileError(
            f"schema_version must be 1, got {schema_version!r}"
        )

    profile_id = _text(root, "profile_id")
    display_name = _text(root, "display_name")
    if profile_id != path.stem:
        raise DrivetrainProfileError(
            f"profile_id {profile_id!r} must match filename {path.stem!r}"
        )

    # Flatten all parameter groups into one dictionary. This is deliberately
    # generic: a new scalar parameter or a new group flows to launch consumers
    # without adding another dataclass field or per-node parameter list here.
    parameters: dict[str, Any] = {}
    metadata_keys = {"schema_version", "profile_id", "display_name"}
    for group_name, group_value in root.items():
        if group_name in metadata_keys:
            continue
        group = _mapping(group_value, group_name)
        for name, value in group.items():
            if name in parameters:
                raise DrivetrainProfileError(
                    f"parameter {name!r} is repeated in multiple groups"
                )
            parameters[name] = value

    # Validate only the inputs needed for the calculations below. Other shared
    # parameters pass through untouched and are validated by the node using them.
    ratio = _positive_number(parameters, "motor_revolutions_per_wheel_revolution")
    motor_limit_tps = _positive_number(parameters, "motor_velocity_limit_tps")
    motor_acceleration_limit_tps_s = _positive_number(
        parameters, "motor_acceleration_limit_tps_s"
    )
    wheel_diameter = _positive_number(parameters, "wheel_diameter_m")
    wheel_width = _positive_number(parameters, "wheel_width_m")
    overall_length = _positive_number(parameters, "overall_wheel_envelope_length_m")
    overall_width = _positive_number(parameters, "overall_wheel_envelope_width_m")
    grouser_angle = _positive_number(parameters, "grouser_angle_deg")
    _positive_number(parameters, "suspension_linkage_l1_mm")
    _positive_number(parameters, "suspension_linkage_l2_mm")
    _positive_number(parameters, "suspension_linkage_l3_mm")
    _positive_number(parameters, "suspension_theta_at_beta_zero_deg")
    _boolean(parameters, "limited_holonomic")

    if overall_length <= wheel_diameter:
        raise DrivetrainProfileError(
            "overall wheel envelope length must exceed wheel diameter"
        )
    if overall_width <= wheel_width:
        raise DrivetrainProfileError(
            "overall wheel envelope width must exceed wheel width"
        )

    theta_rad = math.radians(grouser_angle)
    if abs(math.cos(theta_rad)) < 1e-9:
        raise DrivetrainProfileError("grouser_angle_deg must have non-zero cosine")

    # These values are derived once here rather than copied into the YAML.
    radius_override = parameters.get("effective_rolling_radius_m")
    if radius_override is not None:
        radius_override = _positive_number(parameters, "effective_rolling_radius_m")
    parameters["effective_wheel_radius_m"] = (
        radius_override if radius_override is not None else wheel_diameter / 2.0
    )
    parameters["half_length"] = (overall_length - wheel_diameter) / 2.0
    parameters["half_width"] = (overall_width - wheel_width) / 2.0
    parameters["max_wheel_joint_velocity_rad_s"] = (
        motor_limit_tps * 2.0 * math.pi / ratio
    )
    parameters["max_wheel_joint_acceleration_rad_s2"] = (
        motor_acceleration_limit_tps_s * 2.0 * math.pi / ratio
    )
    return DrivetrainProfile(
        profile_id=profile_id,
        display_name=display_name,
        parameters=parameters,
    )
