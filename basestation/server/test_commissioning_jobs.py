"""Offline state-machine tests for sequential commissioning jobs."""

from __future__ import annotations

import threading
import time
import unittest

from .commissioning_catalog import build_commissioning_catalog
from .commissioning_errors import (
    CommissioningBusy,
    CommissioningNotFound,
    CommissioningStateError,
    CommissioningValidationError,
)
from .commissioning_jobs import CommissioningManager


class FakeConfigStore:
    def __init__(self) -> None:
        self.writes: list[tuple] = []

    def write_motor_config(self, *arguments):
        self.writes.append(arguments)
        return {"saved": True}

    def write_soft_limits(self, *arguments):
        self.writes.append(arguments)
        return {"saved": True}


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.interlocks: list[bool] = []
        self.results: dict[tuple[str, str], dict] = {}
        self.block = threading.Event()
        self.release = threading.Event()

    def set_commissioning_active(self, active: bool) -> None:
        self.interlocks.append(active)

    def save_wheel(self, motor_id: str) -> dict:
        return self._operate("save", motor_id)

    def calibrate_wheel(self, motor_id: str) -> dict:
        return self._operate("calibrate", motor_id)

    def _operate(self, operation: str, motor_id: str) -> dict:
        self.calls.append((operation, motor_id))
        if self.block.is_set():
            self.release.wait(timeout=2.0)
        return self.results.get(
            (operation, motor_id),
            {"ok": True, "message": f"{operation}d {motor_id}"},
        )


def wait_for_state(
    manager: CommissioningManager,
    job_id: str,
    expected_state: str,
    timeout_sec: float = 2.0,
) -> dict:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        job = manager.get_job(job_id)
        if job["state"] == expected_state:
            return job
        time.sleep(0.005)
    raise AssertionError(
        f"job {job_id} did not reach {expected_state}; last state was {job['state']}"
    )


class CommissioningJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = FakeRuntime()
        self.store = FakeConfigStore()
        self.manager = CommissioningManager(
            build_commissioning_catalog(),
            self.store,
            self.runtime,
        )

    def test_save_subset_runs_sequentially_in_catalog_order(self) -> None:
        created = self.manager.create_job("core", "save", ["fr", "fl", "br"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)

        self.assertEqual(
            self.runtime.calls,
            [("save", "fl"), ("save", "br"), ("save", "fr")],
        )
        self.assertEqual(terminal["state"], "succeeded")
        self.assertEqual(
            [item["state"] for item in terminal["items"]],
            ["succeeded", "succeeded", "succeeded"],
        )
        self.assertEqual(self.runtime.interlocks, [True, False])

    def test_failed_save_waits_for_operator_and_can_be_retried(self) -> None:
        self.runtime.results[("save", "bl")] = {
            "ok": False,
            "message": "ODrive unavailable",
        }
        created = self.manager.create_job(
            "core",
            "save",
            ["fl", "bl", "br", "fr"],
        )
        failed = wait_for_state(self.manager, created["id"], "failed")

        self.assertEqual(self.runtime.calls, [("save", "fl"), ("save", "bl")])
        self.assertEqual(
            [item["state"] for item in failed["items"]],
            ["succeeded", "failed", "pending", "pending"],
        )
        self.assertTrue(self.manager.job_active())
        self.assertEqual(self.runtime.interlocks, [True])

        self.runtime.results[("save", "bl")] = {
            "ok": True,
            "message": "saved bl on retry",
        }
        self.manager.retry_job(created["id"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)

        self.assertEqual(
            self.runtime.calls,
            [
                ("save", "fl"),
                ("save", "bl"),
                ("save", "bl"),
                ("save", "br"),
                ("save", "fr"),
            ],
        )
        self.assertEqual(terminal["state"], "succeeded")
        self.assertEqual(self.runtime.interlocks, [True, False])

    def test_failed_save_can_be_skipped_and_sequence_continues(self) -> None:
        self.runtime.results[("save", "bl")] = {
            "ok": False,
            "message": "ODrive unavailable",
        }
        created = self.manager.create_job("core", "save", ["fl", "bl", "br"])
        wait_for_state(self.manager, created["id"], "failed")

        self.manager.skip_job_item(created["id"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)

        self.assertEqual(
            self.runtime.calls,
            [("save", "fl"), ("save", "bl"), ("save", "br")],
        )
        self.assertEqual(terminal["state"], "completed_with_skips")
        self.assertEqual(
            [item["state"] for item in terminal["items"]],
            ["succeeded", "skipped", "succeeded"],
        )
        self.assertEqual(
            terminal["items"][1]["message"],
            "skipped after a failed attempt: ODrive unavailable",
        )

    def test_calibration_requires_fresh_confirmation_for_every_motor(self) -> None:
        created = self.manager.create_job("core", "calibrate", ["br", "fl"])
        self.assertEqual(created["state"], "awaiting_confirmation")
        self.assertEqual(self.runtime.calls, [])

        self.manager.confirm_job(created["id"])
        waiting_for_br = wait_for_state(
            self.manager,
            created["id"],
            "awaiting_confirmation",
        )
        self.assertEqual(self.runtime.calls, [("calibrate", "fl")])
        self.assertEqual(waiting_for_br["items"][1]["motor_id"], "br")
        self.assertEqual(waiting_for_br["items"][1]["state"], "awaiting_confirmation")

        self.manager.confirm_job(created["id"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)
        self.assertEqual(
            self.runtime.calls,
            [("calibrate", "fl"), ("calibrate", "br")],
        )
        self.assertEqual(terminal["state"], "succeeded")
        self.assertEqual(self.runtime.interlocks, [True, False])

    def test_waiting_calibration_can_be_cancelled(self) -> None:
        created = self.manager.create_job("core", "calibrate", ["fl", "bl"])
        cancelled = self.manager.cancel_job(created["id"])

        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(
            [item["state"] for item in cancelled["items"]],
            ["cancelled", "cancelled"],
        )
        self.assertFalse(self.manager.job_active())
        self.assertEqual(self.runtime.calls, [])

    def test_failed_calibration_retry_requires_new_confirmation(self) -> None:
        self.runtime.results[("calibrate", "fl")] = {
            "ok": False,
            "message": "calibration current too low",
        }
        created = self.manager.create_job("core", "calibrate", ["fl", "bl"])
        self.manager.confirm_job(created["id"])
        wait_for_state(self.manager, created["id"], "failed")

        retrying = self.manager.retry_job(created["id"])
        self.assertEqual(retrying["state"], "awaiting_confirmation")
        self.assertEqual(len(self.runtime.calls), 1)

        self.runtime.results[("calibrate", "fl")] = {
            "ok": True,
            "message": "calibrated fl on retry",
        }
        self.manager.confirm_job(created["id"])
        waiting_for_bl = wait_for_state(
            self.manager,
            created["id"],
            "awaiting_confirmation",
        )
        self.assertEqual(waiting_for_bl["active_index"], 1)
        self.assertEqual(
            self.runtime.calls,
            [("calibrate", "fl"), ("calibrate", "fl")],
        )

        self.manager.confirm_job(created["id"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)
        self.assertEqual(terminal["state"], "succeeded")

    def test_skipped_calibration_advances_to_next_confirmation(self) -> None:
        self.runtime.results[("calibrate", "fl")] = {
            "ok": False,
            "message": "encoder unavailable",
        }
        created = self.manager.create_job("core", "calibrate", ["fl", "bl"])
        self.manager.confirm_job(created["id"])
        wait_for_state(self.manager, created["id"], "failed")

        waiting_for_bl = self.manager.skip_job_item(created["id"])

        self.assertEqual(waiting_for_bl["state"], "awaiting_confirmation")
        self.assertEqual(waiting_for_bl["active_index"], 1)
        self.assertEqual(waiting_for_bl["items"][0]["state"], "skipped")
        self.assertEqual(
            waiting_for_bl["items"][0]["message"],
            "skipped after a failed attempt: encoder unavailable",
        )
        self.assertEqual(len(self.runtime.calls), 1)

        self.manager.confirm_job(created["id"])
        terminal = self.manager.wait_for_terminal(created["id"], 2.0)
        self.assertEqual(terminal["state"], "completed_with_skips")
        self.assertEqual(
            self.runtime.calls,
            [("calibrate", "fl"), ("calibrate", "bl")],
        )

    def test_failed_sequence_can_be_cancelled(self) -> None:
        self.runtime.results[("save", "fl")] = {
            "ok": False,
            "message": "ODrive unavailable",
        }
        created = self.manager.create_job("core", "save", ["fl", "bl"])
        wait_for_state(self.manager, created["id"], "failed")

        cancelled = self.manager.cancel_job(created["id"])

        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(
            [item["state"] for item in cancelled["items"]],
            ["failed", "cancelled"],
        )
        self.assertEqual(self.runtime.interlocks, [True, False])

    def test_single_motor_failure_cannot_be_skipped(self) -> None:
        self.runtime.results[("save", "fl")] = {
            "ok": False,
            "message": "ODrive unavailable",
        }
        created = self.manager.create_job("core", "save", ["fl"])
        wait_for_state(self.manager, created["id"], "failed")

        with self.assertRaises(CommissioningStateError):
            self.manager.skip_job_item(created["id"])
        self.manager.cancel_job(created["id"])

    def test_running_job_blocks_other_jobs_and_config_writes(self) -> None:
        self.runtime.block.set()
        created = self.manager.create_job("core", "save", ["fl"])
        wait_for_state(self.manager, created["id"], "running")

        with self.assertRaises(CommissioningBusy):
            self.manager.create_job("core", "save", ["bl"])
        with self.assertRaises(CommissioningBusy):
            self.manager.write_motor_config("core", "shared", "text", "revision")
        with self.assertRaises(CommissioningBusy):
            self.manager.write_soft_limits("core", "text", "revision")

        self.runtime.release.set()
        self.manager.wait_for_terminal(created["id"], 2.0)

    def test_confirmation_is_rejected_while_motor_is_running(self) -> None:
        self.runtime.block.set()
        created = self.manager.create_job("core", "calibrate", ["fl"])
        self.manager.confirm_job(created["id"])
        wait_for_state(self.manager, created["id"], "running")

        with self.assertRaises(CommissioningStateError):
            self.manager.confirm_job(created["id"])
        with self.assertRaises(CommissioningStateError):
            self.manager.cancel_job(created["id"])

        self.runtime.release.set()
        self.manager.wait_for_terminal(created["id"], 2.0)

    def test_invalid_motor_lists_are_rejected_before_interlock(self) -> None:
        invalid_lists = (
            ([], CommissioningValidationError),
            (["fl", "fl"], CommissioningValidationError),
            (["unknown"], CommissioningNotFound),
        )
        for motor_ids, expected_error in invalid_lists:
            with self.subTest(motor_ids=motor_ids):
                with self.assertRaises(expected_error):
                    self.manager.create_job("core", "save", motor_ids)
        self.assertEqual(self.runtime.interlocks, [])


if __name__ == "__main__":
    unittest.main()
