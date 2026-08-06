#!/usr/bin/env python3
"""Print changed axis and button values from ROS 2's standard /joy topic."""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


class ControllerTest(Node):
    """Display controller input changes without repeating unchanged Joy data."""

    # Create the /joy subscription and empty previous-state buffers.
    def __init__(self):
        super().__init__("controller_test")
        self.previous_axes = []
        self.previous_buttons = []
        self.joy_subscription = self.create_subscription(
            Joy, "/joy", self.on_joy, 10
        )
        self.get_logger().info("Waiting for controller data on /joy...")

    # Print only values that changed since the previous Joy message.
    def on_joy(self, message):
        if not self.previous_axes and not self.previous_buttons:
            self.get_logger().info(
                f"Controller reports {len(message.axes)} axes and "
                f"{len(message.buttons)} buttons"
            )
            self.print_initial_state(message)
        else:
            self.print_axis_changes(message.axes)
            self.print_button_changes(message.buttons)

        self.previous_axes = list(message.axes)
        self.previous_buttons = list(message.buttons)

    # Print every value in the first Joy message as the controller baseline.
    def print_initial_state(self, message):
        axes = "  ".join(
            f"axis {index}: {value:+.3f}"
            for index, value in enumerate(message.axes)
        )
        pressed_buttons = [
            str(index) for index, value in enumerate(message.buttons) if value
        ]
        print(f"Initial axes: {axes or 'none'}", flush=True)
        print(
            "Initial pressed buttons: "
            + (", ".join(pressed_buttons) if pressed_buttons else "none"),
            flush=True,
        )

    # Print axes whose values differ meaningfully from the last message.
    def print_axis_changes(self, axes):
        for index, value in enumerate(axes):
            previous_value = (
                self.previous_axes[index]
                if index < len(self.previous_axes)
                else 0.0
            )
            if abs(value - previous_value) >= 0.01:
                print(f"axis   {index:>2}: {value:+.3f}", flush=True)

    # Print button press and release transitions from the last message.
    def print_button_changes(self, buttons):
        for index, value in enumerate(buttons):
            previous_value = (
                self.previous_buttons[index]
                if index < len(self.previous_buttons)
                else 0
            )
            if value != previous_value:
                state = "PRESSED" if value else "released"
                print(f"button {index:>2}: {state}", flush=True)


# Start the monitor and treat Ctrl+C as a normal shutdown.
def main(args=None):
    rclpy.init(args=args)
    node = ControllerTest()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
