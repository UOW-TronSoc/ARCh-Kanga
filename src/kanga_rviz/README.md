# kanga_rviz

Reviewed whole-rover and general RViz configurations for development,
operation, and debugging.

## Owns

- Whole-rover and cross-domain RViz display layouts
- Topic and frame selections for supported operating modes

## Does not own

- URDF or meshes
- TF publishers
- Sensor drivers
- Simulation logic

RViz configurations required for standalone core or payload operation may live
in that domain's bringup package. Autonomy-specific layouts may live with their
autonomy package. Promote a configuration here when it represents a reviewed
whole-rover or generally useful debugging view.

Avoid keeping many near-identical or person-specific RViz files. Maintain a
small set of named configurations with a clear purpose.
