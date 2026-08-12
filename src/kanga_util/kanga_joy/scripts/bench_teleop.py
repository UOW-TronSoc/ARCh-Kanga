#!/usr/bin/env python3
"""Convert the bench controller mapping to Twist and drive safety commands."""

import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool
from std_srvs.srv import SetBool, Trigger


AXIS_VX_ANALOG = 1
AXIS_VY_ANALOG = 0
AXIS_WZ_ANALOG = 3
AXIS_VX_DPAD = 7
AXIS_WZ_DPAD = 6
BUTTON_CLOSED_LOOP = 0
BUTTON_DRIVESTOP = 1
BUTTON_DRIVESTOP_RELEASE = 2
BUTTON_CLEAR_ERRORS = 3
BUTTON_COMMAND_LOSS = 7
REQUIRED_AXIS_COUNT = 8
REQUIRED_BUTTON_COUNT = 8


# Limit a combined joystick percentage to the valid -1 through 1 range.
def clamp_percent(value):
    return max(-1.0, min(1.0, value))


# Read an axis safely and reject non-finite controller values.
def read_axis(axes, index):
    if index >= len(axes) or not math.isfinite(axes[index]):
        return 0.0
    return clamp_percent(axes[index])


class BenchTeleop(Node):
    """Publish bench Twist commands and handle drive-state button edges."""

    # Load limits and create the joystick, drive-state, and safety interfaces.
    def __init__(self):
        super().__init__("bench_teleop")

        self.declare_parameter("max_vx_m_s", 0.20)
        self.declare_parameter("max_vy_m_s", 0.10)
        self.declare_parameter("max_wz_rad_s", 0.30)
        self.declare_parameter("publish_rate_hz", 20.0)
        self.declare_parameter("joy_timeout_s", 0.25)
        self.declare_parameter("neutral_threshold", 0.05)

        self.max_vx_m_s = self.get_parameter("max_vx_m_s").value
        self.max_vy_m_s = self.get_parameter("max_vy_m_s").value
        self.max_wz_rad_s = self.get_parameter("max_wz_rad_s").value
        self.publish_rate_hz = self.get_parameter("publish_rate_hz").value
        self.joy_timeout_s = self.get_parameter("joy_timeout_s").value
        self.neutral_threshold = self.get_parameter("neutral_threshold").value
        self.validate_parameters()

        self.latest_percentages = (0.0, 0.0, 0.0)
        self.previous_buttons = []
        self.last_joy_time = None
        self.first_joy_received = False
        self.closed_loop_active = False
        self.closed_loop_request_pending = False
        self.clear_errors_request_pending = False
        self.motion_armed = False
        self.drivestop_active = False
        self.command_loss_active = False
        self.invalid_layout_reported = False

        drivestop_qos = QoSProfile(depth=1)
        drivestop_qos.reliability = ReliabilityPolicy.RELIABLE
        drivestop_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.velocity_publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.drivestop_publisher = self.create_publisher(
            Bool, "/drivestop", drivestop_qos
        )
        self.drivestop_subscription = self.create_subscription(
            Bool, "/drivestop", self.on_drivestop, drivestop_qos
        )
        self.joy_subscription = self.create_subscription(
            Joy, "/joy", self.on_joy, 10
        )
        self.closed_loop_client = self.create_client(
            SetBool, "/drive_manager/set_closed_loop"
        )
        self.clear_errors_client = self.create_client(
            Trigger, "/drive_manager/clear_errors"
        )
        self.publish_timer = self.create_timer(
            1.0 / self.publish_rate_hz, self.publish_velocity
        )

        self.get_logger().info(
            "Bench teleop ready: B0 state, B1 stop, B2 release, "
            "B3 clear errors, hold B7 command loss"
        )
        self.get_logger().info(
            f"Limits: vx {self.max_vx_m_s:.2f} m/s, "
            f"vy {self.max_vy_m_s:.2f} m/s, "
            f"wz {self.max_wz_rad_s:.2f} rad/s"
        )

    # Reject invalid motion, timing, and neutral-threshold parameters at startup.
    def validate_parameters(self):
        positive_parameters = {
            "max_vx_m_s": self.max_vx_m_s,
            "max_vy_m_s": self.max_vy_m_s,
            "max_wz_rad_s": self.max_wz_rad_s,
            "publish_rate_hz": self.publish_rate_hz,
            "joy_timeout_s": self.joy_timeout_s,
        }
        for name, value in positive_parameters.items():
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if value <= 0.0:
                raise ValueError(f"{name} must be greater than zero")
        if not 0.0 <= self.neutral_threshold < 1.0:
            raise ValueError("neutral_threshold must be between 0 and 1")

    # Cache percentages and process button presses on their rising edges.
    def on_joy(self, message):
        self.last_joy_time = self.get_clock().now()
        if (
            len(message.axes) < REQUIRED_AXIS_COUNT
            or len(message.buttons) < REQUIRED_BUTTON_COUNT
        ):
            self.latest_percentages = (0.0, 0.0, 0.0)
            if not self.invalid_layout_reported:
                self.get_logger().error(
                    "Controller layout must provide at least 8 axes and 8 buttons"
                )
                self.invalid_layout_reported = True
            return

        self.invalid_layout_reported = False
        self.latest_percentages = self.calculate_percentages(message.axes)
        command_loss_requested = bool(message.buttons[BUTTON_COMMAND_LOSS])

        if not self.first_joy_received:
            self.previous_buttons = list(message.buttons)
            self.command_loss_active = command_loss_requested
            self.first_joy_received = True
            return

        self.update_command_loss(command_loss_requested)
        closed_loop_pressed = self.button_rising_edge(
            message.buttons, BUTTON_CLOSED_LOOP
        )
        drivestop_pressed = self.button_rising_edge(
            message.buttons, BUTTON_DRIVESTOP
        )
        drivestop_release_pressed = self.button_rising_edge(
            message.buttons, BUTTON_DRIVESTOP_RELEASE
        )
        clear_errors_pressed = self.button_rising_edge(
            message.buttons, BUTTON_CLEAR_ERRORS
        )
        self.previous_buttons = list(message.buttons)

        # Stop always wins if conflicting buttons arrive in one Joy message.
        if drivestop_pressed:
            self.assert_drivestop()
        elif drivestop_release_pressed:
            self.release_drivestop()
        elif closed_loop_pressed:
            self.toggle_closed_loop()
        elif clear_errors_pressed:
            self.clear_all_errors()

    # Combine the analogue and D-pad mappings before applying speed limits.
    def calculate_percentages(self, axes):
        vx_percent = clamp_percent(
            read_axis(axes, AXIS_VX_ANALOG) + read_axis(axes, AXIS_VX_DPAD)
        )
        vy_percent = read_axis(axes, AXIS_VY_ANALOG)
        wz_percent = clamp_percent(
            read_axis(axes, AXIS_WZ_ANALOG) + read_axis(axes, AXIS_WZ_DPAD)
        )
        return vx_percent, vy_percent, wz_percent

    # Return true only when a button changed from released to pressed.
    def button_rising_edge(self, buttons, index):
        previous_value = (
            self.previous_buttons[index]
            if index < len(self.previous_buttons)
            else 0
        )
        return bool(buttons[index]) and not bool(previous_value)

    # Start or finish a deliberate period with no /cmd_vel publications.
    def update_command_loss(self, command_loss_requested):
        if command_loss_requested == self.command_loss_active:
            return
        self.command_loss_active = command_loss_requested
        self.motion_armed = False
        if command_loss_requested:
            self.get_logger().warning(
                "Command-loss trigger held; /cmd_vel publication stopped"
            )
        else:
            self.get_logger().info(
                "Command-loss trigger released; return axes to neutral"
            )

    # Track the latched global stop state, including messages from other nodes.
    def on_drivestop(self, message):
        self.drivestop_active = message.data
        if message.data:
            self.closed_loop_active = False
            self.motion_armed = False

    # Toggle between all-wheel CLOSED_LOOP and IDLE through drive_manager.
    def toggle_closed_loop(self):
        if self.closed_loop_request_pending:
            self.get_logger().warning("Drive-state request already in progress")
            return
        if self.drivestop_active:
            self.get_logger().warning("Release drivestop before entering CLOSED_LOOP")
            return
        if not self.closed_loop_client.service_is_ready():
            self.get_logger().error("drive_manager set_closed_loop service unavailable")
            return

        desired_closed_loop = not self.closed_loop_active
        if desired_closed_loop and not self.axes_are_neutral():
            self.get_logger().warning("Return all motion axes to neutral before arming")
            return

        if not desired_closed_loop:
            self.closed_loop_active = False
        self.motion_armed = False
        self.publish_zero()

        request = SetBool.Request()
        request.data = desired_closed_loop
        self.closed_loop_request_pending = True
        future = self.closed_loop_client.call_async(request)
        future.add_done_callback(
            lambda result: self.on_closed_loop_response(
                result, desired_closed_loop
            )
        )

    # Apply a completed drive-state response without trusting failed requests.
    def on_closed_loop_response(self, future, desired_closed_loop):
        self.closed_loop_request_pending = False
        try:
            response = future.result()
        except Exception as error:  # noqa: BLE001 - ROS futures can raise broadly.
            self.closed_loop_active = False
            self.motion_armed = False
            self.get_logger().error(f"Drive-state request failed: {error}")
            return

        if not response.success:
            self.closed_loop_active = False
            self.motion_armed = False
            self.get_logger().error(f"Drive-state rejected: {response.message}")
            return

        self.closed_loop_active = desired_closed_loop
        state = "CLOSED_LOOP" if desired_closed_loop else "IDLE"
        self.get_logger().info(f"Drive state: {state} ({response.message})")
        if desired_closed_loop:
            self.get_logger().info(
                "CLOSED_LOOP ready; return axes to neutral once to enable motion"
            )

    # Request clear_errors for every drive wheel through drive_manager.
    def clear_all_errors(self):
        if self.clear_errors_request_pending:
            self.get_logger().warning("Clear-errors request already in progress")
            return
        if not self.clear_errors_client.service_is_ready():
            self.get_logger().error("drive_manager clear_errors service unavailable")
            return

        self.clear_errors_request_pending = True
        future = self.clear_errors_client.call_async(Trigger.Request())
        future.add_done_callback(self.on_clear_errors_response)

    # Report the result of a completed all-wheel clear-errors request.
    def on_clear_errors_response(self, future):
        self.clear_errors_request_pending = False
        try:
            response = future.result()
        except Exception as error:  # noqa: BLE001 - ROS futures can raise broadly.
            self.get_logger().error(f"Clear-errors request failed: {error}")
            return

        if response.success:
            self.get_logger().info(response.message)
        else:
            self.get_logger().error(response.message)

    # Assert the global latched stop and immediately send a zero Twist.
    def assert_drivestop(self):
        self.closed_loop_active = False
        self.motion_armed = False
        self.publish_zero()
        self.drivestop_publisher.publish(Bool(data=True))
        self.get_logger().warning("DRIVESTOP asserted; all wheels requested IDLE")

    # Clear the global stop without automatically re-entering CLOSED_LOOP.
    def release_drivestop(self):
        self.closed_loop_active = False
        self.motion_armed = False
        self.publish_zero()
        self.drivestop_publisher.publish(Bool(data=False))
        self.get_logger().info("Drivestop released; press B0 to enter CLOSED_LOOP")

    # Return true when all mapped chassis percentages are near zero.
    def axes_are_neutral(self):
        return all(
            abs(value) <= self.neutral_threshold
            for value in self.latest_percentages
        )

    # Publish scaled motion while armed, otherwise publish a safe zero command.
    def publish_velocity(self):
        # Deliberately publish nothing while B7 is held to simulate command loss.
        if self.command_loss_active:
            return
        if not self.command_is_available():
            self.publish_zero()
            return

        if not self.motion_armed:
            if not self.axes_are_neutral():
                self.publish_zero()
                return
            self.motion_armed = True
            self.get_logger().info("Motion enabled")

        vx_percent, vy_percent, wz_percent = self.latest_percentages
        command = Twist()
        command.linear.x = vx_percent * self.max_vx_m_s
        command.linear.y = vy_percent * self.max_vy_m_s
        command.angular.z = wz_percent * self.max_wz_rad_s
        self.velocity_publisher.publish(command)

    # Confirm joystick data is fresh and both drive safety gates allow motion.
    def command_is_available(self):
        if (
            not self.first_joy_received
            or not self.closed_loop_active
            or self.drivestop_active
        ):
            return False
        command_age = self.get_clock().now() - self.last_joy_time
        return command_age <= Duration(seconds=self.joy_timeout_s)

    # Publish an explicit zero chassis command.
    def publish_zero(self):
        self.velocity_publisher.publish(Twist())


# Run the bench node and publish zero before a normal shutdown.
def main(args=None):
    rclpy.init(args=args)
    node = BenchTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.publish_zero()
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
