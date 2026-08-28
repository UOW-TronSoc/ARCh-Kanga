# kanga_core_description

Canonical robot description for the Kanga rover base.

## Owns

- Chassis, wheels, suspension, and fixed core geometry
- Versioned drivetrain hardware profiles shared by controller, drive, bringup,
  description, and motor commissioning
- Core rover links, joints, meshes, collision geometry, and frame names
- Description fragments required to attach supported payloads

## Boundary

Payload geometry belongs to each payload description package. The top-level
`kanga_description` package composes the core and selected payload into a full
robot model.

## Core models

### `core_2026`

[`urdf/core_2026.urdf.xacro`](urdf/core_2026.urdf.xacro) is the standalone
description of the rover core used for the 2026 competition cycle. Its reusable
macro is in
[`urdf/core_2026_macro.urdf.xacro`](urdf/core_2026_macro.urdf.xacro).

`core_2026` is paired with `drivetrain_2025`, matching the drivetrain fitted to
the physical rover. The xacro defaults to that profile and rejects a different
profile so future composition cannot silently combine incompatible hardware.

Expand the model directly with:

```bash
xacro src/kanga_core/kanga_core_description/urdf/core_2026.urdf.xacro
```

### Visualise `core_2026`

Build the development image and package, then launch the model from the Docker
environment with host X11 access:

```bash
docker compose \
  -f docker/compose.dev.yaml \
  -f docker/compose.gui.yaml \
  run --rm --build kanga-dev bash -lc \
  'source /opt/ros/humble/setup.bash && \
   colcon build --symlink-install --packages-select kanga_core_description && \
   source install/setup.bash && \
   ros2 launch kanga_core_description view_core_2026.launch.py'
```

The launch starts `robot_state_publisher`, the joint-state slider GUI, and RViz.
RViz permanently uses `body_origin` as its fixed frame and displays the visual
meshes once a `body_origin -> base_link` transform is available. The preliminary
ESP32 body-pose adapter can provide that transform during development. Enable
the disabled TF display when frame debugging is useful.

On hosts where `XAUTHORITY` is not set, provide the Xauthority file explicitly:

```bash
KANGA_XAUTHORITY=/path/to/Xauthority docker compose \
  -f docker/compose.dev.yaml -f docker/compose.gui.yaml \
  run --rm kanga-dev bash
```

For a non-graphical smoke test, launch only the state publishers:

```bash
ros2 launch kanga_core_description view_core_2026.launch.py \
  use_gui:=false use_rviz:=false
```

The headless publisher listens for `wheel_joint_states` and
`suspension_joint_states` by default. Either source may be absent during a
standalone test; its movable joints remain at their neutral positions. It
samples the latest subsystem states into `/joint_states` at 50 Hz, and
`robot_state_publisher` publishes dynamic TF at up to 50 Hz. Subsystem control
and estimation must consume their owning feedback topics directly rather than
the visualization-only merged topic.

### Native and networked RViz

The RViz model display subscribes to the transient-local
`/robot_description` topic and the standard `/tf` and `/tf_static` topics. It
does not depend on a Docker-local parameter, so the publishers and RViz may run
on separate ROS 2 machines.

On the machine publishing the model:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch kanga_core_description view_core_2026.launch.py \
  use_gui:=false use_rviz:=false
```

On the machine running RViz, clone and build this package so the
`package://kanga_core_description/...` mesh paths resolve locally, then run:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select kanga_core_description
source install/setup.bash
ros2 launch kanga_core_description rviz_core_2026.launch.py
```

Both machines must use the same non-conflicting `ROS_DOMAIN_ID`. Leave
`ROS_LOCALHOST_ONLY` unset (or set it to `0`) and use the stock ROS Humble Fast
DDS middleware unless the entire ROS graph is deliberately configured for a
different implementation. ROS 2 discovery also requires multicast and DDS UDP
traffic to be permitted between the machines.

To open the RViz file directly without a launch file:

```bash
rviz2 -d "$(ros2 pkg prefix --share kanga_core_description)/rviz/core_2026.rviz"
```

The model keeps the canonical unprefixed frames and joint names by default,
including `base_link`, `wheel_fl_joint`, `wheel_bl_joint`, `wheel_br_joint`,
and `wheel_fr_joint`. An optional `prefix` xacro argument is available when a
composed model needs unique names.

All four wheel joints are continuous and have no lower or upper position
bounds. The left/right suspension joints have symmetrical ±30° ranges and the
differential-bar joint has a symmetrical ±70° range. Measured diff-bar state is
mapped to the suspension joints by `kanga_core_microcontroller`; the description
only owns the link/joint geometry and limits.

In simulation those same three joints have finite effort and velocity limits,
and Gazebo publishes their actual dynamic state. The limits are intentionally
parameterized so the simulation wrapper can tune constraint torque and bearing
damping without changing rover control behaviour.

The detailed STL files are visual geometry only. Collision geometry is kept
deliberately lightweight for simulation: main-chassis and rear LED/e-stop
boxes, an antenna cylinder, a differential-bar box, one cylinder per wheel,
and separate cylinders for the two linkage arms, their pivot barrel, and two
drivetrain housings on each suspension side.

Only the detailed core model was migrated. The old `kanga_core_simple` variant
is intentionally excluded.

## Drivetrain profiles

[`config/drivetrains/drivetrain_2025.yaml`](config/drivetrains/drivetrain_2025.yaml)
is the current profile (`2025 drivetrain design`). It records measured inputs,
not copies of consumer-specific derived values:

- wheel diameter and width
- overall wheel-envelope length and width
- grouser angle and limited-holonomic hardware capability
- motor revolutions per wheel revolution
- maximum motor velocity and acceleration capability in turns/s and turns/s²
- a deliberately high wheel-joint effort ceiling for simulation (not a
  measured drivetrain torque limit)
- suspension linkage L1/L2/L3 dimensions and physical theta at beta = 0

The profile loader derives wheel radius, wheel-centre half-length/half-width,
and maximum wheel-joint velocity and acceleration. Xacro derives the same wheel
velocity limit from the selected profile and applies it with the configured
effort ceiling to all four continuous wheel joints. Continuous joints have no
position bounds. The loader produces one shared ROS-parameter dictionary used
by controller, drive, wheel feedback, and suspension state. Each node declares
and reads only the entries it needs.

Ordinary new profile values are forwarded automatically: add the value to a
group in the YAML, then declare it in whichever node needs it. The loader only
needs editing when the new value itself must be calculated from other values.

Select a profile once at core bringup:

```bash
ros2 launch kanga_core_bringup core_drive.launch.py \
  drivetrain_profile:=drivetrain_2025
```

Selection is a launch-time hardware choice, not a live tuning parameter. Add a
new profile when the suspension/drivetrain changes; do not copy physical values
into controller or drive YAML files.

## Editable motor limits

The physical profile values are hard ceilings. Normal operating values live in
[`config/motor_limits/core.yaml`](config/motor_limits/core.yaml) so an operator
can lower them without rewriting the rover's physical description. The initial
values match the `drivetrain_2025` ceilings:

- `motor_velocity_limit_tps: 22.0`
- `motor_acceleration_limit_tps_s: 80.0`

`load_effective_drivetrain_configuration()` validates both numbers as finite
and positive, rejects values above the selected profile, then recalculates the
wheel-joint velocity and acceleration parameters. Physical controller, drive,
and commissioning launches all use that same effective dictionary.

Runtime nodes read the file only at launch. Saving a lower value therefore
requires a core relaunch; saving or calibrating a motor also writes the same
validated limits to that ODrive. The factory baseline used by the future
browser Restore Defaults action is under `config/defaults/motor_limits/`.

## Migration provenance

- Source repository: `https://github.com/UOW-TronSoc/ARCH2026-Kanga`
- Source branch: `feat/arm-simulation`
- Source commit: `8b0c0537823fac7aaac26c1bea8bd4f3763bdc06`
- Original description paths:
  `kanga_description/urdf/core/kanga_core_descr.urdf.xacro` and
  `kanga_description/urdf/core/kanga_core_macro.urdf.xacro`
- Original mesh path: `kanga_description/meshes/core/kanga_core/`
- Competition validation: not independently established from repository
  history; geometry must still be checked against the physical rover

Intentional migration changes are limited to the `core_2026` model identity,
the package-local mesh paths, the explicit `drivetrain_2025` compatibility
check, removal of the old simple variant, and a minimal standalone RViz view.
Payload models, raw Onshape exports, legacy launch/RViz files, and simulation
integration were not imported.

Outstanding description work includes validating inertial data, replacing the
temporary wheel effort ceiling when a physical torque limit is established,
and optionally replacing STL visual meshes with coloured DAE assets.
