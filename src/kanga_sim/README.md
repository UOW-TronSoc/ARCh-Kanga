# kanga_sim

Whole-rover simulation composition, shared terrain, and worlds for Kanga.

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

## Current worlds

- `worlds/flat_core.sdf` is the deterministic flat smoke/control world.
- `worlds/core_validation.sdf` contains alternating wheel blocks, a rounded
  berm, a ten-degree incline, and primitive rocks.
- `worlds/sand_dunes.sdf` is a 30 x 20 m loose-sand terrain generated from the
  high-frequency heightmap. Its collision and visual reference the same
  257 x 257 triangle mesh because Fortress can generate mismatched surfaces
  from separate physics and rendering heightmap implementations.

Launch the core composition with:

```bash
ros2 launch kanga_sim core_simulation.launch.py
```

Launch the dune heightmap with:

```bash
ros2 launch kanga_sim core_simulation.launch.py world:=sand_dunes.sdf
```

`render_engine:=auto` is the default. It selects Ogre1 only for worlds that
still contain heightmap primitives and Ogre2 for mesh / primitive worlds;
either can be overridden explicitly.
Fortress's Ogre1 cache does not include the terrain material in its cache key,
so the launcher removes generated heightmap cache entries before loading a
heightmap. This prevents an earlier texture-less launch from staying black.
`spawn_z:=auto` similarly keeps the rover 0.02 m above the highest possible
terrain surface (about 0.812 m in `sand_dunes.sdf`). Pass a numeric value to
override it for a particular spawn location.

All worlds default to the rover's preliminary `loose_sand` contact preset.
That preset favours lateral compliance for the square skid-steer footprint;
selecting `hard_ground` or `compacted_sand` is an explicit diagnostic override.

The rover-specific Gazebo systems and surface presets remain in
`kanga_core_simulation`. This package owns their world selection, spawning,
shared controller/WHS composition, and future payload composition.
