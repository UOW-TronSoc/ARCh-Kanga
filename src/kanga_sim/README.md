# kanga_sim

Simulation-specific integration for Kanga.

## Owns

- Simulator bridges and adapters
- Simulation worlds and assets not part of the canonical robot description
- Simulated hardware configuration
- Simulation-only launch files

## Does not own

- Canonical URDF, xacro, or meshes
- Real hardware drivers
- Control logic that can be shared with the rover
- RViz layouts

The old `feat/arm-simulation` Raisim bridge is a future migration candidate,
not part of this architecture-only change.
