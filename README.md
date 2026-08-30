# ARCh Kanga

Permanent ROS 2 software repository for the UOW TronSoc Kanga rover competing
in the Australian Rover Challenge (ARCh).

This repository is organised as an ongoing product rather than a yearly code
dump. Competition-ready states will be preserved with tags and releases such
as `arch-2027-final`.

## Current status

The ROS 2 Humble development environment, SocketCAN workflow, physical core
drive boundary, shared core controller, canonical 2026 core description, WHS,
microcontroller state adapters, and core bringup are implemented. A Gazebo
Fortress core simulation now replaces the physical drive boundary without
changing controller or operator interfaces. Details:
[core drive migration](docs/migration/core_drive.md) and
[core simulation](src/kanga_core/kanga_core_simulation/README.md).

The primary migration reference is the old `ARCH2026-Kanga` repository at
remote commit `8b0c0537823fac7aaac26c1bea8bd4f3763bdc06` on
`feat/arm-simulation`. Code will be moved deliberately rather than copying the
old tree wholesale. See the [migration guide](docs/migration/README.md) for
progress and branch strategy.

## Repository layout

```text
basestation/         Operator UI/API (single FastAPI server + React, not colcon)
docker/              Reproducible ROS 2 and basestation images
docs/                Architecture, migration, and installation documentation
scripts/             Host and container development helpers
src/                 ROS 2 packages
```

See [the package map](src/README.md) and
[architecture documentation](docs/architecture/README.md) before adding a new
package or moving code across package boundaries.

## Development environment

> **Platform note:** Development, building, and hardware-independent testing can
> be performed in the Linux Docker environment from Linux, macOS, or Windows.
> Running against the rover's physical CAN and USB devices requires a Linux host;
> macOS and Windows Docker installations run Linux containers through a VM and
> are not supported for direct rover hardware operation.

### Path A — ROS workspace

Build and enter the development container from the repository root:

```bash
docker compose -f docker/compose.dev.yaml build
./scripts/docker_shell.bash
```

On macOS or other hosts that cannot install Humble Gazebo binaries:

```bash
KANGA_SIM=none ./scripts/docker_shell.bash
```

Inside the container:

```bash
./scripts/build_workspace.bash
source install/setup.bash
```

### Path B — Basestation operator stack

After `install/setup.bash` exists, start the FastAPI server and built React UI:

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
