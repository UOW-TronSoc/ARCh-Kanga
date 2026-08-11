#!/usr/bin/env python3
"""Continuously publish a hardware-free differential-bar triangle wave."""

import math
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float64


class DiffBarAngleSweep(Node):
    """Sweep beta from -60 to +60 degrees and back every ten seconds."""

    LIMIT_RAD = math.radians(60.0)
    CYCLE_SECONDS = 10.0
    PUBLISH_PERIOD_SECONDS = 0.02

    def __init__(self) -> None:
        super().__init__("diff_bar_angle_sweep")
        self._publisher = self.create_publisher(
            Float64, "diff_bar_angle", qos_profile_sensor_data
        )
        self._start_time = time.monotonic()
        self._timer = self.create_timer(
            self.PUBLISH_PERIOD_SECONDS, self._publish_angle
        )
        self.get_logger().info(
            "Sweeping diff_bar_angle from -60 to +60 degrees and back "
            "every 10 seconds; press Ctrl+C to stop"
        )

    def _publish_angle(self) -> None:
        phase = ((time.monotonic() - self._start_time) % self.CYCLE_SECONDS) / (
            self.CYCLE_SECONDS
        )
        if phase < 0.5:
            angle_rad = -self.LIMIT_RAD + 4.0 * self.LIMIT_RAD * phase
        else:
            angle_rad = self.LIMIT_RAD - 4.0 * self.LIMIT_RAD * (phase - 0.5)

        message = Float64()
        message.data = angle_rad
        self._publisher.publish(message)


def main() -> None:
    rclpy.init()
    node = DiffBarAngleSweep()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
