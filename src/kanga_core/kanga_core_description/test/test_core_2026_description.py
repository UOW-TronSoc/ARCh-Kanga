from pathlib import Path
import math
import subprocess
import xml.etree.ElementTree as ET

import pytest
import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = PACKAGE_ROOT / "urdf" / "core_2026.urdf.xacro"
RVIZ_CONFIG = PACKAGE_ROOT / "rviz" / "core_2026.rviz"
VISUALIZATION_CONFIG = PACKAGE_ROOT / "config" / "visualization.yaml"


def _expand(*mappings: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["xacro", str(DESCRIPTION), *mappings],
        check=False,
        capture_output=True,
        text=True,
    )


def test_core_2026_expands_to_expected_tree() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr

    robot = ET.fromstring(result.stdout)
    assert robot.tag == "robot"
    assert robot.attrib["name"] == "core_2026"

    links = {link.attrib["name"] for link in robot.findall("link")}
    assert links == {
        "base_link",
        "kanga_core",
        "top_payload_mount",
        "front_payload_mount",
        "left_suspension",
        "wheel_fl",
        "wheel_bl",
        "right_suspension",
        "wheel_fr",
        "wheel_br",
        "diff_bar",
    }

    joints = {
        joint.attrib["name"]: joint.attrib["type"]
        for joint in robot.findall("joint")
    }
    assert joints["wheel_fl_joint"] == "continuous"
    assert joints["wheel_bl_joint"] == "continuous"
    assert joints["wheel_br_joint"] == "continuous"
    assert joints["wheel_fr_joint"] == "continuous"
    assert joints["left_suspension_joint"] == "revolute"
    assert joints["right_suspension_joint"] == "revolute"
    assert joints["diff_bar_joint"] == "revolute"


def test_wheels_use_profile_limits_and_unbounded_continuous_position() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    for joint_name in (
        "wheel_fl_joint",
        "wheel_bl_joint",
        "wheel_br_joint",
        "wheel_fr_joint",
    ):
        joint = robot.find(f"./joint[@name='{joint_name}']")
        assert joint is not None
        assert joint.attrib["type"] == "continuous"
        limit = joint.find("limit")
        assert limit is not None
        assert "lower" not in limit.attrib
        assert "upper" not in limit.attrib
        assert float(limit.attrib["effort"]) == pytest.approx(1000.0)
        assert float(limit.attrib["velocity"]) == pytest.approx(
            22.0 * 2.0 * math.pi / 50.0
        )


def test_positive_wheel_rotation_uses_one_forward_axle_convention() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    def rotation_from_rpy(rpy: list[float]) -> list[list[float]]:
        roll, pitch, yaw = rpy
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        return [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]

    def multiply(left: list[list[float]], right: list[list[float]]):
        return [
            [sum(left[row][k] * right[k][column] for k in range(3))
             for column in range(3)]
            for row in range(3)
        ]

    rotations = {"base_link": [[1.0, 0.0, 0.0],
                               [0.0, 1.0, 0.0],
                               [0.0, 0.0, 1.0]]}
    unresolved = list(robot.findall("joint"))
    while unresolved:
        resolved_one = False
        for joint in unresolved.copy():
            parent = joint.find("parent")
            child = joint.find("child")
            assert parent is not None
            assert child is not None
            parent_name = parent.attrib["link"]
            if parent_name not in rotations:
                continue
            origin = joint.find("origin")
            rpy = [0.0, 0.0, 0.0]
            if origin is not None:
                rpy = [float(value) for value in origin.attrib["rpy"].split()]
            rotations[child.attrib["link"]] = multiply(
                rotations[parent_name], rotation_from_rpy(rpy)
            )
            unresolved.remove(joint)
            resolved_one = True
        assert resolved_one, "URDF joint tree could not be resolved"

    # The right suspension frame is mirrored relative to the left. Its wheel
    # axes therefore use the opposite local sign so all positive wheel
    # velocities resolve to the same +Y axle direction in base_link.
    for joint_name in (
        "wheel_fl_joint",
        "wheel_bl_joint",
        "wheel_br_joint",
        "wheel_fr_joint",
    ):
        joint = robot.find(f"./joint[@name='{joint_name}']")
        assert joint is not None
        axis = joint.find("axis")
        child = joint.find("child")
        assert axis is not None
        assert child is not None
        local_axis = [float(value) for value in axis.attrib["xyz"].split()]
        rotation = rotations[child.attrib["link"]]
        base_axis = [
            sum(rotation[row][column] * local_axis[column] for column in range(3))
            for row in range(3)
        ]
        assert base_axis == pytest.approx([0.0, 1.0, 0.0], abs=1e-5)


def test_articulated_suspension_has_expected_travel() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    expected_limit_rad = {
        "left_suspension_joint": math.radians(30.0),
        "right_suspension_joint": math.radians(30.0),
        "diff_bar_joint": math.radians(70.0),
    }
    for joint_name, expected_limit in expected_limit_rad.items():
        joint = robot.find(f"./joint[@name='{joint_name}']")
        assert joint is not None
        assert joint.attrib["type"] == "revolute"
        limit = joint.find("limit")
        assert limit is not None
        assert math.isclose(float(limit.attrib["lower"]), -expected_limit, abs_tol=1e-6)
        assert math.isclose(float(limit.attrib["upper"]), expected_limit, abs_tol=1e-6)


def test_core_2026_meshes_resolve_inside_package() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    package_prefix = "package://kanga_core_description/"
    meshes = robot.findall(".//mesh")
    assert meshes
    for mesh in meshes:
        uri = mesh.attrib["filename"]
        assert uri.startswith(package_prefix)
        relative_path = uri.removeprefix(package_prefix)
        assert (PACKAGE_ROOT / relative_path).is_file(), uri


def test_collision_model_uses_only_simplified_primitives() -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    def collision_shapes(link_name: str) -> list[ET.Element]:
        link = robot.find(f"./link[@name='{link_name}']")
        assert link is not None
        shapes = []
        for collision in link.findall("collision"):
            geometry = collision.find("geometry")
            assert geometry is not None
            assert len(geometry) == 1
            shapes.append(geometry[0])
        return shapes

    core_shapes = collision_shapes("kanga_core")
    assert [shape.tag for shape in core_shapes] == ["box", "box", "cylinder"]
    assert core_shapes[0].attrib["size"] == "0.683 0.3822 0.1228"
    assert core_shapes[1].attrib["size"] == "0.070 0.2583 0.1838"

    core_link = robot.find("./link[@name='kanga_core']")
    assert core_link is not None
    core_collisions = core_link.findall("collision")
    main_body_origin = core_collisions[0].find("origin")
    rear_body_origin = core_collisions[1].find("origin")
    assert main_body_origin is not None
    assert rear_body_origin is not None
    assert main_body_origin.attrib["xyz"] == "0.03833 0 0.0614"
    assert rear_body_origin.attrib["xyz"] == "-0.24116 -0.00339 0.2147"

    # The main box keeps the existing body bottom at zero; the rear box begins
    # at its top and reaches the original core-mesh maximum height.
    assert 0.0614 - 0.1228 / 2.0 == pytest.approx(0.0)
    assert 0.2147 - 0.1838 / 2.0 == pytest.approx(0.1228)
    assert 0.2147 + 0.1838 / 2.0 == pytest.approx(0.3066)

    antenna_origin = core_collisions[2].find("origin")
    antenna_cylinder = core_collisions[2].find("geometry/cylinder")
    assert antenna_origin is not None
    assert antenna_cylinder is not None
    antenna_center_z = float(antenna_origin.attrib["xyz"].split()[2])
    antenna_length = float(antenna_cylinder.attrib["length"])
    assert antenna_center_z - antenna_length / 2.0 == pytest.approx(0.0541)
    assert antenna_center_z + antenna_length / 2.0 == pytest.approx(1.1851)

    for wheel_name in ("wheel_fl", "wheel_bl", "wheel_fr", "wheel_br"):
        wheel_shapes = collision_shapes(wheel_name)
        assert [shape.tag for shape in wheel_shapes] == ["cylinder"]
        assert float(wheel_shapes[0].attrib["radius"]) == pytest.approx(0.125)
        assert float(wheel_shapes[0].attrib["length"]) == pytest.approx(0.18)

    for suspension_name in ("left_suspension", "right_suspension"):
        suspension_link = robot.find(f"./link[@name='{suspension_name}']")
        assert suspension_link is not None
        suspension_collisions = suspension_link.findall("collision")
        suspension_shapes = collision_shapes(suspension_name)
        assert [shape.tag for shape in suspension_shapes] == ["cylinder"] * 5
        radii = [float(shape.attrib["radius"]) for shape in suspension_shapes]
        assert radii == pytest.approx([0.025, 0.025, 0.026, 0.065, 0.065])

        # The two arms are straight, parallel to the suspension plane, and
        # offset from the joint frame. They must not tilt toward wheel centres.
        for arm_collision in suspension_collisions[:2]:
            origin = arm_collision.find("origin")
            assert origin is not None
            xyz = [float(value) for value in origin.attrib["xyz"].split()]
            rpy = [float(value) for value in origin.attrib["rpy"].split()]
            assert xyz[2] == pytest.approx(-0.0334)
            assert rpy[1] == pytest.approx(math.pi / 2.0, abs=1e-5)

        pivot_collision = suspension_collisions[2]
        pivot_origin = pivot_collision.find("origin")
        pivot_cylinder = pivot_collision.find("geometry/cylinder")
        assert pivot_origin is not None
        assert pivot_cylinder is not None
        assert pivot_origin.attrib["xyz"] == "0 -0.00286 0.0026"
        assert pivot_origin.attrib["rpy"] == "0 0 0"
        assert float(pivot_cylinder.attrib["radius"]) == pytest.approx(0.026)
        assert float(pivot_cylinder.attrib["length"]) == pytest.approx(0.112)

    diff_bar_shapes = collision_shapes("diff_bar")
    assert [shape.tag for shape in diff_bar_shapes] == ["box"]
    assert diff_bar_shapes[0].attrib["size"] == "0.4055 0.033 0.0625"
    assert not robot.findall(".//collision/geometry/mesh")


def test_core_2026_accepts_prefix() -> None:
    result = _expand("prefix:=test_")
    assert result.returncode == 0, result.stderr
    robot = ET.fromstring(result.stdout)

    links = {link.attrib["name"] for link in robot.findall("link")}
    joints = {joint.attrib["name"] for joint in robot.findall("joint")}
    assert "test_base_link" in links
    assert "test_wheel_fl_joint" in joints


def test_core_2026_requires_2025_drivetrain() -> None:
    result = _expand("drivetrain_profile:=drivetrain_2026")
    assert result.returncode != 0
    assert "core_2026 requires drivetrain_2025" in result.stderr


def test_core_2026_is_valid_urdf(tmp_path: Path) -> None:
    result = _expand()
    assert result.returncode == 0, result.stderr

    urdf_path = tmp_path / "core_2026.urdf"
    urdf_path.write_text(result.stdout, encoding="utf-8")
    validation = subprocess.run(
        ["check_urdf", str(urdf_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr


def test_rviz_reads_network_robot_description() -> None:
    config = yaml.safe_load(RVIZ_CONFIG.read_text(encoding="utf-8"))
    global_options = config["Visualization Manager"]["Global Options"]
    displays = config["Visualization Manager"]["Displays"]
    robot_model = next(
        display
        for display in displays
        if display["Class"] == "rviz_default_plugins/RobotModel"
    )

    assert global_options["Fixed Frame"] == "body_origin"
    assert robot_model["Description Source"] == "Topic"
    assert robot_model["Description Topic"] == {
        "Depth": 1,
        "Durability Policy": "Transient Local",
        "History Policy": "Keep Last",
        "Reliability Policy": "Reliable",
        "Value": "/robot_description",
    }


def test_visualization_pipeline_runs_at_50_hz() -> None:
    config = yaml.safe_load(VISUALIZATION_CONFIG.read_text(encoding="utf-8"))

    assert config["joint_state_publisher"]["ros__parameters"]["rate"] == 50
    assert config["robot_state_publisher"]["ros__parameters"][
        "publish_frequency"
    ] == 50.0
