# kanga_rviz

Reviewed RViz configurations for development, operation, and debugging.

## Owns

- RViz display layouts
- Topic and frame selections for supported operating modes

## Does not own

- URDF or meshes
- TF publishers
- Sensor drivers
- Simulation logic

Avoid keeping many near-identical or person-specific RViz files. Maintain a
small set of named configurations with a clear purpose.
