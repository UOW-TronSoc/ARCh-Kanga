# kanga_sim

Whole-rover simulation composition for Kanga.

## Owns

- Simulation worlds and shared assets not part of canonical descriptions
- Spawning and composition of core and selected payload simulations
- Whole-rover simulation launch entry points

## Does not own

- Canonical URDF, xacro, or meshes
- Real hardware drivers
- Subsystem-specific simulated hardware and adapters
- Control logic shared with physical hardware
- RViz layouts

Each subsystem simulation remains independently launchable. The old
`feat/arm-simulation` Raisim bridge is a future migration candidate.
