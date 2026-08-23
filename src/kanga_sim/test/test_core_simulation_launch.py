"""Launch the complete headless Fortress core and run its ROS contract."""

from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import launch_testing
import launch_testing.actions
import launch_testing.asserts
import pytest


@pytest.mark.launch_test
def generate_test_description():
    simulation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(
                Path(get_package_share_directory("kanga_sim"))
                / "launch"
                / "core_simulation.launch.py"
            )
        ),
        launch_arguments={
            "gui": "false",
            "use_rviz": "false",
            "world": "flat_core.sdf",
            "surface_preset": "loose_sand",
        }.items(),
    )
    contract = Node(
        package="kanga_sim",
        executable="core_simulation_contract_check",
        name="launch_contract_check",
        output="screen",
    )
    return (
        LaunchDescription(
            [simulation_launch, contract, launch_testing.actions.ReadyToTest()]
        ),
        {"contract": contract},
    )


class TestCoreSimulationContract(unittest.TestCase):
    def test_heightmap_assets_and_safe_spawn(self):
        package_share = Path(get_package_share_directory("kanga_sim"))
        launch_path = package_share / "launch" / "core_simulation.launch.py"
        spec = importlib.util.spec_from_file_location(
            "core_simulation_launch", launch_path
        )
        launch_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launch_module)

        world = package_share / "worlds" / "sand_dunes.sdf"
        self.assertEqual("0.812157", launch_module._safe_spawn_z(world, "auto"))
        self.assertEqual("1.25", launch_module._safe_spawn_z(world, "1.25"))
        self.assertTrue(
            (package_share / "worlds" / "sand_dunes_terrain.obj").is_file()
        )

        root = ET.parse(world).getroot()
        ground = root.find(".//model[@name='ground']")
        collision_mesh = ground.findtext("link/collision/geometry/mesh/uri")
        visual_mesh = ground.findtext("link/visual/geometry/mesh/uri")
        self.assertEqual("sand_dunes_terrain.obj", collision_mesh)
        self.assertEqual(collision_mesh, visual_mesh)
        self.assertEqual([], ground.findall(".//heightmap"))

    def test_contract_finishes(self, proc_info, contract):
        proc_info.assertWaitForShutdown(process=contract, timeout=45)


@launch_testing.post_shutdown_test()
class TestCoreSimulationExit(unittest.TestCase):
    def test_contract_succeeded(self, proc_info, contract):
        launch_testing.asserts.assertExitCodes(proc_info, process=contract)
