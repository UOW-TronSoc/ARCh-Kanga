"""Launch the BMS node.

Launch arguments (passed on the command line):
  launch_socketcan  - if true, also start ros2_socketcan for testing
  interface        - which CAN bus (can1 or can_core); also a ROS param on the node

ROS parameters on the node (set here or left at code defaults):
  interface, req_period
  local_node_id / bms_node_id stay at node defaults (fixed for this pack)

BMS CAN bitrate must be 250000.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    interface = LaunchConfiguration('interface')
    launch_socketcan = LaunchConfiguration('launch_socketcan')

    # /can1/from_can_bus  or  /can_core/from_can_bus
    from_can_bus = PathJoinSubstitution(['', interface, 'from_can_bus'])
    to_can_bus = PathJoinSubstitution(['', interface, 'to_can_bus'])

    bridge = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('ros2_socketcan'),
                'launch',
                'socket_can_bridge.launch.xml',
            ])
        ),
        condition=IfCondition(launch_socketcan),
        launch_arguments={
            'interface': interface,
            'from_can_bus_topic': from_can_bus,
            'to_can_bus_topic': to_can_bus,
        }.items(),
    )

    bms_node = Node(
        package='kanga_core_battery',
        executable='bms_can_node',
        name='can_node',
        namespace='battery',
        parameters=[{
            'interface': interface,
            'req_period': 1,
        }],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'launch_socketcan',
            default_value='false',
            description='true = also start ros2_socketcan for solo testing',
        ),
        DeclareLaunchArgument(
            'interface',
            default_value='can1',
            description='CAN device name and Frame topic prefix (can1, can_core, ...)',
        ),
        bridge,
        bms_node,
    ])
