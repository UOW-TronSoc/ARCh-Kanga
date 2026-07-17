# kanga_core_description

Canonical robot description for the Kanga rover base.

## Owns

- Chassis, wheels, suspension, and fixed core geometry
- Core rover links, joints, meshes, collision geometry, and frame names
- Description fragments required to attach supported payloads

## Boundary

Payload geometry belongs to each payload description package. The top-level
`kanga_description` package composes the core and selected payload into a full
robot model.
