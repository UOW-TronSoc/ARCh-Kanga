"""
Launch Kanga drive ODrive nodes plus drive_manager and JointState.

CORE_DRIVE_MOTORS is the launch-time specification for all four motors. It
keeps each wheel's ROS namespace, URDF joint, CAN node ID, and direction in one
place. The nodes and their ordered parameter arrays are derived from that table.

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
)
from kanga_core_description.motor_limits import (
    DEFAULT_MOTOR_LIMITS,
    load_effective_drivetrain_configuration,
)


# One readable source for the launch-time identity of every core drive motor.
# Python preserves dictionary insertion order, which is also the order used by
# the four-field WheelVelocityCommand message: FL, BL, BR, FR.
CORE_DRIVE_MOTORS = {
    "fl": {
        "namespace": "wheel_fl",
        "joint_name": "wheel_fl_joint",
        "node_id": 1,
        "invert_direction": True,
    },
    "bl": {
        "namespace": "wheel_bl",
        "joint_name": "wheel_bl_joint",
        "node_id": 2,
        "invert_direction": True,
    },
    "br": {
        "namespace": "wheel_br",
        "joint_name": "wheel_br_joint",
        "node_id": 3,
        "invert_direction": False,
    },
    "fr": {
        "namespace": "wheel_fr",
        "joint_name": "wheel_fr_joint",
        "node_id": 4,
        "invert_direction": False,
    },
}


# Create one generic custom_odrive node from a motor specification above.
def _create_motor_node(motor_spec, defaults, can_interface):
    return Node(
        package="custom_odrive",
        executable="custom_odrive_node",
        name="can_node",
        namespace=motor_spec["namespace"],
        parameters=[
            defaults,
            {
                "node_id": motor_spec["node_id"],
                "interface": can_interface,
                "invert_direction": motor_spec["invert_direction"],
            },
        ],
        output="screen",
    )


# Load the physical profile and operating limits, then create drive-side nodes.
def _launch_setup(context):
    can_interface = LaunchConfiguration("can_interface")
    profile_ref = LaunchConfiguration("drivetrain_profile").perform(context)
    motor_limits_ref = LaunchConfiguration("motor_limits").perform(context)
    drivetrain = load_effective_drivetrain_configuration(
        profile_ref,
        motor_limits_ref,
    )

    # ROS parameters use arrays. Both arrays and the motor nodes inherit the
    # order in CORE_DRIVE_MOTORS, so their indices continue to refer to the
    # same physical wheel throughout the drive pipeline.
    wheel_ids = list(CORE_DRIVE_MOTORS.keys())
    wheel_joint_names = [
        motor_spec["joint_name"]
        for motor_spec in CORE_DRIVE_MOTORS.values()
    ]

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

    # node_id must match Fibre axis0.config.can.node_id in the corresponding
    # wheel config. Left motors are inverted so ROS-positive means forward.
    motor_nodes = []
    for motor_spec in CORE_DRIVE_MOTORS.values():
        motor_nodes.append(
            _create_motor_node(motor_spec, defaults, can_interface)
        )

    # Actuator boundary: wheel-joint rad/s from controller → motor-shaft rad/s
    # for custom_odrive, including 50:1 reduction and motor TPS limiting.
    wheel_actuator = Node(
        package="kanga_core_drive",
        executable="wheel_actuator",
        name="wheel_actuator",
        parameters=[
            drive_params,
            # The controller and drive boundary receive the same validated
            # operating limits. This node consumes the reduction and velocity.
            drivetrain.parameters,
            {
                "wheel_ids": wheel_ids,
            },
        ],
        output="screen",
    )

    # State services plus save/calibrate services for each wheel. Commissioning
    # receives the same CAN interface and validated config selected at launch.
    drive_manager = Node(
        package="kanga_core_drive",
        executable="drive_manager",
        name="drive_manager",
        parameters=[
            {
                "wheel_ids": wheel_ids,
                "can_interface": can_interface,
                "drivetrain_profile": profile_ref,
                "motor_limits": motor_limits_ref,
            },
        ],
        output="screen",
    )

    # Echo /wheel_*/controller_status → wheel_joint_states for RSP. The
    # table above explicitly maps each wheel id to its description joint.
    wheel_joint_state_publisher = Node(
        package="kanga_core_drive",
        executable="wheel_joint_state_publisher",
        name="wheel_joint_state_publisher",
        parameters=[
            drive_params,
            drivetrain.parameters,
            {
                "wheel_ids": wheel_ids,
                "joint_names": wheel_joint_names,
            },
        ],
        output="screen",
    )

    actions = [
        LogInfo(
            msg=(
                f"Drive using {drivetrain.profile.profile_id} "
                f"({drivetrain.profile.display_name}); motor limits "
                f"{drivetrain.motor_limits.motor_velocity_limit_tps:g} TPS / "
                f"{drivetrain.motor_limits.motor_acceleration_limit_tps_s:g} TPS/s"
            )
        ),
    ]
    actions.extend(motor_nodes)
    actions.extend(
        [
            wheel_actuator,
            drive_manager,
            wheel_joint_state_publisher,
        ]
    )
    return actions


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
            DeclareLaunchArgument(
                "motor_limits",
                default_value=DEFAULT_MOTOR_LIMITS,
                description="Validated operating-limit config id or YAML path",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
