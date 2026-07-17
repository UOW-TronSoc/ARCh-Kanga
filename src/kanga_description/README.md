# kanga_description

Canonical description for the Kanga rover core and assembly of supported
payload configurations.

## Owns

- Core rover URDF, xacro, meshes, and collision geometry
- Core joint, link, and TF frame naming
- Whole-rover assembly of selected payload description packages
- Description-only launch helpers when required

## Does not own

- RViz layouts
- Manipulator, excavator, or science payload geometry
- Controllers or hardware drivers
- Simulation bridges or worlds
- Camera and navigation runtime configuration

Each payload owns its model in its `kanga_<payload>_description` package. The
2026 repository contains duplicated description trees, so migration must select
and validate canonical assets rather than copying every export and variant.
