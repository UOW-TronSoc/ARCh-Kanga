"""Fixed launch allowlist owned by the onboard runtime.

Add one ``LaunchProfile`` here when a subsystem gains a reviewed production
launch file. Do not accept commands or launch arguments from service callers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchProfile:
    system_id: str
    label: str
    command: tuple[str, ...]
    sentinel_nodes: frozenset[str]


CORE_PROFILE = LaunchProfile(
    system_id="core",
    label="Core Rover",
    command=(
        "ros2",
        "launch",
        "kanga_core_bringup",
        "rover.launch.py",
        "can_interface:=can_core",
        "drivetrain_profile:=drivetrain_2025",
        "motor_limits:=core",
        "initial_drivestop:=true",
        "body_pose_parent_frame:=body_origin",
        "body_pose_child_frame:=base_link",
        "imu_frame_id:=base_link",
    ),
    sentinel_nodes=frozenset(
        {
            "/whs_node",
            "/drive_manager",
            "/wheel_command_mapper",
            "/core_can_bridge",
            "/suspension_joint_state_publisher",
            "/body_pose_tf_broadcaster",
        }
    ),
)

CORE_SIM_PROFILE = LaunchProfile(
    system_id="core_sim",
    label="Core Simulation",
    command=(
        "ros2",
        "launch",
        "kanga_sim",
        "core_simulation.launch.py",
        "world:=sand_dunes.sdf",
    ),
    sentinel_nodes=frozenset(
        {
            "/simulation_clock_bridge",
            "/whs_node",
            "/suspension_joint_state_publisher",
            "/body_pose_tf_broadcaster",
        }
    ),
)


# This tuple is the complete production allowlist. The manager and ROS service
# boundary are generic and should not need changing when another profile lands.
PROFILES = (CORE_PROFILE, CORE_SIM_PROFILE)
