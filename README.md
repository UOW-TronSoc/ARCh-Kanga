# ARCh Kanga

Permanent ROS 2 software repository for the UOW TronSoc Kanga rover competing
in the Australian Rover Challenge (ARCh).

This repository is organised as an ongoing product rather than a yearly code
dump. Competition-ready states will be preserved with tags and releases such
as `arch-2027-final`.

## Current status

The ROS 2 Humble development environment and SocketCAN workflow are working.
The first migration slices are merged to `main`:

- **`kanga_interfaces`** — `BatteryInfo` and `BmsStatus` (merged via PR #15)
- **`ros2_socketcan`** — pinned at `1.3.0` under `src/vendor` via
  `kanga_vendor.repos` (merged via PR #15)

Drive, battery, and bringup implementations are not migrated yet. The external
ODrive package ([`custom-ros-odrive`](https://github.com/UOW-TronSoc/custom-ros-odrive))
is complete but not yet pinned in this workspace.

**Next up:** core drive + ODrive stack (vendor pin → `kanga_core_wheels` →
`kanga_core_drive` mapper). Full hand-off:
[docs/migration/core_drive.md](docs/migration/core_drive.md).

The primary migration reference is the old `ARCH2026-Kanga` repository at
remote commit `8b0c0537823fac7aaac26c1bea8bd4f3763bdc06` on
`feat/arm-simulation`. Code will be moved deliberately rather than copying the
old tree wholesale. See the [migration guide](docs/migration/README.md) for
progress and branch strategy.

## Repository layout

```text
basestation/         Operator UI/API scaffold (ROS participants, not colcon)
docker/              Reproducible ROS 2 and basestation images
docs/                Architecture, migration, and installation documentation
scripts/             Host and container development helpers
src/                 ROS 2 packages
```

See [the package map](src/README.md) and
[architecture documentation](docs/architecture/README.md) before adding a new
package or moving code across package boundaries.

## Development environment

### Path A — ROS workspace

Build and enter the development container from the repository root:

```bash
docker compose -f docker/compose.dev.yaml build
./scripts/docker_shell.bash
```

Inside the container:

```bash
./scripts/build_workspace.bash
source install/setup.bash
```

### Path B — Basestation scaffold

After `install/setup.bash` exists, start the operator stubs:

```bash
./scripts/basestation_up.bash
```

See [Docker setup](docs/install/docker.md), [CAN setup](docs/install/can.md),
and [Basestation setup](docs/install/basestation.md).

## Branch workflow

```text
feature branch -> develop -> main
```

- Develop changes on focused feature branches.
- Merge feature branches into `develop` through pull requests.
- Promote tested milestones from `develop` to `main` through reviewed pull
  requests.
- Do not bypass branch protections or push directly to protected branches.

## Migration principle

Preserve known-working behaviour first, validate it, and only then refactor it.
The old repositories are references, not architectures to reproduce. See the
[migration guide](docs/migration/README.md).
