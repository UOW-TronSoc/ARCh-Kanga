# kanga_description

Whole-rover description composition for supported Kanga configurations.

## Owns

- Assembly of `kanga_core_description` and selected payload descriptions
- Whole-rover attachment choices and top-level model variants
- Description-only launch helpers when required

## Does not own

- RViz layouts
- Core or payload geometry already owned by domain description packages
- Controllers or hardware drivers
- Simulation bridges or worlds
- Camera and navigation runtime configuration

The core and each payload own their model fragments. This package connects
those fragments without copying them. The 2026 repository contains duplicated
description trees, so migration must select and validate canonical assets rather
than copying every export and variant.
