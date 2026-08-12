#!/usr/bin/env python3
"""Publish the bench-teleop Joy layout from a focused Qt keyboard window."""

import math
import sys
import time

import rclpy
from python_qt_binding.QtCore import Qt, QTimer
from python_qt_binding.QtGui import QFont
from python_qt_binding.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from rclpy.node import Node
from sensor_msgs.msg import Joy


AXIS_VX = 1
AXIS_VY = 0
AXIS_WZ = 3
BUTTON_CLOSED_LOOP = 0
BUTTON_DRIVESTOP = 1
BUTTON_DRIVESTOP_RELEASE = 2
BUTTON_CLEAR_ERRORS = 3
BUTTON_COMMAND_LOSS = 7
AXIS_COUNT = 8
BUTTON_COUNT = 8

MOTION_KEYS = {
    Qt.Key_W: (AXIS_VX, 1.0),
    Qt.Key_S: (AXIS_VX, -1.0),
    Qt.Key_Q: (AXIS_VY, 1.0),
    Qt.Key_E: (AXIS_VY, -1.0),
    Qt.Key_A: (AXIS_WZ, 1.0),
    Qt.Key_D: (AXIS_WZ, -1.0),
}

BUTTON_KEYS = {
    Qt.Key_I: BUTTON_CLOSED_LOOP,
    Qt.Key_X: BUTTON_DRIVESTOP,
    Qt.Key_R: BUTTON_DRIVESTOP_RELEASE,
    Qt.Key_C: BUTTON_CLEAR_ERRORS,
    Qt.Key_L: BUTTON_COMMAND_LOSS,
}

KEY_NAMES = {
    Qt.Key_W: "W",
    Qt.Key_S: "S",
    Qt.Key_Q: "Q",
    Qt.Key_E: "E",
    Qt.Key_A: "A",
    Qt.Key_D: "D",
}

HELP = """Keep this window focused while driving

W / S    forward / reverse
Q / E    strafe left / right
A / D    yaw left / right
Space    zero motion

I        toggle CLOSED_LOOP / IDLE
X        assert drivestop
R        release drivestop (remains IDLE)
C        clear drive errors
L        hold to simulate command loss
Esc      quit

Multiple motion keys may be held together.
Losing window focus immediately publishes neutral."""


def clamp(value):
    """Clamp a combined keyboard axis to the Joy percentage range."""
    return max(-1.0, min(1.0, value))


def compose_axes(keys):
    """Compose every held motion key into the eight-axis bench layout."""
    axes = [0.0] * AXIS_COUNT
    for key in keys:
        if key not in MOTION_KEYS:
            continue
        axis, value = MOTION_KEYS[key]
        axes[axis] = clamp(axes[axis] + value)
    return axes


class KeyboardJoy(Node):
    """Publish current keyboard state using the established bench Joy layout."""

    def __init__(self):
        super().__init__("keyboard_joy")
        self.declare_parameter("publish_rate_hz", 20.0)
        self.publish_rate_hz = self.get_parameter("publish_rate_hz").value
        if (
            not isinstance(self.publish_rate_hz, (float, int))
            or not math.isfinite(self.publish_rate_hz)
            or self.publish_rate_hz <= 0.0
        ):
            raise ValueError("publish_rate_hz must be finite and greater than zero")

        self.motion_keys = set()
        self.button_keys = set()
        self.publisher = self.create_publisher(Joy, "/joy", 10)
        self.get_logger().info("Keyboard Joy window ready")

    def press(self, key):
        """Record one non-repeat key press and publish it immediately."""
        if key in MOTION_KEYS:
            self.motion_keys.add(key)
        elif key in BUTTON_KEYS:
            self.button_keys.add(key)
        elif key == Qt.Key_Space:
            self.motion_keys.clear()
        else:
            return
        self.publish_joy()

    def release(self, key):
        """Record a key release and publish neutralised axes immediately."""
        if key in MOTION_KEYS:
            self.motion_keys.discard(key)
        elif key in BUTTON_KEYS:
            self.button_keys.discard(key)
        else:
            return
        self.publish_joy()

    def publish_joy(self):
        """Publish all simultaneously held motion and safety keys."""
        message = Joy()
        message.header.stamp = self.get_clock().now().to_msg()
        message.axes = compose_axes(self.motion_keys)
        message.buttons = [0] * BUTTON_COUNT

        for key in self.button_keys:
            message.buttons[BUTTON_KEYS[key]] = 1

        self.publisher.publish(message)

    def publish_neutral(self):
        """Clear every held key and publish a neutral Joy message."""
        self.motion_keys.clear()
        self.button_keys.clear()
        self.publish_joy()


class KeyboardWindow(QWidget):
    """Focusable keyboard surface with explicit key-up and focus-loss safety."""

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle("Kanga Keyboard Bench Teleop")
        self.setMinimumSize(430, 410)
        self.setFocusPolicy(Qt.StrongFocus)

        self.help_label = QLabel(HELP)
        self.help_label.setFont(QFont("monospace", 11))
        self.help_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.status_label = QLabel("FOCUSED — motion neutral")
        self.status_label.setStyleSheet(
            "font-weight: bold; padding: 8px; background: #28552b; color: white;"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.help_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
            return
        self.node.press(event.key())
        self._update_status()
        event.accept()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        self.node.release(event.key())
        self._update_status()
        event.accept()

    def focusInEvent(self, event):
        self._update_status()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.node.publish_neutral()
        self.status_label.setText("NOT FOCUSED — motion forced neutral")
        self.status_label.setStyleSheet(
            "font-weight: bold; padding: 8px; background: #8a2d2d; color: white;"
        )
        super().focusOutEvent(event)

    def closeEvent(self, event):
        self.node.publish_neutral()
        event.accept()

    def _update_status(self):
        held = [KEY_NAMES[key] for key in KEY_NAMES if key in self.node.motion_keys]
        state = "+".join(held) if held else "motion neutral"
        self.status_label.setText(f"FOCUSED — {state}")
        self.status_label.setStyleSheet(
            "font-weight: bold; padding: 8px; background: #28552b; color: white;"
        )


def main(args=None):
    rclpy.init(args=args)
    node = KeyboardJoy()
    application = QApplication([sys.argv[0]])
    window = KeyboardWindow(node)

    def spin_ros():
        if not rclpy.ok():
            application.quit()
            return
        rclpy.spin_once(node, timeout_sec=0.0)

    ros_timer = QTimer()
    ros_timer.timeout.connect(spin_ros)
    ros_timer.start(10)

    publish_timer = QTimer()
    publish_timer.timeout.connect(node.publish_joy)
    publish_timer.start(round(1000.0 / node.publish_rate_hz))

    window.show()
    window.raise_()
    window.activateWindow()
    window.setFocus(Qt.OtherFocusReason)

    try:
        application.exec_()
    finally:
        node.publish_neutral()
        # Let the separate bench node consume neutral and publish zero.
        time.sleep(0.10)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
