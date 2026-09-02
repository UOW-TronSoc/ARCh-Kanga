"""Offline contract checks for the stable physical-rover launch profile."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROVER_LAUNCH = PACKAGE_ROOT / "launch" / "rover.launch.py"
MICROCONTROLLER_ROOT = PACKAGE_ROOT.parent / "kanga_core_microcontroller"


def test_rover_launch_composes_sensor_and_transform_pipeline() -> None:
    source = ROVER_LAUNCH.read_text(encoding="utf-8")

    required_launches = {
        "socket_can_bridge.launch.xml",
        "view_core_2026.launch.py",
        "whs.launch.py",
        "drive.launch.py",
        "controller.launch.py",
        "core_can_bridge.launch.py",
        "suspension_state.launch.py",
        "body_pose_tf.launch.py",
    }
    for launch_name in required_launches:
        assert launch_name in source

    assert '"use_joint_state_publisher": "true"' in source
    assert '"use_gui": "false"' in source
    assert '"use_rviz": "false"' in source
    assert '"launch_socketcan": "false"' in source
    assert '"imu_frame_id": imu_frame_id' in source
    assert 'LaunchConfiguration("use_body_pose_tf")' in source
    assert "condition=IfCondition(use_body_pose_tf)" in source
    assert "bench_teleop.launch.py" not in source


def test_imu_frame_is_independent_from_body_pose_child() -> None:
    bridge_launch = (
        MICROCONTROLLER_ROOT / "launch" / "core_can_bridge.launch.py"
    ).read_text(encoding="utf-8")

    assert 'LaunchConfiguration("imu_frame_id")' in bridge_launch
    assert '"imu_frame_id": imu_frame_id' in bridge_launch
    assert '"imu_frame_id": body_pose_child_frame' not in bridge_launch


def test_suspension_joint_names_match_the_robot_description() -> None:
    suspension_config = (
        MICROCONTROLLER_ROOT / "config" / "suspension_state.yaml"
    ).read_text(encoding="utf-8")
    description = (
        PACKAGE_ROOT.parent
        / "kanga_core_description"
        / "urdf"
        / "core_2026_macro.urdf.xacro"
    ).read_text(encoding="utf-8")

    for joint_name in (
        "diff_bar_joint",
        "left_suspension_joint",
        "right_suspension_joint",
    ):
        assert joint_name in suspension_config
        assert f'name="${{prefix}}{joint_name}"' in description

    for child_link in ("diff_bar", "left_suspension", "right_suspension"):
        assert '<parent link="${prefix}kanga_core"/>' in description
        assert f'<child link="${{prefix}}{child_link}"/>' in description

    assert description.count('<parent link="${prefix}left_suspension"/>') == 2
    assert description.count('<parent link="${prefix}right_suspension"/>') == 2


def test_imu_tf_is_the_only_parent_of_base_link_in_this_profile() -> None:
    description = (
        PACKAGE_ROOT.parent
        / "kanga_core_description"
        / "urdf"
        / "core_2026_macro.urdf.xacro"
    ).read_text(encoding="utf-8")

    assert '<parent link="${prefix}base_link"/>' in description
    assert '<child link="${prefix}kanga_core"/>' in description
    assert '<child link="${prefix}base_link"/>' not in description
