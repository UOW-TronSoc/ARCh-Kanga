"""Broadcast already-processed ESP32 body pose as a visualization TF."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from kanga_core_microcontroller.core_frames import (
    DEFAULT_BODY_POSE_CHILD_FRAME,
    DEFAULT_BODY_POSE_PARENT_FRAME,
)


def generate_launch_description():
    body_pose_parent_frame = LaunchConfiguration("body_pose_parent_frame")
    body_pose_child_frame = LaunchConfiguration("body_pose_child_frame")
    parameters = PathJoinSubstitution(
        [
            FindPackageShare("kanga_core_microcontroller"),
            "config",
            "body_pose_tf.yaml",
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "body_pose_parent_frame",
                default_value=DEFAULT_BODY_POSE_PARENT_FRAME,
                description="Reference frame expected on body/pose",
            ),
            DeclareLaunchArgument(
                "body_pose_child_frame",
                default_value=DEFAULT_BODY_POSE_CHILD_FRAME,
                description="Body frame driven by body/pose",
            ),
            Node(
                package="kanga_core_microcontroller",
                executable="body_pose_tf_broadcaster",
                name="body_pose_tf_broadcaster",
                parameters=[
                    parameters,
                    {
                        "parent_frame_id": body_pose_parent_frame,
                        "child_frame_id": body_pose_child_frame,
                    },
                ],
                output="screen",
            ),
        ]
    )
