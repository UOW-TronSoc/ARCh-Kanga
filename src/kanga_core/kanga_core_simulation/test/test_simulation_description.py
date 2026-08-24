"""Contract checks for the generated simulation model."""

from pathlib import Path
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
import pytest
import xacro


WHEEL_JOINTS = [
    "wheel_fl_joint",
    "wheel_bl_joint",
    "wheel_br_joint",
    "wheel_fr_joint",
]
PASSIVE_JOINTS = [
    "diff_bar_joint",
    "left_suspension_joint",
    "right_suspension_joint",
]


def generate(surface: str = "loose_sand") -> ET.Element:
    package_share = Path(get_package_share_directory("kanga_core_simulation"))
    document = xacro.process_file(
        str(package_share / "urdf" / "core_2026_sim.urdf.xacro"),
        mappings={
            "drivetrain_profile": "drivetrain_2025",
            "surface_preset": surface,
        },
    )
    return ET.fromstring(document.toxml())


def test_joint_contract_and_nonzero_passive_limits():
    root = generate()
    joints = {joint.attrib["name"]: joint for joint in root.findall("joint")}
    assert all(name in joints for name in WHEEL_JOINTS + PASSIVE_JOINTS)
    for name in PASSIVE_JOINTS:
        limit = joints[name].find("limit")
        assert limit is not None
        assert float(limit.attrib["effort"]) > 0.0
        assert float(limit.attrib["velocity"]) > 0.0


def test_model_attaches_both_kanga_systems_and_wheel_slip():
    root = generate()
    plugins = {plugin.attrib["name"]: plugin for plugin in root.findall(".//plugin")}
    assert "kanga_core_simulation::CoreHardwareSystem" in plugins
    assert "kanga_core_simulation::PassiveSuspensionSystem" in plugins
    assert "gz::sim::systems::WheelSlip" in plugins
    slip_wheels = plugins["gz::sim::systems::WheelSlip"].findall("wheel")
    assert [wheel.attrib["link_name"] for wheel in slip_wheels] == [
        "wheel_fl",
        "wheel_bl",
        "wheel_br",
        "wheel_fr",
    ]


def test_loose_sand_is_laterally_compliant_and_axle_aligned():
    root = generate()
    wheel_surface = next(
        gazebo
        for gazebo in root.findall("gazebo")
        if gazebo.attrib.get("reference") == "wheel_fl"
    )
    assert wheel_surface.findtext("fdir1") == "0 0 1"
    assert float(wheel_surface.findtext("mu1")) < float(
        wheel_surface.findtext("mu2")
    )

    plugin = next(
        candidate
        for candidate in root.findall(".//plugin")
        if candidate.attrib["name"] == "gz::sim::systems::WheelSlip"
    )
    wheel = plugin.find("wheel")
    assert wheel is not None
    assert float(wheel.findtext("slip_compliance_lateral")) > float(
        wheel.findtext("slip_compliance_longitudinal")
    )


def test_surface_presets_have_increasing_slip():
    longitudinal = []
    lateral = []
    for surface in ["hard_ground", "compacted_sand", "loose_sand"]:
        root = generate(surface)
        plugin = next(
            candidate
            for candidate in root.findall(".//plugin")
            if candidate.attrib["name"] == "gz::sim::systems::WheelSlip"
        )
        wheel = plugin.find("wheel")
        assert wheel is not None
        longitudinal.append(float(wheel.findtext("slip_compliance_longitudinal")))
        lateral.append(float(wheel.findtext("slip_compliance_lateral")))
    assert longitudinal[0] < longitudinal[1] < longitudinal[2]
    assert lateral[0] < lateral[1] < lateral[2]


def test_unknown_surface_is_rejected():
    with pytest.raises(xacro.XacroException):
        generate("water")
