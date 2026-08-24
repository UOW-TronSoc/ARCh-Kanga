"""Single rclpy node and executor thread for the basestation server.

All ROS publishers, subscribers, and service clients live on one node
(`basestation_server`) spun by one background executor thread. FastAPI
handlers never touch rclpy directly: they write the operator's current
drive command into `CoreState`, and the node's own 20 Hz timer turns that
into `/cmd_vel` messages. Keeping all publishing on the node's thread also
gives us the dead-man for free — the same timer notices when the operator
has gone quiet and sends a stop.
"""

from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# Operator speed limits. The browser sends stick values from -1 to 1 plus a
# 0-100% speed slider; the server turns that into real-world speeds capped
# by these values. Override per machine with environment variables if needed.
MAX_LINEAR_MPS = float(os.environ.get("BASESTATION_MAX_LINEAR_MPS", "0.3"))
# Tuned so pure yaw at 90% slider reaches wheel saturation (straight already
# matched 0–90% with MAX_LINEAR_MPS; yaw was ~3× too hot at 1.0 rad/s).
MAX_YAW_RAD_S = float(os.environ.get("BASESTATION_MAX_YAW_RAD_S", "0.3"))

# How long the operator can go quiet before we send a stop. The drive stack
# has its own 0.5 s timeout below us; this fires first so the stop comes
# from the layer closest to the operator.
DEADMAN_SECONDS = 0.4

# How often telemetry is pushed to browser tabs (Hz).
TELEMETRY_HZ = float(os.environ.get("BASESTATION_TELEMETRY_HZ", "5"))

# How often the node publishes /cmd_vel while driving (and checks the dead-man).
DRIVE_TICK_SECONDS = 0.05


# ODrive axis states (custom_odrive) used when inferring closed loop from motors.
ODRIVE_AXIS_IDLE = 1
ODRIVE_AXIS_CLOSED_LOOP = 8


@dataclass
class CoreState:
    """Shared between the web handlers and the ROS thread, guarded by a lock."""

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    drivestop: Optional[bool] = None
    closed_loop: Optional[bool] = None

    # Operator's most recent drive command (normalised, not yet scaled).
    drive_x: float = 0.0        # forward/back, -1..1
    drive_yaw: float = 0.0      # turn, -1..1
    drive_scale: float = 0.0    # speed slider, 0..100
    drive_stamp: Optional[float] = None  # monotonic time of last command
    drive_active: bool = False  # True while we are publishing for the operator
    stop_requested: bool = False  # one-shot: publish a single zero and go idle

    # For /health and debugging: what actually went out on /cmd_vel last.
    last_sent_linear: float = 0.0
    last_sent_yaw: float = 0.0

    # Latest robot feedback for the telemetry WebSocket (plain dicts only).
    wheel_velocities: dict[str, Optional[float]] = field(
        default_factory=lambda: {"fl": None, "bl": None, "br": None, "fr": None}
    )
    suspension: dict[str, Optional[float]] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None
    motors: dict[str, Optional[dict[str, Any]]] = field(
        default_factory=lambda: {"fl": None, "bl": None, "br": None, "fr": None}
    )

    def snapshot(self) -> dict:
        with self.lock:
            age = None
            if self.drive_stamp is not None:
                age = round(time.monotonic() - self.drive_stamp, 3)
            return {
                "drivestop": self.drivestop,
                "drive_active": self.drive_active,
                "last_command_age_s": age,
                "last_sent": {
                    "linear_mps": round(self.last_sent_linear, 3),
                    "yaw_rad_s": round(self.last_sent_yaw, 3),
                },
            }

    def telemetry_snapshot(self) -> dict:
        """JSON-ready robot state for /ws/telemetry."""
        with self.lock:
            return {
                "t": "telemetry",
                "drivestop": self.drivestop,
                "wheels": dict(self.wheel_velocities),
                "suspension": dict(self.suspension),
                "body": self.body,
                "motors": dict(self.motors),
            }


def _speed_factor(scale_pct: float) -> float:
    """Map operator slider 0–90% → 0–100% output; 90–100% plateaus at full."""
    s = max(0.0, min(100.0, scale_pct))
    if s >= 90.0:
        return 1.0
    return s / 90.0


def _infer_closed_loop_from_motors(
    motors: dict[str, Optional[dict[str, Any]]],
) -> Optional[bool]:
    """Return closed-loop state when all four wheel axis states agree."""
    states: list[int] = []
    for wheel in ("fl", "bl", "br", "fr"):
        motor = motors.get(wheel)
        if not motor or motor.get("axis_state") is None:
            return None
        states.append(int(motor["axis_state"]))
    if all(state == ODRIVE_AXIS_CLOSED_LOOP for state in states):
        return True
    if all(state == ODRIVE_AXIS_IDLE for state in states):
        return False
    return None


def _joint_velocities(msg) -> dict[str, float]:
    """Pull name -> velocity from a JointState message."""
    out: dict[str, float] = {}
    for i, name in enumerate(msg.name):
        if i < len(msg.velocity):
            out[name] = float(msg.velocity[i])
    return out


def _wheel_short_names(joint_vel: dict[str, float]) -> dict[str, Optional[float]]:
    """Map wheel_fl_joint etc. to fl/bl/br/fr rad/s."""
    mapping = {
        "fl": "wheel_fl_joint",
        "bl": "wheel_bl_joint",
        "br": "wheel_br_joint",
        "fr": "wheel_fr_joint",
    }
    return {k: joint_vel.get(v) for k, v in mapping.items()}


def _yaw_deg_from_quat(x: float, y: float, z: float, w: float) -> float:
    siny = 2.0 * (w * z + x * y)
    cosy = 1.0 - 2.0 * (y * y + z * z)
    return math.degrees(math.atan2(siny, cosy))


class RosRuntime:
    """Owns rclpy init/shutdown, the single node, and its executor thread."""

    def __init__(self) -> None:
        self.state = CoreState()
        self.ready = False
        self.error: Optional[str] = None
        self._node = None
        self._executor = None
        self._thread: Optional[threading.Thread] = None
        self._control_lock = threading.Lock()
        self._control_held = False
        self._svc_lock = threading.Lock()

    # ---- one-shot drive management (REST) ----

    def set_drivestop(self, stop: bool) -> dict:
        """Ask WHS to assert or clear the software stop."""
        return self._call_set_bool("/whs_node/set_drivestop", stop)

    def set_closed_loop(self, enable: bool) -> dict:
        """Enter or exit closed-loop drive (wheels live)."""
        result = self._call_set_bool("/drive_manager/set_closed_loop", enable)
        if result.get("ok"):
            with self.state.lock:
                self.state.closed_loop = enable
        return result

    def clear_drive_errors(self) -> dict:
        """Clear ODrive / drive manager faults."""
        return self._call_trigger("/drive_manager/clear_errors")

    def calibrate_wheel(self, wheel: str) -> dict:
        """Run one-wheel calibration (wheel must be off the ground)."""
        wheel = wheel.lower()
        if wheel not in ("fl", "bl", "br", "fr"):
            return {"ok": False, "message": f"unknown wheel {wheel!r}"}
        return self._call_trigger(
            f"/drive_manager/calibrate_{wheel}", timeout_sec=120.0
        )

    def _call_set_bool(self, service: str, value: bool) -> dict:
        if not self.ready or self._node is None:
            return {"ok": False, "message": "ROS node not ready"}
        with self._svc_lock:
            return self._node.invoke_set_bool(service, value)

    def _call_trigger(self, service: str, timeout_sec: float = 10.0) -> dict:
        if not self.ready or self._node is None:
            return {"ok": False, "message": "ROS node not ready"}
        with self._svc_lock:
            return self._node.invoke_trigger(service, timeout_sec)

    # ---- control session (newest tab wins; see main.ws_control) ----

    def on_control_change(self, connected: bool) -> None:
        """Track whether any tab holds control; stop the rover on loss."""
        with self._control_lock:
            self._control_held = connected
        if not connected:
            # Ask the drive tick for one clean stop. This is a deliberate
            # disconnect, not a dead-man event, so it should not warn.
            with self.state.lock:
                self.state.stop_requested = True
                self.state.drive_stamp = None

    def control_held(self) -> bool:
        with self._control_lock:
            return self._control_held

    def set_drive(self, x: float, yaw: float, scale: float) -> None:
        """Store the operator's latest drive command for the ROS thread.

        Values are clamped here so nothing unreasonable can reach /cmd_vel,
        whatever the browser sends.
        """
        if not all(math.isfinite(v) for v in (x, yaw, scale)):
            return
        with self.state.lock:
            self.state.drive_x = max(-1.0, min(1.0, x))
            self.state.drive_yaw = max(-1.0, min(1.0, yaw))
            self.state.drive_scale = max(0.0, min(100.0, scale))
            self.state.drive_stamp = time.monotonic()

    def telemetry_for_browser(self) -> dict:
        """Latest robot feedback plus WHS liveness, for /ws/telemetry."""
        snap = self.state.telemetry_snapshot()
        snap["whs_online"] = self.whs_online()
        with self.state.lock:
            inferred = _infer_closed_loop_from_motors(self.state.motors)
            if inferred is not None:
                self.state.closed_loop = inferred
            snap["closed_loop"] = bool(self.state.closed_loop)
        return snap

    def whs_online(self) -> bool:
        """True when WHS stop authority appears reachable.

        A latched /drivestop value means our subscription is live even if
        DDS discovery has not yet repopulated count_publishers() after a sim
        restart.
        """
        if self._node is None:
            return False
        with self.state.lock:
            if self.state.drivestop is not None:
                return True
        if self._node.drivestop_service_ready():
            return True
        return self._node.count_publishers("/drivestop") > 0

    def start(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import (
                PoseWithCovarianceStamped,
                TwistWithCovarianceStamped,
            )
            from geometry_msgs.msg import Twist
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.node import Node
            from rclpy.qos import (
                DurabilityPolicy,
                HistoryPolicy,
                QoSProfile,
                ReliabilityPolicy,
                qos_profile_sensor_data,
            )
            from sensor_msgs.msg import JointState
            from std_msgs.msg import Bool
            from std_srvs.srv import SetBool, Trigger

            state = self.state
            sensor_qos = qos_profile_sensor_data
            status_qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
                reliability=ReliabilityPolicy.BEST_EFFORT,
            )

            class BasestationNode(Node):
                def __init__(self) -> None:
                    super().__init__("basestation_server")
                    # WHS latches /drivestop (reliable + transient_local,
                    # KeepLast(1)); matching QoS means late joiners like this
                    # server immediately receive the current stop state.
                    drivestop_qos = QoSProfile(
                        history=HistoryPolicy.KEEP_LAST,
                        depth=1,
                        reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.TRANSIENT_LOCAL,
                    )
                    self.create_subscription(
                        Bool, "/drivestop", self._on_drivestop, drivestop_qos
                    )
                    self.create_subscription(
                        JointState,
                        "/wheel_joint_states",
                        self._on_wheel_joints,
                        10,
                    )
                    self.create_subscription(
                        JointState,
                        "/suspension_joint_states",
                        self._on_suspension_joints,
                        10,
                    )
                    self.create_subscription(
                        PoseWithCovarianceStamped,
                        "/body/pose",
                        self._on_body_pose,
                        sensor_qos,
                    )
                    self.create_subscription(
                        TwistWithCovarianceStamped,
                        "/body/twist",
                        self._on_body_twist,
                        sensor_qos,
                    )
                    self._subscribe_motor_status()
                    self._cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
                    # One-shot actions the operator page triggers over REST.
                    self._clients_set_bool = {
                        "/whs_node/set_drivestop": self.create_client(
                            SetBool, "/whs_node/set_drivestop"
                        ),
                        "/drive_manager/set_closed_loop": self.create_client(
                            SetBool, "/drive_manager/set_closed_loop"
                        ),
                    }
                    self._clients_trigger = {
                        "/drive_manager/clear_errors": self.create_client(
                            Trigger, "/drive_manager/clear_errors"
                        ),
                        **{
                            f"/drive_manager/calibrate_{w}": self.create_client(
                                Trigger, f"/drive_manager/calibrate_{w}"
                            )
                            for w in ("fl", "bl", "br", "fr")
                        },
                    }
                    # One timer does both jobs: republish the operator's
                    # command while it is fresh, and stop the rover when the
                    # operator goes quiet (closed tab, frozen browser,
                    # dropped Wi-Fi — they all look like silence here).
                    self.create_timer(DRIVE_TICK_SECONDS, self._drive_tick)
                    self.get_logger().info(
                        "basestation_server ready "
                        f"(max {MAX_LINEAR_MPS} m/s, {MAX_YAW_RAD_S} rad/s, "
                        f"dead-man {DEADMAN_SECONDS}s)"
                    )

                def _on_drivestop(self, msg: Bool) -> None:
                    with state.lock:
                        state.drivestop = bool(msg.data)
                        if msg.data:
                            state.closed_loop = False

                def _on_wheel_joints(self, msg: JointState) -> None:
                    with state.lock:
                        state.wheel_velocities = _wheel_short_names(
                            _joint_velocities(msg)
                        )

                def _on_suspension_joints(self, msg: JointState) -> None:
                    with state.lock:
                        state.suspension = _joint_velocities(msg)

                def _on_body_pose(self, msg: PoseWithCovarianceStamped) -> None:
                    p = msg.pose.pose.position
                    o = msg.pose.pose.orientation
                    yaw = _yaw_deg_from_quat(o.x, o.y, o.z, o.w)
                    with state.lock:
                        prev = state.body or {}
                        state.body = {
                            **prev,
                            "x": round(p.x, 3),
                            "y": round(p.y, 3),
                            "z": round(p.z, 3),
                            "yaw_deg": round(yaw, 1),
                        }

                def _on_body_twist(self, msg: TwistWithCovarianceStamped) -> None:
                    t = msg.twist.twist
                    with state.lock:
                        prev = state.body or {}
                        state.body = {
                            **prev,
                            "vx_mps": round(t.linear.x, 3),
                            "wz_rad_s": round(t.angular.z, 3),
                        }

                def _subscribe_motor_status(self) -> None:
                    """Per-wheel ODrive feedback — physical rover only."""
                    try:
                        from custom_odrive.msg import ControllerStatus
                    except ImportError:
                        self.get_logger().info(
                            "custom_odrive not available — motor telemetry skipped"
                        )
                        return
                    wheels = ("fl", "bl", "br", "fr")
                    for wheel in wheels:
                        self.create_subscription(
                            ControllerStatus,
                            f"/wheel_{wheel}/controller_status",
                            lambda msg, w=wheel: self._on_motor_status(w, msg),
                            status_qos,
                        )

                def _on_motor_status(self, wheel: str, msg) -> None:
                    with state.lock:
                        state.motors[wheel] = {
                            "axis_state": int(msg.axis_state),
                            "vel_estimate": round(float(msg.vel_estimate), 3),
                        }

                def invoke_set_bool(self, service: str, value: bool) -> dict:
                    client = self._clients_set_bool.get(service)
                    if client is None:
                        return {"ok": False, "message": f"unknown service {service}"}
                    if not client.wait_for_service(timeout_sec=3.0):
                        return {"ok": False, "message": f"{service} not available"}
                    req = SetBool.Request()
                    req.data = value
                    resp = client.call(req)
                    if resp is None:
                        return {"ok": False, "message": f"{service} call failed"}
                    return {"ok": bool(resp.success), "message": resp.message}

                def drivestop_service_ready(self) -> bool:
                    client = self._clients_set_bool.get("/whs_node/set_drivestop")
                    return client is not None and client.service_is_ready()

                def invoke_trigger(
                    self, service: str, timeout_sec: float = 10.0
                ) -> dict:
                    client = self._clients_trigger.get(service)
                    if client is None:
                        return {"ok": False, "message": f"unknown service {service}"}
                    if not client.wait_for_service(timeout_sec=timeout_sec):
                        return {"ok": False, "message": f"{service} not available"}
                    resp = client.call(Trigger.Request())
                    if resp is None:
                        return {"ok": False, "message": f"{service} call failed"}
                    return {"ok": bool(resp.success), "message": resp.message}

                def _publish_twist(self, linear: float, yaw: float) -> None:
                    msg = Twist()
                    msg.linear.x = linear
                    msg.angular.z = yaw
                    self._cmd_vel_pub.publish(msg)
                    with state.lock:
                        state.last_sent_linear = linear
                        state.last_sent_yaw = yaw

                def _drive_tick(self) -> None:
                    with state.lock:
                        stamp = state.drive_stamp
                        x = state.drive_x
                        yaw = state.drive_yaw
                        scale = state.drive_scale
                        active = state.drive_active
                        stop_requested = state.stop_requested
                        state.stop_requested = False
                    if stop_requested:
                        self._publish_twist(0.0, 0.0)
                        with state.lock:
                            state.drive_active = False
                        self.get_logger().info(
                            "operator disconnected — published zero /cmd_vel"
                        )
                        return
                    if stamp is None:
                        return
                    fresh = (time.monotonic() - stamp) <= DEADMAN_SECONDS
                    if fresh:
                        factor = _speed_factor(scale)
                        self._publish_twist(
                            x * factor * MAX_LINEAR_MPS,
                            yaw * factor * MAX_YAW_RAD_S,
                        )
                        if not active:
                            with state.lock:
                                state.drive_active = True
                    elif active:
                        # Operator went quiet mid-drive: send one stop and
                        # go idle. The drive stack's own 0.5 s timeout backs
                        # this up if the stop message itself is lost.
                        self._publish_twist(0.0, 0.0)
                        with state.lock:
                            state.drive_active = False
                        self.get_logger().warning(
                            "dead-man: no operator command for "
                            f"{DEADMAN_SECONDS}s — published zero /cmd_vel"
                        )

            if not rclpy.ok():
                rclpy.init()
            self._node = BasestationNode()
            self._executor = SingleThreadedExecutor()
            self._executor.add_node(self._node)
            self._thread = threading.Thread(
                target=self._executor.spin, name="ros-executor", daemon=True
            )
            self._thread.start()
            self.ready = True
        except Exception as exc:  # noqa: BLE001 — server stays up; /health reports it
            self.error = str(exc)
            self.ready = False

    def stop(self) -> None:
        if self._executor is not None:
            self._executor.shutdown()
        if self._node is not None:
            self._node.destroy_node()
        try:
            import rclpy

            if rclpy.ok():
                rclpy.shutdown()
        except Exception:  # noqa: BLE001 — best-effort teardown
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.ready = False
