#!/usr/bin/env python3
"""Commission one or more Kanga drive ODrives via custom_odrive commission.

Merges package share config/motors/shared_motor_config.py with each
wheel_<id>_motor_config.py, writes a temp file, then runs:

  ros2 run custom_odrive commission -- \\
    --can <iface> --config <merged> --ns /wheel_<id> [--calibrate] [--save]

Rules (kanga policy):
  --calibrate  exactly one wheel (Fibre FULL_CALIBRATION_SEQUENCE)
  --save       apply then save_configuration(); may list many wheels (sequential)

Does not change custom_odrive C++ — only orchestrates its existing CLI.

Examples:
  # Apply+save all wheels (no motion calibration):
  ros2 run kanga_core_drive commission_wheels -- --wheels all --save

  # Calibrate front-left from an interactive terminal:
  ros2 run kanga_core_drive commission_wheels -- --wheels fl --calibrate

  # Trusted orchestrators may supply their already-collected confirmation:
  ros2 run kanga_core_drive commission_wheels -- \\
    --wheels fl --calibrate --save --off-ground-confirmed

  # Bench mode (stop drive.launch first — no ROS nodes on the bus):
  ros2 run kanga_core_drive commission_wheels -- --wheels fl --save --bench
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from kanga_core_description.drivetrain_profile import (
    DEFAULT_DRIVETRAIN_PROFILE,
)
from kanga_core_description.motor_limits import (
    DEFAULT_MOTOR_LIMITS,
    load_effective_drivetrain_configuration,
)

# Same directory as this script when installed to lib/kanga_core_drive/
# (ament installs sibling .py modules next to the entrypoint).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_merge import WHEEL_IDS, motor_config_path, write_merged_config  # noqa: E402


# Parse and validate a wheel selection while preserving its order.
def parse_wheels(value: str) -> list[str]:
    """Parse 'all' or comma-separated fl,bl,br,fr (order preserved, deduped)."""
    value = value.strip().lower()
    if value in ("all", "*"):
        return list(WHEEL_IDS)
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("need at least one wheel id")
    unknown = [p for p in parts if p not in WHEEL_IDS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown wheel id(s) {unknown}; expected {list(WHEEL_IDS)} or all"
        )
    # Preserve operator order; drop accidental duplicates (fl,fl → fl).
    seen: set[str] = set()
    ordered: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


# Run the underlying custom_odrive commissioning command once.
def run_commission(
    *,
    can_interface: str,
    config: Path,
    wheel_namespace: str | None,
    calibrate: bool,
    save: bool,
    off_ground_confirmed: bool,
) -> int:
    """Invoke custom_odrive commission; return process exit code.

    When wheel_namespace is set, parks that custom_odrive_node before Fibre
    work. Omit it (--bench) when drive.launch is not running to avoid CAN bus
    fights between Fibre commissioning and the C++ ODrive nodes.

    The vendored command deliberately owns the final interactive safety prompt.
    A trusted orchestrator can answer that one prompt through this wrapper only
    after supplying ``--off-ground-confirmed``. That mode is prohibited with
    ``--bench`` so the answer can never be consumed by the separate bench-mode
    coexistence prompt.
    """
    command = [
        "ros2",
        "run",
        "custom_odrive",
        "commission",
        "--",
        "--can",
        can_interface,
        "--config",
        str(config),
    ]
    if wheel_namespace is not None:
        command.extend(["--ns", wheel_namespace])
    if calibrate:
        command.append("--calibrate")
    if save:
        command.append("--save")
    print("+", " ".join(command), flush=True)

    if off_ground_confirmed:
        print(
            "Supplying the calling workflow's off-ground confirmation",
            flush=True,
        )
        completed_process = subprocess.run(
            command,
            input="yes\n",
            text=True,
            check=False,
        )
        return completed_process.returncode

    # In normal terminal use stdin remains attached, so custom_odrive presents
    # its original wheel-off-ground prompt directly to the operator.
    return subprocess.call(command)


# Parse CLI options and commission the requested wheels sequentially.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheels",
        type=parse_wheels,
        required=True,
        help="Comma-separated wheel ids (fl,bl,br,fr) or 'all'",
    )
    parser.add_argument("--can", default="can_core", help="SocketCAN interface")
    parser.add_argument(
        "--drivetrain-profile",
        default=DEFAULT_DRIVETRAIN_PROFILE,
        help=(
            "Profile id from kanga_core_description "
            f"(default: {DEFAULT_DRIVETRAIN_PROFILE})"
        ),
    )
    parser.add_argument(
        "--motor-limits",
        default=DEFAULT_MOTOR_LIMITS,
        help=(
            "Operating-limit config id or YAML path "
            f"(default: {DEFAULT_MOTOR_LIMITS})"
        ),
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run FULL_CALIBRATION_SEQUENCE (one wheel only)",
    )
    parser.add_argument(
        "--off-ground-confirmed",
        action="store_true",
        help=(
            "A trusted calling workflow has confirmed this exact motor is off "
            "the ground; valid only with --calibrate"
        ),
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Apply config then save_configuration() per wheel",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Bench mode: omit --ns (stop drive.launch before commissioning)",
    )
    parser.add_argument(
        "--motors-dir",
        type=Path,
        default=None,
        help="Override motors config directory (default: package share)",
    )
    args = parser.parse_args(argv)

    # HARD RULE: never run FULL_CALIBRATION on more than one axis in one CLI.
    if args.calibrate and len(args.wheels) != 1:
        parser.error("--calibrate requires exactly one wheel (e.g. --wheels fl)")
    if args.off_ground_confirmed and not args.calibrate:
        parser.error("--off-ground-confirmed requires --calibrate")
    if args.off_ground_confirmed and args.bench:
        parser.error("--off-ground-confirmed cannot be combined with --bench")

    drivetrain = load_effective_drivetrain_configuration(
        args.drivetrain_profile,
        args.motor_limits,
    )
    print(
        "Using drivetrain profile: "
        f"{drivetrain.profile.profile_id} ({drivetrain.profile.display_name})",
        flush=True,
    )
    print(
        "Using validated motor limits: "
        f"{drivetrain.motor_limits.motor_velocity_limit_tps:g} turns/s, "
        f"{drivetrain.motor_limits.motor_acceleration_limit_tps_s:g} turns/s²",
        flush=True,
    )

    share = Path(get_package_share_directory("kanga_core_drive"))
    motors_dir = args.motors_dir or (share / "config" / "motors")
    shared_path = motors_dir / "shared_motor_config.py"
    if not shared_path.is_file():
        print(f"Missing shared config: {shared_path}", file=sys.stderr)
        return 1

    # Sequential: one Fibre session at a time (save may list many wheels).
    for wheel_id in args.wheels:
        wheel_path = motor_config_path(motors_dir, wheel_id)
        if not wheel_path.is_file():
            print(f"Missing wheel config: {wheel_path}", file=sys.stderr)
            return 1
        wheel_namespace = None if args.bench else f"/wheel_{wheel_id}"
        # Temp dir keeps merged Fibre scripts off the package tree and cleans up
        # even if commission fails mid-run.
        with tempfile.TemporaryDirectory(prefix="kanga_motor_cfg_") as temp_directory:
            merged_config = Path(temp_directory) / f"wheel_{wheel_id}_merged.py"
            write_merged_config(
                shared_path,
                wheel_path,
                merged_config,
                drivetrain.parameters["motor_velocity_limit_tps"],
                drivetrain.parameters["motor_acceleration_limit_tps_s"],
            )
            commission_exit_code = run_commission(
                can_interface=args.can,
                config=merged_config,
                wheel_namespace=wheel_namespace,
                calibrate=args.calibrate,
                save=args.save,
                off_ground_confirmed=args.off_ground_confirmed,
            )
            if commission_exit_code != 0:
                print(
                    f"Commission failed for {wheel_id} (exit {commission_exit_code})",
                    file=sys.stderr,
                )
                return commission_exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
