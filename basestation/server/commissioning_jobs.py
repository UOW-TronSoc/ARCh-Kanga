"""
Single-job coordinator for sequential motor save and calibration operations.

Save jobs run each requested motor in catalog order. Calibration jobs pause
before every motor and require a fresh confirmation before starting that one
motor. A failed motor also pauses the job so the operator can retry it, skip it
in a multi-motor sequence, or cancel the sequence. The coordinator owns the
commissioning-active interlock used by file writes and browser drive controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from typing import Any
import uuid

from .commissioning_catalog import CommissioningCatalog, MotorDefinition
from .commissioning_config import CommissioningConfigStore
from .commissioning_errors import (
    CommissioningBusy,
    CommissioningNotFound,
    CommissioningStateError,
    CommissioningValidationError,
)


# A failed job is deliberately not terminal: it remains active while waiting
# for the operator's retry, skip, or cancel decision.
TERMINAL_JOB_STATES = {"succeeded", "completed_with_skips", "cancelled"}
SUPPORTED_OPERATIONS = {"save", "calibrate"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobItem:
    """Mutable state for one motor in an ordered job."""

    motor_id: str
    label: str
    state: str = "pending"
    message: str = ""

    def public_dict(self) -> dict:
        return {
            "motor_id": self.motor_id,
            "label": self.label,
            "state": self.state,
            "message": self.message,
        }


@dataclass
class CommissioningJob:
    """Runtime-only commissioning job; jobs do not survive server restart."""

    job_id: str
    subsystem_id: str
    operation: str
    items: list[JobItem]
    state: str
    active_index: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def public_dict(self) -> dict:
        return {
            "id": self.job_id,
            "subsystem": self.subsystem_id,
            "operation": self.operation,
            "state": self.state,
            "active_index": self.active_index,
            "items": [item.public_dict() for item in self.items],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CommissioningManager:
    """Coordinate config storage, ROS operations, and the global job lock."""

    def __init__(
        self,
        catalog: CommissioningCatalog,
        config_store: CommissioningConfigStore,
        runtime: Any,
    ) -> None:
        self.catalog = catalog
        self.config_store = config_store
        self.runtime = runtime
        self._condition = threading.Condition(threading.RLock())
        self._jobs: dict[str, CommissioningJob] = {}
        self._active_job_id: str | None = None

    # ---- catalog and configuration ----

    def public_catalog(self) -> dict:
        return self.catalog.public_dict()

    def read_motor_config(self, subsystem_id: str, scope: str) -> dict:
        return self.config_store.read_motor_config(subsystem_id, scope)

    def write_motor_config(
        self,
        subsystem_id: str,
        scope: str,
        content: str,
        revision: str,
    ) -> dict:
        # Hold the same lock used by create_job so a config replacement and a
        # hardware operation can never begin between each other's checks.
        with self._condition:
            self._require_no_active_job_locked()
            return self.config_store.write_motor_config(
                subsystem_id,
                scope,
                content,
                revision,
            )

    def read_soft_limits(self, subsystem_id: str) -> dict:
        return self.config_store.read_soft_limits(subsystem_id)

    def write_soft_limits(
        self,
        subsystem_id: str,
        content: str,
        revision: str,
    ) -> dict:
        with self._condition:
            self._require_no_active_job_locked()
            return self.config_store.write_soft_limits(
                subsystem_id,
                content,
                revision,
            )

    # ---- job creation and inspection ----

    def create_job(
        self,
        subsystem_id: str,
        operation: str,
        motor_ids: list[str],
    ) -> dict:
        subsystem = self.catalog.subsystem(subsystem_id)
        subsystem.require_available()
        normalized_operation = operation.strip().lower()
        if normalized_operation not in SUPPORTED_OPERATIONS:
            raise CommissioningValidationError(
                "operation must be 'save' or 'calibrate'"
            )
        ordered_motors = self._ordered_motors(subsystem_id, motor_ids)

        worker: threading.Thread | None = None
        with self._condition:
            self._require_no_active_job_locked()
            items = [
                JobItem(motor_id=motor.motor_id, label=motor.label)
                for motor in ordered_motors
            ]
            if normalized_operation == "calibrate":
                items[0].state = "awaiting_confirmation"
                state = "awaiting_confirmation"
            else:
                state = "pending"

            job = CommissioningJob(
                job_id=uuid.uuid4().hex,
                subsystem_id=subsystem.subsystem_id,
                operation=normalized_operation,
                items=items,
                state=state,
            )
            self._jobs[job.job_id] = job
            self._active_job_id = job.job_id
            self._set_runtime_interlock_locked(True)
            self._trim_history_locked()
            self._condition.notify_all()

            if normalized_operation == "save":
                worker = threading.Thread(
                    target=self._run_save_job,
                    args=(job.job_id,),
                    name=f"commission-save-{job.job_id[:8]}",
                    daemon=True,
                )
            result = job.public_dict()

        if worker is not None:
            worker.start()
        return result

    def get_job(self, job_id: str) -> dict:
        with self._condition:
            return self._job_locked(job_id).public_dict()

    def job_active(self) -> bool:
        with self._condition:
            return self._active_job_id is not None

    # ---- operator decisions ----

    def confirm_job(self, job_id: str) -> dict:
        with self._condition:
            job = self._job_locked(job_id)
            if job.job_id != self._active_job_id:
                raise CommissioningStateError("job is no longer active")
            if job.operation != "calibrate":
                raise CommissioningStateError(
                    "only calibration jobs require free-to-spin confirmation"
                )
            if job.state != "awaiting_confirmation":
                raise CommissioningStateError(
                    f"job is {job.state}; confirmation is not currently accepted"
                )

            item = job.items[job.active_index]
            if item.state != "awaiting_confirmation":
                raise CommissioningStateError(
                    "the current motor is not awaiting confirmation"
                )
            item.state = "running"
            item.message = "confirmed motor is free to spin"
            job.state = "running"
            self._touch_locked(job)
            worker = threading.Thread(
                target=self._run_calibration_item,
                args=(job.job_id, job.active_index),
                name=f"commission-calibrate-{job.job_id[:8]}-{item.motor_id}",
                daemon=True,
            )
            result = job.public_dict()

        worker.start()
        return result

    def cancel_job(self, job_id: str) -> dict:
        with self._condition:
            job = self._job_locked(job_id)
            if job.job_id != self._active_job_id:
                raise CommissioningStateError("job is no longer active")
            if job.state not in {"awaiting_confirmation", "failed"}:
                raise CommissioningStateError(
                    "a job may only be cancelled while waiting for confirmation "
                    "or a failure decision"
                )

            first_pending_index = (
                job.active_index
                if job.state == "awaiting_confirmation"
                else job.active_index + 1
            )
            for item in job.items[first_pending_index:]:
                if item.state in {"pending", "awaiting_confirmation"}:
                    item.state = "cancelled"
                    item.message = "cancelled before motor operation"
            job.state = "cancelled"
            self._finish_job_locked(job)
            return job.public_dict()

    def retry_job(self, job_id: str) -> dict:
        """Retry the failed motor without creating a replacement job."""
        worker: threading.Thread | None = None
        with self._condition:
            job = self._active_failed_job_locked(job_id)
            item = job.items[job.active_index]

            if job.operation == "calibrate":
                # Calibration retry still requires a fresh acknowledgement
                # before the backend is allowed to release drivestop.
                item.state = "awaiting_confirmation"
                item.message = "confirm this motor is free to spin before retrying"
                job.state = "awaiting_confirmation"
            else:
                item.state = "pending"
                item.message = "retry requested"
                job.state = "pending"
                worker = self._save_worker(job)
            self._touch_locked(job)
            result = job.public_dict()

        if worker is not None:
            worker.start()
        return result

    def skip_job_item(self, job_id: str) -> dict:
        """Skip one failed motor and continue an existing multi-motor job."""
        worker: threading.Thread | None = None
        with self._condition:
            job = self._active_failed_job_locked(job_id)
            if len(job.items) == 1:
                raise CommissioningStateError(
                    "skip is only available for a multi-motor sequence"
                )

            skipped_item = job.items[job.active_index]
            failure_message = skipped_item.message.strip()
            skipped_item.state = "skipped"
            skipped_item.message = "skipped after a failed attempt"
            if failure_message:
                skipped_item.message += f": {failure_message}"
            next_index = job.active_index + 1

            if next_index >= len(job.items):
                job.state = "completed_with_skips"
                self._finish_job_locked(job)
            else:
                job.active_index = next_index
                next_item = job.items[next_index]
                if job.operation == "calibrate":
                    next_item.state = "awaiting_confirmation"
                    next_item.message = "confirm this motor is free to spin"
                    job.state = "awaiting_confirmation"
                else:
                    next_item.state = "pending"
                    next_item.message = ""
                    job.state = "pending"
                    worker = self._save_worker(job)
                self._touch_locked(job)
            result = job.public_dict()

        if worker is not None:
            worker.start()
        return result

    def wait_for_terminal(self, job_id: str, timeout_sec: float) -> dict:
        """Wait for legacy synchronous callers without blocking FastAPI's loop."""
        return self._wait_for_states(job_id, TERMINAL_JOB_STATES, timeout_sec)

    def wait_for_terminal_or_failure(
        self,
        job_id: str,
        timeout_sec: float,
    ) -> dict:
        """Let non-interactive compatibility callers observe a failed attempt."""
        return self._wait_for_states(
            job_id,
            TERMINAL_JOB_STATES | {"failed"},
            timeout_sec,
        )

    def _wait_for_states(
        self,
        job_id: str,
        states: set[str],
        timeout_sec: float,
    ) -> dict:
        deadline = time.monotonic() + timeout_sec
        with self._condition:
            while True:
                job = self._job_locked(job_id)
                if job.state in states:
                    return job.public_dict()
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    raise CommissioningStateError(
                        f"job did not finish within {timeout_sec:g} seconds"
                    )
                self._condition.wait(timeout=remaining)

    # ---- background workers ----

    def _run_save_job(self, job_id: str) -> None:
        while True:
            with self._condition:
                job = self._job_locked(job_id)
                index = job.active_index
                item = job.items[index]
                item.state = "running"
                item.message = "applying config and saving to ODrive"
                job.state = "running"
                self._touch_locked(job)
                motor_id = item.motor_id

            result = self._call_runtime("save", motor_id)

            with self._condition:
                job = self._job_locked(job_id)
                item = job.items[index]
                if not result["ok"]:
                    self._fail_job_locked(job, index, result["message"])
                    return

                item.state = "succeeded"
                item.message = result["message"]
                next_index = index + 1
                if next_index >= len(job.items):
                    job.state = self._successful_terminal_state(job)
                    self._finish_job_locked(job)
                    return

                job.active_index = next_index
                job.items[next_index].state = "pending"
                job.state = "pending"
                self._touch_locked(job)

    def _run_calibration_item(self, job_id: str, index: int) -> None:
        with self._condition:
            job = self._job_locked(job_id)
            motor_id = job.items[index].motor_id

        result = self._call_runtime("calibrate", motor_id)

        with self._condition:
            job = self._job_locked(job_id)
            item = job.items[index]
            if not result["ok"]:
                self._fail_job_locked(job, index, result["message"])
                return

            item.state = "succeeded"
            item.message = result["message"]
            next_index = index + 1
            if next_index >= len(job.items):
                job.state = self._successful_terminal_state(job)
                self._finish_job_locked(job)
                return

            job.active_index = next_index
            next_item = job.items[next_index]
            next_item.state = "awaiting_confirmation"
            next_item.message = "confirm this motor is free to spin"
            job.state = "awaiting_confirmation"
            self._touch_locked(job)

    def _call_runtime(self, operation: str, motor_id: str) -> dict:
        try:
            if operation == "save":
                result = self.runtime.save_wheel(motor_id)
            else:
                result = self.runtime.calibrate_wheel(motor_id)
        except Exception as exc:  # noqa: BLE001 - contain worker failures
            return {"ok": False, "message": f"runtime error: {exc}"}

        if not isinstance(result, dict):
            return {"ok": False, "message": "runtime returned an invalid result"}
        return {
            "ok": bool(result.get("ok")),
            "message": str(result.get("message", "")),
        }

    # ---- lock-held helpers ----

    def _ordered_motors(
        self,
        subsystem_id: str,
        motor_ids: list[str],
    ) -> list[MotorDefinition]:
        subsystem = self.catalog.subsystem(subsystem_id)
        if not motor_ids:
            raise CommissioningValidationError(
                "motor_ids must contain at least one motor"
            )

        normalized_ids = [motor_id.strip().lower() for motor_id in motor_ids]
        if len(normalized_ids) != len(set(normalized_ids)):
            raise CommissioningValidationError("motor_ids must not contain duplicates")
        for motor_id in normalized_ids:
            subsystem.motor(motor_id)

        requested = set(normalized_ids)
        # Client order is deliberately ignored. Hardware operations always use
        # the catalog's safe order, including requested subsets.
        return [motor for motor in subsystem.motors if motor.motor_id in requested]

    def _job_locked(self, job_id: str) -> CommissioningJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise CommissioningNotFound(f"unknown commissioning job {job_id!r}")
        return job

    def _require_no_active_job_locked(self) -> None:
        if self._active_job_id is not None:
            raise CommissioningBusy(
                f"commissioning job {self._active_job_id} is already active"
            )

    def _touch_locked(self, job: CommissioningJob) -> None:
        job.updated_at = _now()
        self._condition.notify_all()

    def _fail_job_locked(
        self,
        job: CommissioningJob,
        failed_index: int,
        message: str,
    ) -> None:
        failed_item = job.items[failed_index]
        failed_item.state = "failed"
        failed_item.message = message
        job.state = "failed"
        # Keep the global commissioning interlock active. The same job can now
        # be resumed, skipped, or cancelled without another job entering in
        # between the failed attempt and the operator's decision.
        self._touch_locked(job)

    def _active_failed_job_locked(self, job_id: str) -> CommissioningJob:
        job = self._job_locked(job_id)
        if job.job_id != self._active_job_id:
            raise CommissioningStateError("job is no longer active")
        if job.state != "failed":
            raise CommissioningStateError(
                f"job is {job.state}; no failed motor is awaiting a decision"
            )
        if job.items[job.active_index].state != "failed":
            raise CommissioningStateError("the active motor has not failed")
        return job

    def _save_worker(self, job: CommissioningJob) -> threading.Thread:
        return threading.Thread(
            target=self._run_save_job,
            args=(job.job_id,),
            name=f"commission-save-{job.job_id[:8]}",
            daemon=True,
        )

    @staticmethod
    def _successful_terminal_state(job: CommissioningJob) -> str:
        if any(item.state == "skipped" for item in job.items):
            return "completed_with_skips"
        return "succeeded"

    def _finish_job_locked(self, job: CommissioningJob) -> None:
        job.updated_at = _now()
        if self._active_job_id == job.job_id:
            self._active_job_id = None
            self._set_runtime_interlock_locked(False)
        self._condition.notify_all()

    def _set_runtime_interlock_locked(self, active: bool) -> None:
        setter = getattr(self.runtime, "set_commissioning_active", None)
        if callable(setter):
            setter(active)

    def _trim_history_locked(self) -> None:
        """Retain the active job plus the newest 24 completed jobs."""
        if len(self._jobs) <= 25:
            return
        completed_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job_id != self._active_job_id and job.state in TERMINAL_JOB_STATES
        ]
        while len(self._jobs) > 25 and completed_ids:
            del self._jobs[completed_ids.pop(0)]
