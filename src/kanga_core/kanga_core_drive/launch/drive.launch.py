"""Launch Kanga drive ODrive nodes plus drive_manager and JointState.

Same pattern as custom_odrive example_multi_launch.py: defaults YAML + one
Node block per motor with required/override fields only. Copy a block to add
another axis; only put required fields and overrides in each dict.

Mapping (keep aligned with config/motors/ and commission_wheels):
  wheel_fl  node_id 1  invert_direction True
  wheel_bl  node_id 2  invert_direction True
  wheel_br  node_id 3
  wheel_fr  node_id 4

All share one SocketCAN interface. It defaults to can_core and can be overridden
at launch, for example: can_interface:=can0. The host must bring the interface
up first at the same bitrate as the ODrives.

Do not set start_enabled here — leave the package default. Global stop uses
/drivestop when needed. Enter CLOSED_LOOP via:
  ros2 service call /drive_manager/set_closed_loop std_srvs/srv/SetBool "{data: true}"
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from kanga_core_description.drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
    load_drivetrain_profile,
)


# Load the shared profile and create all drive-side nodes.
def _launch_setup(context):
    can_interface = LaunchConfiguration("can_interface")
    profile_ref = LaunchConfiguration("drivetrain_profile").perform(context)
    profile = load_drivetrain_profile(profile_ref)


    # Shared custom_odrive defaults (radians, idle on startup/shutdown, …).
    # Per-Node dicts below only override what differs per wheel.
    defaults = os.path.join(
        get_package_share_directory("custom_odrive"),
        "config",
        "custom_odrive_defaults.yaml",
    )
    drive_params = os.path.join(
        get_package_share_directory("kanga_core_drive"),
        "config",
        "drive.yaml",
    )

    # node_id must match Fibre axis0.config.can.node_id (wheel_* configs).
    # invert_direction: left-side mechanical mount (ROS +fw = robot forward).
    wheel_fl = Node(
        package="custom_odrive",
        executable="custom_odrive_node",
        name="can_node",
        namespace="wheel_fl",
        parameters=[
            defaults,
            {
                "node_id": 1,
                "interface": can_interface,
                "invert_direction": True,
            },
        ],
        output="screen",
    )

    wheel_bl = Node(
        package="custom_odrive",
        executable="custom_odrive_node",
        name="can_node",
        namespace="wheel_bl",
        parameters=[
            defaults,
            {
                "node_id": 2,
                "interface": can_interface,
                "invert_direction": True,
            },
        ],
        output="screen",
    )

    # No invert_direction → uses defaults (false).
    wheel_br = Node(
        package="custom_odrive",
        executable="custom_odrive_node",
        name="can_node",
        namespace="wheel_br",
        parameters=[
            defaults,
            {
                "node_id": 3,
                "interface": can_interface,
            },
        ],
        output="screen",
    )

    wheel_fr = Node(
        package="custom_odrive",
        executable="custom_odrive_node",
        name="can_node",
        namespace="wheel_fr",
        parameters=[
            defaults,
            {
                "node_id": 4,
                "interface": can_interface,
            },
        ],
        output="screen",
    )

    # Actuator boundary: wheel-joint rad/s from controller → motor-shaft rad/s
    # for custom_odrive, including 50:1 reduction and motor TPS limiting.
    wheel_actuator = Node(
        package="kanga_core_drive",
        executable="wheel_actuator",
        name="wheel_actuator",
        parameters=[
            drive_params,
            # Same shared dictionary used by controller and feedback. This node
            # only declares the reduction and motor limit that it consumes.
            profile.parameters,
            {
                "wheel_ids": ["fl", "bl", "br", "fr"],
            },
        ],
        output="screen",
    )

    # set_closed_loop + calibrate_fl/bl/br/fr; can_interface passed into
    # calibrate so Fibre uses the same bus as the nodes above.
    drive_manager = Node(
        package="kanga_core_drive",
        executable="drive_manager",
        name="drive_manager",
        parameters=[
            {
                "wheel_ids": ["fl", "bl", "br", "fr"],
                "can_interface": can_interface,
                "drivetrain_profile": profile_ref,
            },
        ],
        output="screen",
    )

    # Echo /wheel_*/controller_status → wheel_joint_states for RSP.
    # joint_names must match kanga_core_description when that lands.
    wheel_joint_state_publisher = Node(
        package="kanga_core_drive",
        executable="wheel_joint_state_publisher",
        name="wheel_joint_state_publisher",
        parameters=[
            drive_params,
            profile.parameters,
            {
                "wheel_ids": ["fl", "bl", "br", "fr"],
                "joint_names": [
                    "wheel_fl_joint",
                    "wheel_bl_joint",
                    "wheel_br_joint",
                    "wheel_fr_joint",
                ],
            },
        ],
        output="screen",
    )

    return [
        LogInfo(msg=f"Drive using {profile.profile_id} ({profile.display_name})"),
        wheel_fl,
        wheel_bl,
        wheel_br,
        wheel_fr,
        wheel_actuator,
        drive_manager,
        wheel_joint_state_publisher,
    ]


# Declare selectable CAN and drivetrain launch arguments.
def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "can_interface",
                default_value="can_core",
                description="Host SocketCAN interface shared by all wheel ODrives",
            ),
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Drivetrain profile id from kanga_core_description",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
