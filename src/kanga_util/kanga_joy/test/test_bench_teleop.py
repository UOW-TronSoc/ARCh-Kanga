"""Integration checks for authoritative WHS routing in bench teleop."""

import importlib.util
from pathlib import Path
import threading
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool
from std_srvs.srv import SetBool


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "bench_teleop.py"
SPEC = importlib.util.spec_from_file_location("bench_teleop_under_test", SCRIPT_PATH)
BENCH_TELEOP_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH_TELEOP_MODULE)
BenchTeleop = BENCH_TELEOP_MODULE.BenchTeleop


def wait_until(predicate, timeout_s=2.0):
    """Poll a cross-thread condition until it succeeds or times out."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class FakeWhs(Node):
    """Record service requests and publish the matching authoritative state."""

    def __init__(self):
        super().__init__("fake_whs")
        qos = QoSProfile(depth=1)
        qos.reliability = ReliabilityPolicy.RELIABLE
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.publisher = self.create_publisher(Bool, "/drivestop", qos)
        self.requests = []
        self.service = self.create_service(
            SetBool, "/whs_node/set_drivestop", self.on_request
        )
        self.publisher.publish(Bool(data=True))

    def on_request(self, request, response):
        self.requests.append(request.data)
        self.publisher.publish(Bool(data=request.data))
        response.success = True
        response.message = "test state applied"
        return response


def test_bench_teleop_routes_stop_and_release_through_whs():
    rclpy.init()
    fake_whs = FakeWhs()
    teleop = BenchTeleop()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(fake_whs)
    executor.add_node(teleop)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        assert wait_until(teleop.drivestop_client.service_is_ready)
        assert wait_until(lambda: teleop.drivestop_active)
        assert not hasattr(teleop, "drivestop_publisher")

        teleop.closed_loop_active = True
        teleop.motion_armed = True
        teleop.assert_drivestop()
        assert teleop.drivestop_active
        assert not teleop.closed_loop_active
        assert not teleop.motion_armed
        assert wait_until(lambda: fake_whs.requests == [True])
        assert wait_until(lambda: not teleop.drivestop_request_pending)

        teleop.release_drivestop()
        assert not teleop.closed_loop_active
        assert not teleop.motion_armed
        assert wait_until(lambda: fake_whs.requests == [True, False])
        assert wait_until(lambda: not teleop.drivestop_active)
    finally:
        executor.shutdown()
        spin_thread.join(timeout=2.0)
        teleop.destroy_node()
        fake_whs.destroy_node()
        rclpy.shutdown()


def test_stop_disarms_locally_when_whs_is_unavailable():
    rclpy.init()
    teleop = BenchTeleop()
    try:
        teleop.drivestop_active = False
        teleop.closed_loop_active = True
        teleop.motion_armed = True
        teleop.assert_drivestop()

        assert teleop.drivestop_active
        assert not teleop.closed_loop_active
        assert not teleop.motion_armed
        assert not teleop.drivestop_request_pending
    finally:
        teleop.destroy_node()
        rclpy.shutdown()
