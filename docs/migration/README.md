# 2026 code migration

## Primary reference

```text
Repository: https://github.com/UOW-TronSoc/ARCH2026-Kanga
Branch:     feat/arm-simulation
Commit:     8b0c0537823fac7aaac26c1bea8bd4f3763bdc06
```

The remote commit is the reference, not the locally modified checkout. Other
competition-tested branches may be consulted component by component, but
`feat/arm-simulation` is the starting point for inventory and provenance.

## Migration method

For each component:

1. Identify the best-known working source file and exact commit.
2. Record its destination package and any duplicated variants.
3. Import the smallest coherent behaviour without redesigning it simultaneously.
4. Make only the changes needed to build in the new workspace.
5. Add a behavioural or unit test where practical.
6. Validate against the old implementation or hardware.
7. Refactor behind that validation.

Do not merge the old branch wholesale. Do not migrate generated files such as
`__pycache__`, build products, editor workspaces, or temporary variants.

Do not create an in-tree deprecated copy of the old arm stack. Keep
`ARCH2026-Kanga` as the external reference and migrate selectively into
`kanga_manipulator_*` when that work starts.

## CAN and ODrive policy

ODrive is a multi-project dependency. Drive and manipulator motor work wait
until the external ODrive repository exists and is pinned under `src/vendor`.

Use a hybrid CAN model:

- **External ODrive repository:** owns direct SocketCAN access and its epoll /
  socket helpers internally (same pattern as the upstream
  [odriverobotics/ros_odrive](https://github.com/odriverobotics/ros_odrive)
  lineage that the 2026 package was expanded from). Launch one ODrive node per
  axis. Do not depend on any Kanga package.
- **ARCh-Kanga:** use `ros2socketcan_bridge` (see
  [ROS4SPACE/ros2can_bridge](https://github.com/ROS4SPACE/ros2can_bridge)) for
  club-owned devices such as Daly BMS, microcontrollers, and science. Do not
  port the ODrive epoll event-loop stack into `kanga_canbus` or teach it as the
  Kanga CAN pattern.

Linux SocketCAN allows multiple RAW sockets on one interface, so ODrive nodes
and a ros2can bridge may share a bus. Do not also command those same ODrive
axes through the bridge.

## Initial migration order

1. Inventory custom interfaces used by the drive and ODrive stacks.
2. Establish Kanga-wide definitions in `kanga_interfaces` and identify generic
   ODrive interfaces that must live in the external ODrive repository.
3. Establish the reusable ODrive implementation in its own repository, move
   SocketCAN/epoll helpers into that repository, record provenance (including
   the upstream ros_odrive origin and how the fork differs), and pin it beneath
   `src/vendor` through a `.repos` manifest.
4. Use `ros2socketcan_bridge` in Kanga bringup for non-ODrive CAN traffic; do
   not migrate `kanga_canbus` epoll/`SocketCanIntf` as the ODrive foundation.
5. Establish the Jetson GPIO motion-stop input and manual competition override,
   then define their software contract through `kanga_whs` and
   `kanga_interfaces`.
6. Migrate wheel mapping into `kanga_core_drive`, separating pure kinematics
   from ROS and ODrive glue.
7. Migrate the canonical rover-base model into `kanga_core_description`, then
   migrate each payload model into its payload description package.
8. Compose the complete model in `kanga_description` and add minimal core-only
   and whole-rover bringup.
9. Migrate utilities, autonomy, manipulator, excavator, science, and simulation
   in independently reviewed package slices. Rewrite the manipulator into
   `kanga_manipulator_*` guided by the old `kanga_arm*` packages; do not bulk
   copy them into a deprecated tree.

Manipulator and excavator code must be inventoried as separate current
systems. Do not preserve their old shared control or launch structure unless a
current, validated requirement justifies a common library.

## Provenance requirement

Every imported subsystem README should record:

- source repository, branch, and commit;
- original package or file paths;
- whether it was competition-tested;
- intentional changes made during migration;
- outstanding validation or refactoring work.

The external ODrive repository must additionally document its upstream origin,
why it was forked, how it differs from upstream, its hardware compatibility
policy, and that SocketCAN/epoll helpers are internal to that repository.
