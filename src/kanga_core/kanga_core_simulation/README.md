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
