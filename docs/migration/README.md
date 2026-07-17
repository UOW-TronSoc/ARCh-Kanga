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

Basestation operator UI/API migration is tracked separately in
[basestation.md](basestation.md).

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
2. Establish Kanga-wide definitions in `kanga_interfaces` and identify generic
   ODrive interfaces that must remain independent of Kanga.
3. Establish the reusable ODrive implementation in its own repository, record
   its provenance, and pin it beneath `src/vendor` through a `.repos` manifest.
4. Establish the Jetson GPIO motion-stop input and manual competition override,
   then define their software contract through `kanga_whs` and
   `kanga_interfaces`.
5. Migrate wheel mapping into `kanga_core_drive`, separating pure kinematics
   from ROS and ODrive glue.
6. Migrate the canonical rover-base model into `kanga_core_description`, then
   migrate each payload model into its payload description package.
7. Compose the complete model in `kanga_description` and add minimal core-only
   and whole-rover bringup.
8. Migrate utilities, autonomy, manipulator, excavator, science, and simulation
   in independently reviewed package slices.

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

The external ODrive repository must additionally document its upstream origin,
why it was forked, how it differs from upstream, and its compatibility policy.
