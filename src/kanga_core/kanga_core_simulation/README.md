# kanga_core_simulation

Standalone simulation integration for the Kanga rover base.

## Owns

- Core simulated-hardware configuration
- Core-only simulation launch entry points
- Simulator adapters specific to the rover base

## Boundary

The top-level `kanga_sim` package owns worlds and composes this package with a
selected payload simulation. Canonical geometry remains in
`kanga_core_description`.

## Planned Gazebo integration

This section records the current simulation direction. It is a design note;
the Gazebo runtime, launch files, and plugins described below are not yet
implemented. The development Docker image currently contains ROS 2 Humble but
does not contain a Gazebo runtime.

Use Gazebo Fortress initially because it is the officially supported Gazebo
pairing for ROS 2 Humble. Simulation-specific systems should use Gazebo system
plugins and the ROS/Gazebo bridge directly; this project does not plan to use
`ros2_control`.

### State and TF ownership

Gazebo must be the sole authority for simulated physical state:

- Gazebo, or a simulation pose adapter, publishes `world`/`odom` to
  `base_link`.
- Gazebo publishes simulated wheel, differential-bar, and suspension joint
  state.
- `robot_state_publisher` consumes that joint state and publishes the remaining
  link transforms.
- An RViz instance on another ROS 2 host consumes `/robot_description`,
  `/joint_states`, `/tf`, and `/tf_static`; it does not run hardware feedback
  adapters.

The simulation launch must therefore disable physical-hardware state sources:

```text
use_body_pose_tf:=false
use_suspension_state:=false
use_joint_state_publisher:=false
use_drive:=false
```

The controller may be enabled after a Gazebo drive adapter exists to consume
its wheel commands. The simulation adapter must respect the drivetrain
profile's wheel velocity and acceleration limits. The current 1000 N·m URDF
wheel effort value is deliberately a non-binding simulation ceiling, not a
motor torque model.

External RViz should use `world` or `odom` as its fixed frame when global rover
motion needs to be visible. The RViz-only launch in `kanga_core_description`
is the intended remote visualization entry point.

### Reduced-order passive suspension

For the initial terrain simulation, use a reduced-order passive model instead
of either prescribing joint positions or reproducing every RSSR linkage body.
Keep these three simulated revolute joints dynamic:

- `diff_bar_joint`
- `left_suspension_joint`
- `right_suspension_joint`

A `kanga_core_simulation` Gazebo system plugin should reuse the tested nonlinear
kinematic relationship from differential-bar angle `beta` to the two
suspension angles. It should enforce the two closure errors

```text
C_left  = theta_left  - f(beta)
C_right = theta_right - f(beta)
```

with constraint reaction torques and damping. It must not simply overwrite the
joint positions. Contact forces from wheels on rocks or terrain must be able to
move the passive suspension and differential bar, while the constraint
transfers the reaction to the other joints. Apply the corresponding reaction
to `diff_bar_joint` so the plugin does not inject unbalanced energy.

Retain the existing ±70° differential-bar and ±30° suspension limits. Add
only enough joint damping or bearing friction for stable simulation; do not add
a centring spring unless one exists on the physical rover. Gazebo owns and
publishes the resulting joint positions. The real encoder-facing suspension
state publisher remains disabled in simulation.

This model should provide useful passive articulation over berms, rocks, and
mounds without the numerical and maintenance cost of a complete RSSR model.
If its wheel paths or load transfer prove visibly wrong, the later high-fidelity
option is an SDFormat model with the actual closed linkage. URDF itself must
remain a tree, while SDFormat can represent a kinematic graph with closed
loops. Prototype any closed-loop model separately before replacing the reduced
model because solver support and stability depend on the selected physics
engine, joint placement, inertias, and time step.

References:

- [SDFormat model kinematics](https://sdformat.org/tutorials/specification/spec_model_kinematics/)
- [Gazebo physics concepts](https://gazebosim.org/api/physics/8/physicsconcepts.html)
- [ROS and Gazebo version compatibility](https://gazebosim.org/docs/harmonic/ros_installation/)

### PLA wheel interaction with sand

The first Gazebo implementation should approximate sand with rigid terrain,
not particle simulation:

1. Represent berms and mounds with a heightmap or simplified collision mesh.
2. Represent important rocks with individual simplified collision geometry.
3. Give sand regions an appropriate visual material and tuned contact
   properties.
4. Configure longitudinal and lateral wheel-slip compliance for all four
   wheels.
5. Tune friction, slip, contact stiffness, and contact damping against simple
   measurements from the physical rover.

Gazebo has no built-in material pair named "PLA on sand". Treat the parameters
as an effective interaction model for the particular wheel geometry, sand grain
size, moisture, and compaction. Keep named presets such as `hard_ground`,
`compacted_sand`, and `loose_sand` in simulation configuration rather than in
the canonical robot description.

Useful calibration tests are:

- an incline test, using the initial sliding angle for a rough Coulomb-friction
  estimate (`mu ~= tan(angle)`);
- a powered wheel or rover drawbar-pull test to tune longitudinal traction and
  slip;
- a lateral drag test to tune sideways friction; and
- comparison against a known slope, block, berm, or rock traversal.

The current smooth-cylinder wheel collision cannot mechanically engage the
ground with the wheel grousers. Begin with it and the wheel-slip model. If rock
and berm climbing looks unrealistic, add a simulation-only compound wheel
collision made from the cylinder and a modest number of primitive grouser
shapes. Do not use the detailed visual mesh as the default collision mesh.

Rigid Gazebo terrain will not reproduce sinkage, ruts, bulldozing, or displaced
soil. Those effects would justify evaluating a terramechanics simulator such as
Project Chrono, which provides SCM deformable soil and DEM granular terrain.
That is a separate high-fidelity path and is not required for the initial
suspension and navigation showcase.

References:

- [Gazebo Fortress wheel-slip system](https://gazebosim.org/api/gazebo/6/WheelSlip_8hh.html)
- [Gazebo friction and contact parameters](https://get.gazebosim.org/tutorials?cat=physics&tut=physics_params)
- [Project Chrono terrain models](https://api.projectchrono.org/development/vehicle_terrain.html)
