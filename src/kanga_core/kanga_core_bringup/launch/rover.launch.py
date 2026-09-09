"""Stable, headless production bringup for the physical Kanga rover core."""

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

from kanga_core_description.drivetrain_profile import DEFAULT_DRIVETRAIN_PROFILE  # pyright: ignore[reportMissingImports]
from kanga_core_description.motor_limits import DEFAULT_MOTOR_LIMITS  # pyright: ignore[reportMissingImports]
from kanga_core_microcontroller.core_frames import (  # pyright: ignore[reportMissingImports]
    DEFAULT_BODY_POSE_CHILD_FRAME,
    DEFAULT_BODY_POSE_PARENT_FRAME,
)


def _include(package_name, launch_file, *, arguments=None, condition=None):
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
    motor_limits = LaunchConfiguration("motor_limits")
    initial_drivestop = LaunchConfiguration("initial_drivestop")
    body_pose_parent_frame = LaunchConfiguration("body_pose_parent_frame")
    body_pose_child_frame = LaunchConfiguration("body_pose_child_frame")
    use_body_pose_tf = LaunchConfiguration("use_body_pose_tf")
    imu_frame_id = LaunchConfiguration("imu_frame_id")
    receiver_interval_sec = LaunchConfiguration("receiver_interval_sec")

    socketcan_launch = PathJoinSubstitution(
        [FindPackageShare("ros2_socketcan"), "launch", "socket_can_bridge.launch.xml"]
    )

    socketcan = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(socketcan_launch),
        launch_arguments={
            "interface": can_interface,
            "receiver_interval_sec": receiver_interval_sec,
        }.items(),
    )
    description = _include(
        "kanga_core_description",
        "view_core_2026.launch.py",
        arguments={
            "drivetrain_profile": drivetrain_profile,
            "use_joint_state_publisher": "true",
            "use_gui": "false",
            "use_rviz": "false",
            "joint_state_sources": (
                '["wheel_joint_states", "suspension_joint_states"]'
            ),
        },
    )
    whs = _include(
        "kanga_whs",
        "whs.launch.py",
        arguments={"initial_drivestop": initial_drivestop},
    )
    drive = _include(
        "kanga_core_drive",
        "drive.launch.py",
        arguments={
            "can_interface": can_interface,
            "drivetrain_profile": drivetrain_profile,
            "motor_limits": motor_limits,
        },
    )
    controller = _include(
        "kanga_core_controller",
        "controller.launch.py",
        arguments={
            "drivetrain_profile": drivetrain_profile,
            "motor_limits": motor_limits,
        },
    )
    core_can_bridge = _include(
        "kanga_core_microcontroller",
        "core_can_bridge.launch.py",
        arguments={
            "can_interface": can_interface,
            "launch_socketcan": "false",
            "body_pose_parent_frame": body_pose_parent_frame,
            "body_pose_child_frame": body_pose_child_frame,
            "imu_frame_id": imu_frame_id,
        },
    )
    suspension_state = _include(
        "kanga_core_microcontroller",
        "suspension_state.launch.py",
        arguments={"drivetrain_profile": drivetrain_profile},
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

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can_core",
                description="Host SocketCAN interface shared by the core devices",
            ),
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Core drivetrain profile from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "motor_limits",
                default_value=DEFAULT_MOTOR_LIMITS,
                description="Validated core operating-limit configuration",
            ),
            DeclareLaunchArgument(
                "initial_drivestop",
                default_value="true",
                description="Fail-safe initial WHS motion-inhibit state",
            ),
            DeclareLaunchArgument(
                "body_pose_parent_frame",
                default_value=DEFAULT_BODY_POSE_PARENT_FRAME,
                description="Non-authoritative IMU orientation TF parent",
            ),
            DeclareLaunchArgument(
                "body_pose_child_frame",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description="Non-authoritative IMU orientation TF child",
            ),
            DeclareLaunchArgument(
                "use_body_pose_tf",
                default_value="true",
                description=(
                    "Publish body_origin to base_link from the IMU; disable when "
                    "a localisation system owns the base_link parent transform"
                ),
            ),
            DeclareLaunchArgument(
                "imu_frame_id",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description="Frame stamped on imu/data; use imu_link when modelled",
            ),
            DeclareLaunchArgument(
                "receiver_interval_sec",
                default_value="0.05",
                description="SocketCAN receiver poll timeout",
            ),
            socketcan,
            description,
            whs,
            drive,
            controller,
            core_can_bridge,
            suspension_state,
            body_pose_tf,
        ]
    )
