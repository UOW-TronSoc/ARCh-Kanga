# kanga_core_description

Canonical robot description for the Kanga rover base.

## Owns

- Chassis, wheels, suspension, and fixed core geometry
- Versioned drivetrain hardware profiles shared by controller, drive, bringup,
  description, and motor commissioning
- Core rover links, joints, meshes, collision geometry, and frame names
- Description fragments required to attach supported payloads

## Boundary

Payload geometry belongs to each payload description package. The top-level
`kanga_description` package composes the core and selected payload into a full
robot model.

## Drivetrain profiles

[`config/drivetrains/drivetrain_2025.yaml`](config/drivetrains/drivetrain_2025.yaml)
is the current profile (`2025 drivetrain design`). It records measured inputs,
not copies of consumer-specific derived values:

- wheel diameter and width
- overall wheel-envelope length and width
- grouser angle and limited-holonomic hardware capability
- motor revolutions per wheel revolution
- commissioned motor velocity and acceleration limits in turns/s and turns/s²

The profile loader derives wheel radius, wheel-centre half-length/half-width,
and maximum wheel-joint velocity and acceleration. It then produces one shared
ROS-parameter dictionary used by controller, drive, and joint feedback. Each node declares
and reads only the entries it needs.

Ordinary new profile values are forwarded automatically: add the value to a
group in the YAML, then declare it in whichever node needs it. The loader only
needs editing when the new value itself must be calculated from other values.

Select a profile once at core bringup:

```bash
ros2 launch kanga_core_bringup core_drive.launch.py \
  drivetrain_profile:=drivetrain_2025
```

Selection is a launch-time hardware choice, not a live tuning parameter. Add a
new profile when the suspension/drivetrain changes; do not copy physical values
into controller or drive YAML files.
