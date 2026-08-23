"""Compose the Kanga core Gazebo boundary in a selectable shared world."""

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import xacro


def _as_bool(context, name: str) -> bool:
    return LaunchConfiguration(name).perform(context).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_spawn_z(world: Path, requested: str, clearance: float = 0.02) -> str:
    """Resolve auto above every readable heightmap or OBJ collision mesh."""
    if requested.strip().lower() != "auto":
        return requested

    root = ET.parse(world).getroot()
    highest_surface = 0.0
    found_surface = False
    for model in root.findall(".//world/model"):
        model_pose = (model.findtext("pose") or "0 0 0 0 0 0").split()
        model_z = float(model_pose[2])
        for heightmap in model.findall(".//heightmap"):
            size = (heightmap.findtext("size") or "0 0 0").split()
            position = (heightmap.findtext("pos") or "0 0 0").split()
            highest_surface = max(
                highest_surface,
                model_z + float(position[2]) + max(0.0, float(size[2])),
            )
            found_surface = True

        for mesh in model.findall(".//collision/geometry/mesh"):
            uri = (mesh.findtext("uri") or "").strip()
            if uri.startswith("file://"):
                mesh_path = Path(uri[7:])
            else:
                mesh_path = world.parent / uri
            if mesh_path.suffix.lower() != ".obj":
                continue
            if not mesh_path.is_file():
                raise RuntimeError(f"Collision mesh not found: {mesh_path}")
            scale = [
                float(value)
                for value in (mesh.findtext("scale") or "1 1 1").split()
            ]
            mesh_max_z = None
            with mesh_path.open(encoding="ascii") as mesh_file:
                for line in mesh_file:
                    if line.startswith("v "):
                        vertex_z = float(line.split()[3]) * scale[2]
                        mesh_max_z = (
                            vertex_z
                            if mesh_max_z is None
                            else max(mesh_max_z, vertex_z)
                        )
            if mesh_max_z is not None:
                highest_surface = max(highest_surface, model_z + mesh_max_z)
                found_surface = True

    return f"{(highest_surface if found_surface else 0.0) + clearance:.6g}"


def _clear_ogre_heightmap_cache() -> int:
    """Remove Ogre1 terrain caches whose key ignores material changes."""
    cache_root = Path.home() / ".ignition" / "rendering" / "ogre-paging"
    if not cache_root.is_dir():
        return 0

    removed = 0
    for cache in cache_root.iterdir():
        if cache.is_dir() and cache.name.startswith("scene::Heightmap("):
            shutil.rmtree(cache)
            removed += 1
    return removed


def _launch_setup(context):
    sim_share = Path(get_package_share_directory("kanga_core_simulation"))
    description_share = Path(get_package_share_directory("kanga_core_description"))
    gazebo_share = Path(get_package_share_directory("ros_gz_sim"))

    world = Path(LaunchConfiguration("world").perform(context)).expanduser()
    if not world.is_absolute():
        world = Path(get_package_share_directory("kanga_sim")) / "worlds" / world
    if not world.is_file():
        raise RuntimeError(f"Gazebo world not found: {world}")

    spawn_z = _safe_spawn_z(
        world, LaunchConfiguration("spawn_z").perform(context)
    )

    world_text = world.read_text()
    has_heightmap = "<heightmap>" in world_text
    render_engine = LaunchConfiguration("render_engine").perform(context)
    if render_engine == "auto":
        # Fortress Ogre2 crashes while compiling the NVIDIA heightmap terrain
        # shader on this stack. Ogre1 supports the same SDF heightmap and keeps
        # ordinary non-heightmap worlds on the faster Ogre2 path.
        render_engine = "ogre" if has_heightmap else "ogre2"
    if render_engine not in {"ogre", "ogre2"}:
        raise RuntimeError("render_engine must be auto, ogre, or ogre2")

    cleared_heightmap_caches = 0
    if _as_bool(context, "gui") and has_heightmap and render_engine == "ogre":
        # Fortress hashes the elevation image but not its terrain material.
        # A cache generated before textures are available then stays black on
        # every later launch. These are generated files and are safe to rebuild.
        cleared_heightmap_caches = _clear_ogre_heightmap_cache()

    drivetrain_profile = LaunchConfiguration("drivetrain_profile").perform(context)
    surface_preset = LaunchConfiguration("surface_preset").perform(context)
    model = xacro.process_file(
        str(sim_share / "urdf" / "core_2026_sim.urdf.xacro"),
        mappings={
            "drivetrain_profile": drivetrain_profile,
            "surface_preset": surface_preset,
        },
    ).toxml()
    robot_description = ParameterValue(model, value_type=str)

    gz_arguments = ["-v", "3"]
    if not _as_bool(context, "paused"):
        gz_arguments.append("-r")
    if not _as_bool(context, "gui"):
        gz_arguments.append("-s")
    else:
        gz_arguments.extend(["--render-engine-gui", render_engine])
    gz_arguments.append(str(world))

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(gazebo_share / "launch" / "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": " ".join(gz_arguments)}.items(),
    )
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="simulation_clock_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        parameters=[
            {
                "qos_overrides./clock.publisher.history": "keep_last",
                "qos_overrides./clock.publisher.depth": 1,
                "qos_overrides./clock.publisher.reliability": "best_effort",
            }
        ],
        output="screen",
    )

    visualization_parameters = str(
        description_share / "config" / "visualization.yaml"
    )
    state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[
            visualization_parameters,
            {"robot_description": robot_description, "use_sim_time": True},
        ],
        output="screen",
    )
    joint_state_aggregator = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        parameters=[
            visualization_parameters,
            {
                "robot_description": robot_description,
                "source_list": [
                    "wheel_joint_states",
                    "suspension_joint_states",
                ],
                "use_sim_time": True,
            },
        ],
        output="screen",
    )
    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_kanga_core",
        arguments=[
            "-name",
            "kanga_core",
            "-topic",
            "/robot_description",
            "-x",
            LaunchConfiguration("spawn_x"),
            "-y",
            LaunchConfiguration("spawn_y"),
            "-z",
            spawn_z,
            "-R",
            LaunchConfiguration("spawn_roll"),
            "-P",
            LaunchConfiguration("spawn_pitch"),
            "-Y",
            LaunchConfiguration("spawn_yaw"),
        ],
        output="screen",
    )

    controller = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(
                Path(get_package_share_directory("kanga_core_controller"))
                / "launch"
                / "controller.launch.py"
            )
        ),
        launch_arguments={
            "drivetrain_profile": drivetrain_profile,
            "use_sim_time": "true",
        }.items(),
        condition=IfCondition(LaunchConfiguration("use_controller")),
    )
    body_pose_tf = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(
                Path(get_package_share_directory("kanga_core_microcontroller"))
                / "launch"
                / "body_pose_tf.launch.py"
            )
        ),
        launch_arguments={"use_sim_time": "true"}.items(),
    )
    suspension_state = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(
                Path(get_package_share_directory("kanga_core_microcontroller"))
                / "launch"
                / "suspension_state.launch.py"
            )
        ),
        launch_arguments={
            "drivetrain_profile": drivetrain_profile,
            "use_sim_time": "true",
        }.items(),
    )
    whs = Node(
        package="kanga_whs",
        executable="whs_node",
        name="whs_node",
        parameters=[{"use_sim_time": True}],
        condition=IfCondition(LaunchConfiguration("use_whs")),
        output="screen",
    )
    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", str(description_share / "rviz" / "core_2026.rviz")],
        parameters=[{"use_sim_time": True}],
        condition=IfCondition(LaunchConfiguration("use_rviz")),
        output="screen",
    )

    return [
        LogInfo(
            msg=(
                f"Kanga core simulation: {world.name}, {drivetrain_profile}, "
                f"surface={surface_preset}, renderer={render_engine}, "
                f"spawn_z={spawn_z}, cleared_heightmap_caches="
                f"{cleared_heightmap_caches} (starts IDLE)"
            )
        ),
        gazebo,
        clock_bridge,
        state_publisher,
        joint_state_aggregator,
        spawn,
        controller,
        body_pose_tf,
        suspension_state,
        whs,
        rviz,
    ]


def generate_launch_description():
    arguments = [
        DeclareLaunchArgument(
            "world",
            default_value="flat_core.sdf",
            description="World filename from kanga_sim/worlds or an absolute path",
        ),
        DeclareLaunchArgument(
            "gui", default_value="true", description="Start the Gazebo GUI"
        ),
        DeclareLaunchArgument(
            "render_engine",
            default_value="auto",
            description="GUI renderer: auto, ogre, or ogre2",
        ),
        DeclareLaunchArgument(
            "paused", default_value="false", description="Start Gazebo paused"
        ),
        DeclareLaunchArgument(
            "drivetrain_profile",
            default_value="drivetrain_2025",
            description="Shared physical drivetrain profile",
        ),
        DeclareLaunchArgument(
            "surface_preset",
            default_value="loose_sand",
            description="hard_ground, compacted_sand, or loose_sand",
        ),
        DeclareLaunchArgument("spawn_x", default_value="0.0"),
        DeclareLaunchArgument("spawn_y", default_value="0.0"),
        DeclareLaunchArgument(
            "spawn_z",
            default_value="auto",
            description=(
                "Base-link spawn height; auto uses 0.02 m above the world's "
                "highest heightmap surface"
            ),
        ),
        DeclareLaunchArgument("spawn_roll", default_value="0.0"),
        DeclareLaunchArgument("spawn_pitch", default_value="0.0"),
        DeclareLaunchArgument("spawn_yaw", default_value="0.0"),
        DeclareLaunchArgument(
            "use_controller",
            default_value="true",
            description="Start the unchanged shared core controller",
        ),
        DeclareLaunchArgument(
            "use_whs",
            default_value="true",
            description="Start the shared whole-robot software stop node",
        ),
        DeclareLaunchArgument(
            "use_rviz", default_value="false", description="Start RViz"
        ),
    ]
    return LaunchDescription([*arguments, OpaqueFunction(function=_launch_setup)])
