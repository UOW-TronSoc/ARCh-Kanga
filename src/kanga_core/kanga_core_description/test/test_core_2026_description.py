from pathlib import Path
import math
import subprocess
import xml.etree.ElementTree as ET

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = PACKAGE_ROOT / "urdf" / "core_2026.urdf.xacro"
RVIZ_CONFIG = PACKAGE_ROOT / "rviz" / "core_2026.rviz"


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


def test_wheels_are_unbounded_continuous_joints() -> None:
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
    displays = config["Visualization Manager"]["Displays"]
    robot_model = next(
        display
        for display in displays
        if display["Class"] == "rviz_default_plugins/RobotModel"
    )

    assert robot_model["Description Source"] == "Topic"
    assert robot_model["Description Topic"] == {
        "Depth": 1,
        "Durability Policy": "Transient Local",
        "History Policy": "Keep Last",
        "Reliability Policy": "Reliable",
        "Value": "/robot_description",
    }
