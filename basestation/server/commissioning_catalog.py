"""
Fixed commissioning catalog for browser-visible subsystems and motors.

API callers select catalog IDs only. They never provide filesystem paths,
ROS namespaces, CAN node IDs, or shell arguments. Keeping those details here
makes the backend the authority for what the browser is allowed to operate.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .commissioning_errors import (
    CommissioningNotFound,
    CommissioningUnavailable,
)


@dataclass(frozen=True)
class MotorDefinition:
    """One motor identity plus its catalogued active/default files."""

    motor_id: str
    label: str
    namespace: str
    node_id: int
    active_config: Path
    default_config: Path

    def public_dict(self) -> dict:
        """Return browser-safe identity without exposing filesystem paths."""
        return {
            "id": self.motor_id,
            "label": self.label,
            "namespace": self.namespace,
            "node_id": self.node_id,
        }


@dataclass(frozen=True)
class SubsystemDefinition:
    """Commissioning contract for one rover subsystem."""

    subsystem_id: str
    label: str
    description: str
    available: bool
    can_interface: str | None = None
    drivetrain_profile: str | None = None
    active_shared_config: Path | None = None
    default_shared_config: Path | None = None
    active_soft_limits: Path | None = None
    default_soft_limits: Path | None = None
    hard_profile: Path | None = None
    motors: tuple[MotorDefinition, ...] = ()

    def require_available(self) -> None:
        if not self.available:
            raise CommissioningUnavailable(
                f"{self.label} commissioning is not available yet"
            )

    def motor(self, motor_id: str) -> MotorDefinition:
        """Resolve only a motor ID listed for this subsystem."""
        self.require_available()
        normalized = motor_id.strip().lower()
        for motor in self.motors:
            if motor.motor_id == normalized:
                return motor
        expected = ", ".join(motor.motor_id for motor in self.motors)
        raise CommissioningNotFound(
            f"unknown {self.subsystem_id} motor {motor_id!r}; expected {expected}"
        )

    def public_dict(self) -> dict:
        """Return the subsystem information needed to build dropdowns."""
        result = {
            "id": self.subsystem_id,
            "label": self.label,
            "description": self.description,
            "available": self.available,
            "motors": [motor.public_dict() for motor in self.motors],
        }
        if self.can_interface is not None:
            result["can_interface"] = self.can_interface
        if self.drivetrain_profile is not None:
            result["drivetrain_profile"] = self.drivetrain_profile
        return result


class CommissioningCatalog:
    """Read-only lookup around the fixed subsystem definitions."""

    def __init__(self, subsystems: tuple[SubsystemDefinition, ...]) -> None:
        self._subsystems = subsystems

    def subsystem(self, subsystem_id: str) -> SubsystemDefinition:
        normalized = subsystem_id.strip().lower()
        for subsystem in self._subsystems:
            if subsystem.subsystem_id == normalized:
                return subsystem
        expected = ", ".join(item.subsystem_id for item in self._subsystems)
        raise CommissioningNotFound(
            f"unknown subsystem {subsystem_id!r}; expected {expected}"
        )

    def public_dict(self) -> dict:
        return {
            "subsystems": [
                subsystem.public_dict() for subsystem in self._subsystems
            ]
        }


def default_workspace_root() -> Path:
    """Return the mounted workspace root, with an override for tests/deploys."""
    configured = os.environ.get("BASESTATION_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def build_commissioning_catalog(
    workspace_root: Path | None = None,
) -> CommissioningCatalog:
    """Build the fixed Core/Arm/Payload catalog under one workspace root."""
    root = (workspace_root or default_workspace_root()).resolve()
    drive = root / "src" / "kanga_core" / "kanga_core_drive"
    description = root / "src" / "kanga_core" / "kanga_core_description"
    active_motors = drive / "config" / "motors"
    default_motors = drive / "config" / "defaults" / "motors"

    # Keep this order and identity aligned with CORE_DRIVE_MOTORS in
    # kanga_core_drive/launch/drive.launch.py. An offline test checks the two.
    core_motor_rows = (
        ("fl", "Front left", "wheel_fl", 1),
        ("bl", "Back left", "wheel_bl", 2),
        ("br", "Back right", "wheel_br", 3),
        ("fr", "Front right", "wheel_fr", 4),
    )
    core_motors = tuple(
        MotorDefinition(
            motor_id=motor_id,
            label=label,
            namespace=namespace,
            node_id=node_id,
            active_config=active_motors / f"wheel_{motor_id}_motor_config.py",
            default_config=default_motors / f"wheel_{motor_id}_motor_config.py",
        )
        for motor_id, label, namespace, node_id in core_motor_rows
    )

    return CommissioningCatalog(
        (
            SubsystemDefinition(
                subsystem_id="core",
                label="Core",
                description="Four wheel ODrive S1 controllers on can_core",
                available=True,
                can_interface="can_core",
                drivetrain_profile="drivetrain_2025",
                active_shared_config=active_motors / "shared_motor_config.py",
                default_shared_config=default_motors / "shared_motor_config.py",
                active_soft_limits=(
                    description / "config" / "motor_limits" / "core.yaml"
                ),
                default_soft_limits=(
                    description
                    / "config"
                    / "defaults"
                    / "motor_limits"
                    / "core.yaml"
                ),
                hard_profile=(
                    description
                    / "config"
                    / "drivetrains"
                    / "drivetrain_2025.yaml"
                ),
                motors=core_motors,
            ),
            SubsystemDefinition(
                subsystem_id="arm",
                label="Arm",
                description="Motor contracts and configs have not been migrated yet",
                available=False,
            ),
            SubsystemDefinition(
                subsystem_id="payload",
                label="Payload",
                description="Payload commissioning hardware has not been defined yet",
                available=False,
            ),
        )
    )
