"""Start drivetrain-profiled differential-bar suspension state mapping."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from kanga_core_description.drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
    load_drivetrain_profile,
)


def _launch_setup(context):
    profile_ref = LaunchConfiguration("drivetrain_profile").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time")
    profile = load_drivetrain_profile(profile_ref)
    parameters = PathJoinSubstitution(
        [
            FindPackageShare("kanga_core_microcontroller"),
            "config",
            "suspension_state.yaml",
        ]
    )

    return [
        LogInfo(
            msg=(
                f"Suspension using {profile.profile_id} "
                f"({profile.display_name})"
            )
        ),
        Node(
            package="kanga_core_microcontroller",
            executable="suspension_joint_state_publisher",
            name="suspension_joint_state_publisher",
            parameters=[
                parameters,
                profile.parameters,
                {"use_sim_time": use_sim_time},
            ],
            output="screen",
        ),
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "drivetrain_profile",
                default_value=DEFAULT_DRIVETRAIN_PROFILE,
                description="Drivetrain profile id from kanga_core_description",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="false",
                description="Use the ROS simulation clock",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
