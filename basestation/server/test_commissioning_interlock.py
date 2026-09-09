"""Unit tests for browser-drive inhibition during commissioning."""

from __future__ import annotations

import unittest

from .ros import RosRuntime, _wait_for_ros_response


class FakeFuture:
    """Small rclpy Future stand-in for response-wait unit tests."""

    def __init__(self, *, result=None, exception=None, done=False) -> None:
        self._result = result
        self._exception = exception
        self._done = done
        self.cancelled = False
        self._callbacks = []

    def add_done_callback(self, callback) -> None:
        self._callbacks.append(callback)
        if self._done:
            callback(self)

    def done(self) -> bool:
        return self._done

    def exception(self):
        return self._exception

    def result(self):
        return self._result

    def cancel(self) -> None:
        self.cancelled = True


class FakeRosNode:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.set_bool_results: list[dict] = []
        self.trigger_result = {"ok": True, "message": "calibrated and saved br"}
        self.save_trigger_result: dict | None = None

    def invoke_set_bool(self, service: str, value: bool) -> dict:
        self.calls.append((service, value))
        if self.set_bool_results:
            return self.set_bool_results.pop(0)
        return {"ok": True, "message": "drivestop updated"}

    def invoke_trigger(self, service: str, timeout_sec: float) -> dict:
        self.calls.append((service, timeout_sec))
        if "calibrate" in service:
            return self.trigger_result
        if self.save_trigger_result is not None:
            return self.save_trigger_result
        return {"ok": True, "message": service}


class FailingExecutor:
    def spin(self) -> None:
        raise RuntimeError("timer callback failed")


class CommissioningInterlockTests(unittest.TestCase):
    def test_executor_failure_marks_runtime_degraded(self) -> None:
        runtime = RosRuntime()
        runtime._executor = FailingExecutor()
        runtime.ready = True

        runtime._spin_executor()

        self.assertFalse(runtime.ready)
        self.assertEqual(
            runtime.error,
            "ROS executor stopped: timer callback failed",
        )

    def test_completed_ros_response_is_returned(self) -> None:
        future = FakeFuture(result="response", done=True)

        self.assertEqual(_wait_for_ros_response(future, 0.01), "response")
        self.assertFalse(future.cancelled)

    def test_missing_ros_response_has_a_bounded_timeout(self) -> None:
        future = FakeFuture()

        with self.assertRaisesRegex(TimeoutError, "timed out after"):
            _wait_for_ros_response(future, 0.01)
        self.assertTrue(future.cancelled)

    def test_ros_response_exception_is_propagated(self) -> None:
        future = FakeFuture(exception=RuntimeError("DDS failure"), done=True)

        with self.assertRaisesRegex(RuntimeError, "DDS failure"):
            _wait_for_ros_response(future, 0.01)

    def test_nonzero_drive_and_drive_enables_are_rejected_while_active(self) -> None:
        runtime = RosRuntime()
        runtime.set_commissioning_active(True)

        self.assertTrue(runtime.commissioning_active())
        self.assertFalse(runtime.set_drive(1.0, 0.0, 50.0))
        self.assertEqual(
            runtime.set_closed_loop(True)["message"],
            "cannot enable closed loop during commissioning",
        )
        self.assertEqual(
            runtime.set_drivestop(False)["message"],
            "cannot release drivestop during commissioning",
        )
        self.assertEqual(
            runtime.clear_drive_errors()["message"],
            "cannot clear drive errors during commissioning",
        )

    def test_zero_drive_idle_and_stop_requests_remain_allowed(self) -> None:
        runtime = RosRuntime()
        runtime.set_commissioning_active(True)

        self.assertTrue(runtime.set_drive(0.0, 0.0, 50.0))
        # ROS is deliberately not started in this test. Reaching the ordinary
        # readiness error proves these safe-direction calls passed the interlock.
        self.assertEqual(runtime.set_closed_loop(False)["message"], "ROS node not ready")
        self.assertEqual(runtime.set_drivestop(True)["message"], "ROS node not ready")

        runtime.set_commissioning_active(False)
        self.assertFalse(runtime.commissioning_active())
        self.assertTrue(runtime.set_drive(1.0, 0.0, 50.0))

    def test_save_releases_then_reasserts_drivestop(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.save_wheel("fl")

        self.assertTrue(result["ok"])
        self.assertIn("drivestop reasserted", result["message"])
        self.assertEqual(
            fake_node.calls,
            [
                ("/whs_node/set_drivestop", False),
                ("/drive_manager/save_fl", 120.0),
                ("/whs_node/set_drivestop", True),
            ],
        )
        self.assertFalse(runtime.save_wheel("unknown")["ok"])

    def test_save_does_not_start_without_drivestop_release(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        fake_node.set_bool_results = [
            {"ok": False, "message": "WHS unavailable"},
        ]
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.save_wheel("fl")

        self.assertFalse(result["ok"])
        self.assertIn("save not started", result["message"])
        self.assertEqual(
            fake_node.calls,
            [("/whs_node/set_drivestop", False)],
        )

    def test_save_failure_still_reasserts_drivestop(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        fake_node.save_trigger_result = {
            "ok": False,
            "message": "save timed out",
        }
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.save_wheel("br")

        self.assertFalse(result["ok"])
        self.assertIn("save timed out", result["message"])
        self.assertEqual(
            fake_node.calls[-1],
            ("/whs_node/set_drivestop", True),
        )

    def test_calibration_releases_then_reasserts_drivestop(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.calibrate_wheel("br")

        self.assertTrue(result["ok"])
        self.assertIn("drivestop reasserted", result["message"])
        self.assertEqual(
            fake_node.calls,
            [
                ("/whs_node/set_drivestop", False),
                ("/drive_manager/calibrate_br", 240.0),
                ("/whs_node/set_drivestop", True),
            ],
        )

    def test_calibration_does_not_start_without_drivestop_release(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        fake_node.set_bool_results = [
            {"ok": False, "message": "WHS unavailable"},
        ]
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.calibrate_wheel("fl")

        self.assertFalse(result["ok"])
        self.assertIn("calibration not started", result["message"])
        self.assertEqual(
            fake_node.calls,
            [("/whs_node/set_drivestop", False)],
        )

    def test_calibration_failure_still_reasserts_drivestop(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        fake_node.trigger_result = {
            "ok": False,
            "message": "calibration timed out",
        }
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.calibrate_wheel("br")

        self.assertFalse(result["ok"])
        self.assertIn("calibration timed out", result["message"])
        self.assertIn("drivestop reasserted", result["message"])
        self.assertEqual(
            fake_node.calls[-1],
            ("/whs_node/set_drivestop", True),
        )

    def test_failed_drivestop_restore_is_reported_as_job_failure(self) -> None:
        runtime = RosRuntime()
        fake_node = FakeRosNode()
        fake_node.set_bool_results = [
            {"ok": True, "message": "released"},
            {"ok": False, "message": "WHS response timeout"},
        ]
        runtime._node = fake_node
        runtime.ready = True

        result = runtime.calibrate_wheel("br")

        self.assertFalse(result["ok"])
        self.assertIn("WARNING: could not reassert drivestop", result["message"])


if __name__ == "__main__":
    unittest.main()
