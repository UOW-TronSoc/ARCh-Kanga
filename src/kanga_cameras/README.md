# kanga_cameras

Shared Kanga integration for ROS-compatible cameras used by the rover core,
payloads, and autonomous systems.

## Owns

- Kanga-specific camera configuration and launch integration
- Common status and naming across supported ZED, RealSense, and OAK cameras

## Boundary

This package is provisional. Prefer upstream ROS camera drivers directly if no
shared Kanga-specific integration layer is required.
