"""
Validated and atomic storage for browser-editable commissioning files.

Motor files are treated as a small declarative assignment language. They are
parsed with Python's AST but never executed by the server. Soft limits are
parsed as YAML and checked against the unchanged drivetrain-profile ceilings.
"""

from __future__ import annotations

import ast
import hashlib
import math
import os
from pathlib import Path
import stat
import tempfile
import threading
from typing import Any

import yaml

from .commissioning_catalog import (
    CommissioningCatalog,
    MotorDefinition,
    SubsystemDefinition,
)
from .commissioning_errors import (
    CommissioningRevisionConflict,
    CommissioningStorageError,
    CommissioningValidationError,
)


MAX_CONFIG_BYTES = 256 * 1024
SERIAL_NAME = "SERIAL_NUMBER"
PROTECTED_LIMIT_NAMES = {
    "MOTOR_VELOCITY_LIMIT_TPS",
    "MOTOR_ACCELERATION_LIMIT_TPS_S",
}
PROTECTED_ODRIVE_TARGETS = {
    "odrv.axis0.controller.config.vel_limit",
    "odrv.axis0.controller.config.vel_ramp_rate",
}
SUPPORTED_ENUM_TYPES = {
    "ArmedState",
    "AxisError",
    "AxisState",
    "CanError",
    "ComponentStatus",
    "ControlMode",
    "ControllerError",
    "DrvFault",
    "EncoderError",
    "EncoderFieldStatus",
    "EncoderId",
    "EncoderMode",
    "FieldStrengthMonitoring",
    "GpioMode",
    "IncrementalEncoderFilter",
    "InputMode",
    "LegacyODriveError",
    "LockinState",
    "MotorError",
    "MotorType",
    "ODriveError",
    "ProcedureResult",
    "Protocol",
    "Rs485EncoderMode",
    "SensorlessEstimatorError",
    "SpiEncoderMode",
    "StreamProtocolType",
    "ThermistorCurrentLimiterError",
    "ThermistorMode",
}
SOFT_LIMIT_FIELDS = (
    "motor_velocity_limit_tps",
    "motor_acceleration_limit_tps_s",
)


def content_revision(content: str) -> str:
    """Return the stable revision token used for optimistic file writes."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _attribute_path(node: ast.AST) -> str | None:
    """Return a dotted name for simple Name/Attribute expressions."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _validate_literal(node: ast.AST, line_number: int) -> None:
    """Allow inert literals, supported enums, math.inf, and limit constants."""
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (str, int, float, bool)):
            raise CommissioningValidationError(
                f"line {line_number}: unsupported literal {node.value!r}"
            )
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise CommissioningValidationError(
                f"line {line_number}: write infinity as math.inf"
            )
        return

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        _validate_literal(node.operand, line_number)
        return

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            _validate_literal(element, line_number)
        return

    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise CommissioningValidationError(
                    f"line {line_number}: dictionary unpacking is not allowed"
                )
            _validate_literal(key, line_number)
            _validate_literal(value, line_number)
        return

    path = _attribute_path(node)
    if path == "math.inf":
        return
    if path is not None:
        root, separator, member = path.partition(".")
        if root in SUPPORTED_ENUM_TYPES and separator and "." not in member:
            return

    if isinstance(node, ast.Name) and node.id in PROTECTED_LIMIT_NAMES:
        return

    raise CommissioningValidationError(
        f"line {line_number}: values must be literals, supported enums, "
        "math.inf, or injected motor-limit constants"
    )


class MotorConfigValidator:
    """Validate shared and per-motor Fibre files without executing them."""

    def validate_shared(self, content: str) -> None:
        metadata = self._validate_assignments(content)
        if metadata["serial_count"]:
            raise CommissioningValidationError(
                "SERIAL_NUMBER belongs in an individual motor config"
            )
        if metadata["node_id_count"]:
            raise CommissioningValidationError(
                "CAN node_id belongs in an individual motor config"
            )

    def validate_individual(
        self,
        content: str,
        expected_node_id: int,
    ) -> str:
        metadata = self._validate_assignments(content)
        serial = metadata["serial"]
        if not isinstance(serial, str) or not serial.strip():
            raise CommissioningValidationError(
                "individual config requires a literal, non-empty SERIAL_NUMBER"
            )
        node_id = metadata["node_id"]
        if node_id != expected_node_id:
            raise CommissioningValidationError(
                f"CAN node_id must remain {expected_node_id}, got {node_id!r}"
            )
        return serial.strip()

    def _validate_assignments(self, content: str) -> dict[str, Any]:
        _validate_content_size(content)
        try:
            tree = ast.parse(content, mode="exec")
        except SyntaxError as exc:
            location = f"line {exc.lineno}" if exc.lineno else "unknown line"
            raise CommissioningValidationError(
                f"invalid Python syntax at {location}: {exc.msg}"
            ) from exc

        serial: str | None = None
        serial_count = 0
        node_id: int | None = None
        node_id_count = 0

        for statement in tree.body:
            if not isinstance(statement, ast.Assign):
                raise CommissioningValidationError(
                    f"line {statement.lineno}: only declarative assignments are allowed"
                )
            if len(statement.targets) != 1:
                raise CommissioningValidationError(
                    f"line {statement.lineno}: chained assignments are not allowed"
                )

            target = statement.targets[0]
            target_path = _attribute_path(target)
            if target_path is None:
                raise CommissioningValidationError(
                    f"line {statement.lineno}: assignment target is not supported"
                )
            if target_path in PROTECTED_LIMIT_NAMES:
                raise CommissioningValidationError(
                    f"line {statement.lineno}: {target_path} is protected by soft limits"
                )
            if target_path in PROTECTED_ODRIVE_TARGETS:
                raise CommissioningValidationError(
                    f"line {statement.lineno}: {target_path} is protected by soft limits"
                )
            if target_path != SERIAL_NAME and not target_path.startswith("odrv."):
                raise CommissioningValidationError(
                    f"line {statement.lineno}: target must be SERIAL_NUMBER or odrv.*"
                )

            _validate_literal(statement.value, statement.lineno)

            if target_path == SERIAL_NAME:
                serial_count += 1
                if isinstance(statement.value, ast.Constant):
                    serial = statement.value.value
                else:
                    serial = None

            if target_path == "odrv.axis0.config.can.node_id":
                node_id_count += 1
                if (
                    isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, int)
                    and not isinstance(statement.value.value, bool)
                ):
                    node_id = statement.value.value
                else:
                    node_id = None

        if serial_count > 1:
            raise CommissioningValidationError(
                "SERIAL_NUMBER may only be assigned once"
            )
        if node_id_count > 1:
            raise CommissioningValidationError("CAN node_id may only be assigned once")
        return {
            "serial": serial,
            "serial_count": serial_count,
            "node_id": node_id,
            "node_id_count": node_id_count,
        }


def _validate_content_size(content: str) -> None:
    size = len(content.encode("utf-8"))
    if size > MAX_CONFIG_BYTES:
        raise CommissioningValidationError(
            f"config is {size} bytes; maximum is {MAX_CONFIG_BYTES}"
        )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommissioningStorageError(f"cannot read {path.name}: {exc}") from exc


def _atomic_write(path: Path, content: str) -> None:
    """Replace one file atomically while retaining its existing permissions."""
    _validate_content_size(content)
    try:
        original_mode = stat.S_IMODE(path.stat().st_mode)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
    except OSError as exc:
        raise CommissioningStorageError(
            f"cannot prepare atomic write for {path.name}: {exc}"
        ) from exc

    temporary_path = Path(temporary_name)
    try:
        os.fchmod(file_descriptor, original_mode)
        # fdopen takes ownership. Mark the raw descriptor closed before any
        # later exception reaches finally, where only an unowned fd is closed.
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as file:
            file_descriptor = -1
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        raise CommissioningStorageError(f"cannot save {path.name}: {exc}") from exc
    finally:
        if file_descriptor >= 0:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _require_paths(
    subsystem: SubsystemDefinition,
    *paths: Path | None,
) -> tuple[Path, ...]:
    subsystem.require_available()
    if any(path is None for path in paths):
        raise CommissioningValidationError(
            f"{subsystem.label} does not define the requested config files"
        )
    return tuple(path for path in paths if path is not None)


class CommissioningConfigStore:
    """Read and write only files resolved through CommissioningCatalog."""

    def __init__(self, catalog: CommissioningCatalog) -> None:
        self.catalog = catalog
        self._validator = MotorConfigValidator()
        self._write_lock = threading.RLock()

    def read_motor_config(self, subsystem_id: str, scope: str) -> dict:
        subsystem = self.catalog.subsystem(subsystem_id)
        active_path, default_path, motor = self._motor_config_paths(
            subsystem,
            scope,
        )
        content = _read_text(active_path)
        default_content = _read_text(default_path)
        return self._motor_document(
            subsystem,
            scope,
            motor,
            content,
            default_content,
        )

    def write_motor_config(
        self,
        subsystem_id: str,
        scope: str,
        content: str,
        revision: str,
    ) -> dict:
        subsystem = self.catalog.subsystem(subsystem_id)
        with self._write_lock:
            active_path, default_path, motor = self._motor_config_paths(
                subsystem,
                scope,
            )
            current = _read_text(active_path)
            self._check_revision(current, revision)

            if motor is None:
                self._validator.validate_shared(content)
            else:
                candidate_serial = self._validator.validate_individual(
                    content,
                    motor.node_id,
                )
                self._require_unique_serial(
                    subsystem,
                    motor,
                    candidate_serial,
                )

            _atomic_write(active_path, content)
            return self._motor_document(
                subsystem,
                scope,
                motor,
                content,
                _read_text(default_path),
            )

    def read_soft_limits(self, subsystem_id: str) -> dict:
        subsystem = self.catalog.subsystem(subsystem_id)
        active_path, default_path, hard_profile = _require_paths(
            subsystem,
            subsystem.active_soft_limits,
            subsystem.default_soft_limits,
            subsystem.hard_profile,
        )
        content = _read_text(active_path)
        values, hard_maxima, profile_id = self._validate_soft_limits(
            content,
            hard_profile,
        )
        return self._soft_limit_document(
            subsystem,
            content,
            _read_text(default_path),
            values,
            hard_maxima,
            profile_id,
        )

    def write_soft_limits(
        self,
        subsystem_id: str,
        content: str,
        revision: str,
    ) -> dict:
        subsystem = self.catalog.subsystem(subsystem_id)
        with self._write_lock:
            active_path, default_path, hard_profile = _require_paths(
                subsystem,
                subsystem.active_soft_limits,
                subsystem.default_soft_limits,
                subsystem.hard_profile,
            )
            current = _read_text(active_path)
            self._check_revision(current, revision)
            values, hard_maxima, profile_id = self._validate_soft_limits(
                content,
                hard_profile,
            )
            _atomic_write(active_path, content)
            return self._soft_limit_document(
                subsystem,
                content,
                _read_text(default_path),
                values,
                hard_maxima,
                profile_id,
            )

    def _motor_config_paths(
        self,
        subsystem: SubsystemDefinition,
        scope: str,
    ) -> tuple[Path, Path, MotorDefinition | None]:
        subsystem.require_available()
        normalized = scope.strip().lower()
        if normalized == "shared":
            active, default = _require_paths(
                subsystem,
                subsystem.active_shared_config,
                subsystem.default_shared_config,
            )
            return active, default, None

        motor = subsystem.motor(normalized)
        return motor.active_config, motor.default_config, motor

    def _require_unique_serial(
        self,
        subsystem: SubsystemDefinition,
        selected_motor: MotorDefinition,
        candidate_serial: str,
    ) -> None:
        normalized_candidate = candidate_serial.casefold()
        for other_motor in subsystem.motors:
            if other_motor.motor_id == selected_motor.motor_id:
                continue
            other_content = _read_text(other_motor.active_config)
            other_serial = self._validator.validate_individual(
                other_content,
                other_motor.node_id,
            )
            if other_serial.casefold() == normalized_candidate:
                raise CommissioningValidationError(
                    f"SERIAL_NUMBER duplicates {other_motor.motor_id}"
                )

    @staticmethod
    def _check_revision(current: str, supplied_revision: str) -> None:
        if supplied_revision != content_revision(current):
            raise CommissioningRevisionConflict(
                "config changed after it was loaded; reload before saving"
            )

    @staticmethod
    def _motor_document(
        subsystem: SubsystemDefinition,
        requested_scope: str,
        motor: MotorDefinition | None,
        content: str,
        default_content: str,
    ) -> dict:
        return {
            "subsystem": subsystem.subsystem_id,
            "scope": "shared" if motor is None else "individual",
            "motor_id": None if motor is None else motor.motor_id,
            "content": content,
            "default_content": default_content,
            "revision": content_revision(content),
            "requested_scope": requested_scope.strip().lower(),
        }

    @staticmethod
    def _validate_soft_limits(
        content: str,
        hard_profile_path: Path,
    ) -> tuple[dict[str, float], dict[str, float], str]:
        _validate_content_size(content)
        try:
            raw_limits = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise CommissioningValidationError(
                f"invalid motor-limit YAML: {exc}"
            ) from exc
        if not isinstance(raw_limits, dict):
            raise CommissioningValidationError(
                "motor-limit config must be a YAML mapping"
            )

        unknown_fields = set(raw_limits) - set(SOFT_LIMIT_FIELDS)
        if unknown_fields:
            names = ", ".join(sorted(str(field) for field in unknown_fields))
            raise CommissioningValidationError(
                f"unknown motor-limit field(s): {names}"
            )

        try:
            hard_document = yaml.safe_load(_read_text(hard_profile_path))
            hard_group = hard_document["drivetrain"]
            profile_id = hard_document["profile_id"]
        except (KeyError, TypeError, yaml.YAMLError) as exc:
            raise CommissioningValidationError(
                f"hard drivetrain profile {hard_profile_path.name} is malformed"
            ) from exc
        if not isinstance(hard_group, dict):
            raise CommissioningValidationError(
                f"hard drivetrain profile {hard_profile_path.name} has no drivetrain mapping"
            )
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise CommissioningValidationError(
                f"hard drivetrain profile {hard_profile_path.name} has no profile_id"
            )

        values: dict[str, float] = {}
        hard_maxima: dict[str, float] = {}
        for field in SOFT_LIMIT_FIELDS:
            value = raw_limits.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CommissioningValidationError(f"{field} must be a number")
            numeric_value = float(value)
            if not math.isfinite(numeric_value) or numeric_value <= 0.0:
                raise CommissioningValidationError(
                    f"{field} must be finite and > 0"
                )

            hard_value = hard_group.get(field)
            if isinstance(hard_value, bool) or not isinstance(
                hard_value,
                (int, float),
            ):
                raise CommissioningValidationError(
                    f"hard drivetrain profile does not define numeric {field}"
                )
            numeric_hard_value = float(hard_value)
            if numeric_value > numeric_hard_value:
                raise CommissioningValidationError(
                    f"{field}={numeric_value:g} exceeds the {profile_id} "
                    f"hard limit of {numeric_hard_value:g}"
                )
            values[field] = numeric_value
            hard_maxima[field] = numeric_hard_value

        return values, hard_maxima, str(profile_id)

    @staticmethod
    def _soft_limit_document(
        subsystem: SubsystemDefinition,
        content: str,
        default_content: str,
        values: dict[str, float],
        hard_maxima: dict[str, float],
        profile_id: str,
    ) -> dict:
        return {
            "subsystem": subsystem.subsystem_id,
            "content": content,
            "default_content": default_content,
            "revision": content_revision(content),
            "values": values,
            "hard_maxima": hard_maxima,
            "drivetrain_profile": profile_id,
            "relaunch_required": True,
        }
