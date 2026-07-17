# kanga_bringup

Top-level launch entry points for operating the physical rover.

## Owns

- Named rover operating modes
- Composition of whole-rover description, safety, core bringup, cameras,
  selected payload bringup, and optional autonomy launches
- Selection of reviewed configuration sets

## Does not own

- Control algorithms
- Device protocols
- Simulation-only launch flows
- Package-private configuration

Launch files should be small, readable compositions. Core and payload bringup
packages remain standalone; this package selects and connects those stacks for
a whole-rover operating mode.
