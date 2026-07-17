# ROS 2 source tree

Colcon searches this tree recursively. Domain directories are structure folders
containing related ROS packages; they have a README but no `package.xml` or
`CMakeLists.txt` of their own.

```text
src/
├── kanga_interfaces/             Shared ROS interfaces
├── kanga_whs/                    Whole-robot motion-stop coordination
├── kanga_cameras/                Shared camera integration
├── kanga_description/            Whole-rover model composition
├── kanga_bringup/                Whole-rover physical composition
├── kanga_sim/                    Whole-rover simulation composition
├── kanga_rviz/                   Whole-rover and general RViz layouts
│
├── kanga_core/                   Rover-base domain
│   ├── kanga_core_drive/
│   ├── kanga_core_description/
│   ├── kanga_core_bringup/
│   ├── kanga_core_microcontroller/
│   ├── kanga_core_battery/
│   └── kanga_core_simulation/
│
├── kanga_auto/                   Autonomous systems domain
├── kanga_util/                   Cross-cutting utility domain
├── kanga_manipulator/            Manipulator payload domain
├── kanga_excavator/              Excavator payload domain
├── kanga_science/                Science payload domain
└── vendor/                       Externally maintained ROS repositories
```

Each payload domain contains its own:

```text
kanga_<payload>_description/
kanga_<payload>_controller/
kanga_<payload>_bringup/
kanga_<payload>_simulation/
kanga_<payload>_microcontroller/
kanga_<payload>_utils/            Reserved structure folder, not a package
```

Package and structure-folder READMEs define their exact responsibilities.

## Composition model

- `kanga_core_*` packages operate the rover base independently of a payload.
- Payload packages operate their payload independently of the rover base.
- `kanga_whs` provides the shared software motion-inhibit contract from a
  physical switch connected to Jetson GPIO.
- Top-level `kanga_description`, `kanga_bringup`, and `kanga_sim` packages
  compose the core with a selected payload for whole-rover operation.
- Domain-specific RViz configurations may live with domain bringup packages;
  `kanga_rviz` owns reviewed whole-rover and general debugging layouts.

## Rules

- Put shared ROS interface definitions in `kanga_interfaces`; do not define
  messages inside feature packages without a strong ownership reason.
- Keep mathematical logic independent of ROS where practical so it can be unit
  tested without a running ROS graph.
- Keep hardware transport out of core drive and payload controller logic.
- Every motor controller must enforce the shared motion-inhibit state.
- Keep whole-rover composition in the top-level composition packages.
- Keep canonical core geometry in `kanga_core_description`, payload geometry in
  its payload package, and full model assembly in `kanga_description`.
- Import independently maintained ROS repositories beneath `vendor` using a
  pinned `.repos` manifest; do not manually copy their source.
- Do not copy upstream projects such as RTAB-Map or Nav2 into this repository.
- Do not create permanent files with suffixes such as `_new`, `_old`,
  `_working`, or `_final`.
