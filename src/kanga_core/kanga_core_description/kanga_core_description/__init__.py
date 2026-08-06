"""Shared physical configuration for the Kanga rover core."""

from .drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
    DrivetrainProfile,
    DrivetrainProfileError,
    load_drivetrain_profile,
)

__all__ = [
    "DEFAULT_DRIVETRAIN_PROFILE",
    "DrivetrainProfile",
    "DrivetrainProfileError",
    "load_drivetrain_profile",
]
