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

### Runtime container model

Kanga uses one ROS runtime container plus one basestation container. The ROS
container has two forms; they are alternatives, not services to run together:

| Environment | ROS runtime | Basestation | Normal total |
| --- | --- | --- | --- |
| Development or simulation | `kanga-dev` | `basestation-server` | 2 containers |
| Rover production | `kanga-onboard` | `basestation-server` | 2 containers |

`kanga-dev` is persistent. Every `docker_shell.bash` invocation enters the same
running container, allowing the launch agent, simulation or physical stack, and
multiple diagnostic shells to share one process namespace. `kanga-onboard` is
the headless, automatically restarted production form and is not used alongside
`kanga-dev`.

### Path A — ROS workspace

Build/start the development image and enter its persistent container from the
repository root:

```bash
./scripts/docker_shell.bash
```

`docker_shell.bash` performs the Docker image build automatically when creating
the runtime. It does not build the ROS workspace; run `build_workspace.bash`
inside the container as shown below.

On macOS or other hosts that cannot install Humble Gazebo binaries:

```bash
KANGA_SIM=none ./scripts/docker_shell.bash
```

On a graphical Linux host, GPU selection is controlled when `kanga-dev` is
first created:

```bash
KANGA_GPU=auto ./scripts/docker_shell.bash    # default: use NVIDIA when ready
KANGA_GPU=nvidia ./scripts/docker_shell.bash  # require NVIDIA or fail clearly
KANGA_GPU=none ./scripts/docker_shell.bash    # disable NVIDIA selection
```

`KANGA_GPU` affects GUI applications such as Gazebo and RViz. Because
`kanga-dev` is persistent, run `./scripts/docker_dev_down.bash` before changing
`KANGA_GPU` or `KANGA_SIM`; additional shells always reuse the existing
container configuration.

Inside the container:

```bash
./scripts/build_workspace.bash
source install/setup.bash
```

For launch-manager development, keep the agent in the first shell and open a
second shell into that same container:

```bash
# Terminal 1
./scripts/docker_shell.bash
ros2 launch kanga_launch_agent launch_agent.launch.py

# Terminal 2 — reuses the running container
./scripts/docker_shell.bash
```

Stop the persistent development runtime with
`./scripts/docker_dev_down.bash`. A manually started simulation is reported by
the agent as `UNMANAGED` and remains outside launch-manager control for now.

### Path B — Basestation operator stack

After `install/setup.bash` exists, start the FastAPI server and built React UI:

```bash
./scripts/basestation_up.bash
```

This starts only `basestation-server`; it does not create another ROS runtime.
During development the agent runs in `kanga-dev`. On the rover, systemd starts
`kanga-onboard` before the basestation.

See [Docker setup](docs/install/docker.md), [CAN setup](docs/install/can.md),
[Basestation setup](docs/install/basestation.md), and the complete
[system startup and launch-manager plan](docs/launch-manager/README.md).

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
