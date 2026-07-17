# 2026 code migration

## Primary reference

```text
Repository: https://github.com/UOW-TronSoc/ARCH2026-Kanga
Branch:     feat/arm-simulation
Commit:     8b0c0537823fac7aaac26c1bea8bd4f3763bdc06
```

The remote commit is the reference, not the locally modified checkout. Other
competition-tested branches may be consulted component by component, but
`feat/arm-simulation` is the starting point for inventory and provenance.

## Migration method

For each component:

1. Identify the best-known working source file and exact commit.
2. Record its destination package and any duplicated variants.
3. Import the smallest coherent behaviour without redesigning it simultaneously.
4. Make only the changes needed to build in the new workspace.
5. Add a behavioural or unit test where practical.
6. Validate against the old implementation or hardware.
7. Refactor behind that validation.

Do not merge the old branch wholesale. Do not migrate generated files such as
`__pycache__`, build products, editor workspaces, or temporary variants.

## Initial migration order

1. Inventory custom interfaces used by the drive and ODrive stacks.
2. Establish the required definitions in `kanga_interfaces`.
3. Import and document the modified ODrive implementation in
   `kanga_hardware/kanga_odrive`.
4. Migrate wheel mapping into `kanga_drive`, separating pure kinematics from
   ROS and ODrive glue.
5. Migrate the canonical core rover model into `kanga_description`, then
   migrate each payload model into its payload description package.
6. Add minimal real-rover composition in `kanga_bringup`.
7. Migrate hardware, utilities, autonomy, manipulator, excavator, science, and
   simulation in independently reviewed package slices.

Manipulator and excavator code must be inventoried as separate current
systems. Do not preserve their old shared control or launch structure unless a
current, validated requirement justifies a common library.

## Provenance requirement

Every imported subsystem README should record:

- source repository, branch, and commit;
- original package or file paths;
- whether it was competition-tested;
- intentional changes made during migration;
- outstanding validation or refactoring work.

The ODrive README must additionally document its upstream origin, why it was
forked, and why it must not be casually replaced with upstream.
