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

  # Calibrate front-left only (drive_manager calibrate_fl shells this):
  ros2 run kanga_core_drive commission_wheels -- --wheels fl --calibrate
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from ament_index_python.packages import get_package_share_directory

# Same directory as this script when installed to lib/kanga_core_drive/
# (ament installs sibling .py modules next to the entrypoint).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_merge import WHEEL_IDS, motor_config_path, write_merged_config  # noqa: E402


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


def run_commission(
    *,
    can: str,
    config: Path,
    ns: str,
    calibrate: bool,
    save: bool,
) -> int:
    """Invoke custom_odrive commission; return process exit code.

    --ns must match the ROS namespace of the live custom_odrive_node for that
    wheel (e.g. /wheel_fl) so Fibre identity and any node-side checks align.
    """
    cmd = [
        "ros2",
        "run",
        "custom_odrive",
        "commission",
        "--",
        "--can",
        can,
        "--config",
        str(config),
        "--ns",
        ns,
    ]
    if calibrate:
        cmd.append("--calibrate")
    if save:
        cmd.append("--save")
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


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
        "--calibrate",
        action="store_true",
        help="Run FULL_CALIBRATION_SEQUENCE (one wheel only)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Apply config then save_configuration() per wheel",
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
        ns = f"/wheel_{wheel_id}"
        # Temp dir keeps merged Fibre scripts off the package tree and cleans up
        # even if commission fails mid-run.
        with tempfile.TemporaryDirectory(prefix="kanga_motor_cfg_") as tmp:
            merged = Path(tmp) / f"wheel_{wheel_id}_merged.py"
            write_merged_config(shared_path, wheel_path, merged)
            rc = run_commission(
                can=args.can,
                config=merged,
                ns=ns,
                calibrate=args.calibrate,
                save=args.save,
            )
            if rc != 0:
                print(f"Commission failed for {wheel_id} (exit {rc})", file=sys.stderr)
                return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
