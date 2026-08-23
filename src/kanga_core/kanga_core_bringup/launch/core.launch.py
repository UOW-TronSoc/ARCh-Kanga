# This unified launch is a development and testing ground. When the rover is
# production-ready, add a separate lightweight production launch instead of
# stripping the useful diagnostics and visualisation options from this file.
"""Compose the currently available physical Kanga core packages."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from kanga_core_description.drivetrain_profile import DEFAULT_DRIVETRAIN_PROFILE
from kanga_core_microcontroller.core_frames import (
    DEFAULT_BODY_POSE_CHILD_FRAME,
    DEFAULT_BODY_POSE_PARENT_FRAME,
)


def _include(package_name, launch_file, *, arguments=None, condition=None):
    """Create a compact include for one installed package launch file."""
    package_share = get_package_share_directory(package_name)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_share, "launch", launch_file)
        ),
        launch_arguments=(arguments or {}).items(),
        condition=condition,
    )


def generate_launch_description():
    can_interface = LaunchConfiguration("can_interface")
    drivetrain_profile = LaunchConfiguration("drivetrain_profile")
    use_drive = LaunchConfiguration("use_drive")
    use_whs = LaunchConfiguration("use_whs")
    initial_drivestop = LaunchConfiguration("initial_drivestop")
    use_controller = LaunchConfiguration("use_controller")
    use_suspension_state = LaunchConfiguration("use_suspension_state")
    use_body_pose_tf = LaunchConfiguration("use_body_pose_tf")
    body_pose_parent_frame = LaunchConfiguration("body_pose_parent_frame")
    body_pose_child_frame = LaunchConfiguration("body_pose_child_frame")
    use_joint_state_publisher = LaunchConfiguration("use_joint_state_publisher")
    use_gui = LaunchConfiguration("use_gui")
    use_rviz = LaunchConfiguration("use_rviz")
    use_onboard_control = LaunchConfiguration("use_onboard_control")
    device_id = LaunchConfiguration("device_id")
    joint_state_sources = LaunchConfiguration("joint_state_sources")
    launch_socketcan = LaunchConfiguration("launch_socketcan")
    use_core_can_bridge = LaunchConfiguration("use_core_can_bridge")
    receiver_interval_sec = LaunchConfiguration("receiver_interval_sec")

    socketcan_launch = PathJoinSubstitution(
        [FindPackageShare("ros2_socketcan"), "launch", "socket_can_bridge.launch.xml"]
    )

    description = _include(
        "kanga_core_description",
        "view_core_2026.launch.py",
        arguments={
            "drivetrain_profile": drivetrain_profile,
            "use_joint_state_publisher": use_joint_state_publisher,
            "use_gui": use_gui,
            "use_rviz": use_rviz,
            "joint_state_sources": joint_state_sources,
        },
    )

    drive = _include(
        "kanga_core_drive",
        "drive.launch.py",
        arguments={
            "can_interface": can_interface,
            "drivetrain_profile": drivetrain_profile,
        },
        condition=IfCondition(use_drive),
    )

    whs = _include(
        "kanga_whs",
        "whs.launch.py",
        arguments={"initial_drivestop": initial_drivestop},
        condition=IfCondition(use_whs),
    )

    controller = _include(
        "kanga_core_controller",
        "controller.launch.py",
        arguments={"drivetrain_profile": drivetrain_profile},
        condition=IfCondition(use_controller),
    )

    suspension_state = _include(
        "kanga_core_microcontroller",
        "suspension_state.launch.py",
        arguments={"drivetrain_profile": drivetrain_profile},
        condition=IfCondition(use_suspension_state),
    )

    body_pose_tf = _include(
        "kanga_core_microcontroller",
        "body_pose_tf.launch.py",
        arguments={
            "body_pose_parent_frame": body_pose_parent_frame,
            "body_pose_child_frame": body_pose_child_frame,
        },
        condition=IfCondition(use_body_pose_tf),
    )

    core_can_bridge = _include(
        "kanga_core_microcontroller",
        "core_can_bridge.launch.py",
        arguments={
            "launch_socketcan": "false",
            "body_pose_parent_frame": body_pose_parent_frame,
            "body_pose_child_frame": body_pose_child_frame,
        },
        condition=IfCondition(use_core_can_bridge),
    )

    socketcan = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(socketcan_launch),
        condition=IfCondition(launch_socketcan),
        launch_arguments={
            "interface": can_interface,
            "receiver_interval_sec": receiver_interval_sec,
        }.items(),
    )

    # Temporary local-control implementation until kanga_onboard_control gains
    # its production launch. This is deliberately disabled by default.
    onboard_control = _include(
        "kanga_joy",
        "bench_teleop.launch.py",
        arguments={"device_id": device_id},
        condition=IfCondition(use_onboard_control),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can_core",
                description="Host SocketCAN interface used by the core ODrives",
            ),
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Core drivetrain profile from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "use_drive",
                default_value="true",
                description="Start the physical ODrive stack and drive manager",
            ),
            DeclareLaunchArgument(
                "use_whs",
                default_value="true",
                description="Start the sole software /drivestop authority",
            ),
            DeclareLaunchArgument(
                "initial_drivestop",
                default_value="true",
                description=(
                    "Initial WHS state. Keep true for fail-safe physical bringup."
                ),
            ),
            DeclareLaunchArgument(
                "use_controller",
                default_value="true",
                description="Start the /cmd_vel to wheel-command controller",
            ),
            DeclareLaunchArgument(
                "use_suspension_state",
                default_value="true",
                description="Start differential-bar suspension state mapping",
            ),
            DeclareLaunchArgument(
                "use_body_pose_tf",
                default_value="false",
                description="Broadcast body/pose as a visualization transform",
            ),
            DeclareLaunchArgument(
                "body_pose_parent_frame",
                default_value=DEFAULT_BODY_POSE_PARENT_FRAME,
                description="Reference frame stamped on body/pose and TF parent",
            ),
            DeclareLaunchArgument(
                "body_pose_child_frame",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description="Body frame for twist, IMU, and the body/pose TF child",
            ),
            DeclareLaunchArgument(
                "use_joint_state_publisher",
                default_value="false",
                description=(
                    "Merge wheel and suspension state topics into /joint_states"
                ),
            ),
            DeclareLaunchArgument(
                "use_gui",
                default_value="false",
                description=(
                    "Use joint-state sliders; ignored unless "
                    "use_joint_state_publisher is true"
                ),
            ),
            DeclareLaunchArgument(
                "joint_state_sources",
                default_value=(
                    '["wheel_joint_states", "suspension_joint_states"]'
                ),
                description="JointState topics merged into /joint_states",
            ),
            DeclareLaunchArgument(
                "use_rviz",
                default_value="false",
                description="Start RViz with the core_2026 configuration",
            ),
            DeclareLaunchArgument(
                "use_onboard_control",
                default_value="false",
                description="Start the provisional local gamepad control path",
            ),
            DeclareLaunchArgument(
                "device_id",
                default_value="0",
                description="SDL game-controller index for onboard control",
            ),
            DeclareLaunchArgument(
                "launch_socketcan",
                default_value="true",
                description=(
                    "Start the shared ros2_socketcan bridge on can_interface. "
                    "Core CAN consumers (microcontroller bridge, BMS) subscribe "
                    "to from_can_bus / to_can_bus."
                ),
            ),
            DeclareLaunchArgument(
                "use_core_can_bridge",
                default_value="true",
                description="Start the ESP32 core CAN protocol bridge node",
            ),
            DeclareLaunchArgument(
                "receiver_interval_sec",
                default_value="0.05",
                description=(
                    "SocketCAN receiver poll timeout in seconds. ESP32 telemetry "
                    "arrives in ~20 ms bursts, so 0.05 avoids spurious timeouts."
                ),
            ),
            socketcan,
            description,
            whs,
            drive,
            controller,
            suspension_state,
            body_pose_tf,
            core_can_bridge,
            onboard_control,
        ]
    )
