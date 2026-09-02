"""Start the core microcontroller CAN protocol bridge.

This is the real-rover source of `body/pose`, `body/twist`, `imu/data`, and
`diff_bar_angle`. In simulation the Gazebo core hardware plugin publishes the
same topics instead, so this node must not be started alongside it.

ros2_socketcan is optional here. In production, core bringup owns the shared
SocketCAN bridge for can_core, so leave launch_socketcan:=false and let this
node attach to the `from_can_bus` topic that bridge already publishes.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from kanga_core_microcontroller.core_frames import (
    DEFAULT_BODY_POSE_CHILD_FRAME,
    DEFAULT_BODY_POSE_PARENT_FRAME,
)


def generate_launch_description():
    can_interface = LaunchConfiguration("can_interface")
    launch_socketcan = LaunchConfiguration("launch_socketcan")
    body_pose_parent_frame = LaunchConfiguration("body_pose_parent_frame")
    body_pose_child_frame = LaunchConfiguration("body_pose_child_frame")
    imu_frame_id = LaunchConfiguration("imu_frame_id")
    receiver_interval_sec = LaunchConfiguration("receiver_interval_sec")

    socketcan_launch = PathJoinSubstitution(
        [FindPackageShare("ros2_socketcan"), "launch", "socket_can_bridge.launch.xml"]
    )
    parameters = PathJoinSubstitution(
        [
            FindPackageShare("kanga_core_microcontroller"),
            "config",
            "core_can_bridge.yaml",
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can0",
                description="Host SocketCAN interface when launch_socketcan is true",
            ),
            DeclareLaunchArgument(
                "launch_socketcan",
                default_value="false",
                description=(
                    "Start ros2_socketcan in this launch file. "
                    "Leave false when core bringup already runs the bridge."
                ),
            ),
            DeclareLaunchArgument(
                "body_pose_parent_frame",
                default_value=DEFAULT_BODY_POSE_PARENT_FRAME,
                description="Reference frame stamped on body/pose",
            ),
            DeclareLaunchArgument(
                "body_pose_child_frame",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description="Body frame stamped on body/twist",
            ),
            DeclareLaunchArgument(
                "imu_frame_id",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description=(
                    "Frame stamped on imu/data. This is independent of the "
                    "body-pose TF child so a measured imu_link can be added later"
                ),
            ),
            DeclareLaunchArgument(
                "receiver_interval_sec",
                default_value="0.05",
                description=(
                    "SocketCAN receiver poll timeout in seconds when "
                    "launch_socketcan is true"
                ),
            ),
            IncludeLaunchDescription(
                AnyLaunchDescriptionSource(socketcan_launch),
                condition=IfCondition(launch_socketcan),
                launch_arguments={
                    "interface": can_interface,
                    "receiver_interval_sec": receiver_interval_sec,
                }.items(),
            ),
            Node(
                package="kanga_core_microcontroller",
                executable="core_can_bridge",
                name="core_can_bridge",
                parameters=[
                    parameters,
                    {
                        "body_pose_frame_id": body_pose_parent_frame,
                        "body_twist_frame_id": body_pose_child_frame,
                        "imu_frame_id": imu_frame_id,
                    },
                ],
                output="screen",
            ),
        ]
    )
