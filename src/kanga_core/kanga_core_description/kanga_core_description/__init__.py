"""Shared physical configuration for the Kanga rover core."""

from .drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
    DrivetrainProfile,
    DrivetrainProfileError,
    load_drivetrain_profile,
)
from .motor_limits import (
    DEFAULT_MOTOR_LIMITS,
    EffectiveDrivetrainConfiguration,
    MotorLimits,
    MotorLimitsError,
    load_effective_drivetrain_configuration,
    load_motor_limits,
)

__all__ = [
    "DEFAULT_DRIVETRAIN_PROFILE",
    "DrivetrainProfile",
    "DrivetrainProfileError",
    "load_drivetrain_profile",
    "DEFAULT_MOTOR_LIMITS",
    "EffectiveDrivetrainConfiguration",
    "MotorLimits",
    "MotorLimitsError",
    "load_effective_drivetrain_configuration",
    "load_motor_limits",
]
