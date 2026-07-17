# ROS 2 source tree

Colcon searches this tree recursively. Some top-level directories are structure
folders containing multiple ROS packages; structure folders have a README but
no `package.xml` or `CMakeLists.txt` of their own.

```text
src/
├── kanga_interfaces/             Shared ROS interfaces package
├── kanga_description/            Core rover and whole-rover assembly package
├── kanga_drive/                  Drive control package
├── kanga_bringup/                Whole-rover bringup package
├── kanga_sim/                    Whole-rover simulation package
├── kanga_rviz/                   RViz configuration package
│
├── kanga_hardware/               Hardware structure folder
│   ├── kanga_cameras/
│   ├── kanga_battery/
│   ├── kanga_core/
│   ├── kanga_odrive/
│   └── kanga_microcontroller/
│
├── kanga_auto/                   Autonomy structure folder
│   ├── kanga_slam/
│   ├── kanga_cube_detection/
│   ├── kanga_nav2/
│   └── kanga_placard_detection/
│
├── kanga_util/                   Cross-cutting utility structure folder
│   ├── kanga_canbus/
│   ├── kanga_onboard_control/
│   └── kanga_joy/
│
├── kanga_manipulator/            Manipulator structure folder
├── kanga_excavator/              Excavator structure folder
└── kanga_science/                Science structure folder
```

Each payload structure contains its own:

```text
kanga_<payload>_description/
kanga_<payload>_controller/
kanga_<payload>_bringup/
kanga_<payload>_simulation/
kanga_<payload>_microcontroller/
kanga_<payload>_utils/            Reserved structure folder, not a package
```

Package and structure-folder READMEs define their exact responsibilities.

## Rules

- Put shared ROS interface definitions in `kanga_interfaces`; do not define
  messages inside feature packages without a strong ownership reason.
- Keep mathematical logic independent of ROS where practical so it can be unit
  tested without a running ROS graph.
- Keep hardware transport out of drive and payload controller logic.
- Keep whole-rover composition in `kanga_bringup`; payload bringup packages
  compose only their own payload stack.
- Keep canonical core geometry and whole-rover assembly in
  `kanga_description`; each payload owns its geometry in its description
  package.
- Do not copy third-party source trees such as RTAB-Map or Nav2 into the
  workspace.
- Do not create permanent files with suffixes such as `_new`, `_old`,
  `_working`, or `_final`.
- A structure folder must not have `package.xml` or `CMakeLists.txt` unless it
  intentionally becomes a ROS package.
