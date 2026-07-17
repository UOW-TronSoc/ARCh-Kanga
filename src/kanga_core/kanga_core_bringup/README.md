# kanga_core_bringup

Standalone bringup for operating the physical Kanga rover base without a
payload.

## Owns

- Core-only launch entry points
- Composition of core description, drive, battery, and microcontroller nodes
- Core-specific configuration selected by those launch files
- Core-only RViz configuration when useful for standalone operation

## Boundary

`kanga_bringup` composes the core with cameras, a selected payload, and optional
autonomy for full-rover operation.
