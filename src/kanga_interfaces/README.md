# kanga_interfaces

Shared ROS 2 messages, services, and actions for Kanga.

## Owns

- Kanga-specific `.msg`, `.srv`, and `.action` definitions
- Interface generation and interface-only dependencies

## Does not own

- Nodes or executable logic
- Hardware communication
- Launch or parameter files

Add an interface only when standard ROS interfaces cannot express the contract
clearly. Keep definitions transport-neutral and document units in field
comments. Interface migration from the 2026 repository has not started yet.
