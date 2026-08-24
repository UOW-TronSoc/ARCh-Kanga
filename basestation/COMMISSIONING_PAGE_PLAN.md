# Motor Commissioning Page Plan

Status: **frontend mockup implemented; backend and hardware integration not
implemented**. Last reviewed 2026-08-25.

This document defines the next basestation feature slice: a protected browser
page for editing motor configuration, applying and saving it to ODrives, and
calibrating motors individually or as a controlled sequence.

The current `/commissioning` route is a browser-only preview. It uses mock
configs and simulated job timing so the layout and safety workflow can be
reviewed without a rover. Its banner explicitly states that it does not read or
write files, call ROS, or contact motors.

## Current state

The repository already has the lower-level core commissioning path:

- `commission_wheels` merges the shared motor config, drivetrain-profile
  limits, and one wheel-specific overlay before invoking `custom_odrive`.
- Save operations can already process several wheels sequentially from the CLI.
- Calibration is deliberately limited to one wheel per CLI invocation.
- `drive_manager` exposes per-wheel calibration Trigger services, and the
  basestation exposes a REST endpoint, but there is no commissioning page.

The current browser endpoint cannot complete a physical calibration because
the underlying CLI asks for off-ground confirmation on interactive stdin. There
is also no browser or ROS service for applying and saving one or all motor
configs. Only the four core wheel motors have real configs; Arm and Payload are
still package placeholders.

## Intended result

Complete the protected `/commissioning` page with:

- subsystem and motor selectors;
- raw-text editing for the shared config, each motor overlay, and a separate
  soft-limit config;
- file Save, Reset, and Restore Defaults controls;
- Apply & Save and Calibrate & Save for one motor;
- Save All and sequential Calibrate All actions; and
- an off-ground confirmation before every motor calibration.

Core is the first functional subsystem. Arm and Payload appear in the catalog
as unavailable placeholders until their motor IDs, namespaces, CAN interfaces,
and configs are implemented.

## Safety and configuration model

The checked-in `drivetrain_2025.yaml` remains unchanged and authoritative. Its
motor velocity and acceleration values are hardware hard caps, currently
22 turns/s and 80 turns/s².

A package-owned soft-limit config exposes motor velocity and velocity-ramp
acceleration through the same raw text editor as the motor configs. Both values
must be finite, positive, and no greater than the selected drivetrain hard
caps. The validated soft limits feed:

1. controller wheel-command limiting;
2. the drive-layer motor clamp; and
3. the final ODrive config generated during commissioning.

ODrive changes take effect after Save or Calibrate. Runtime ROS changes take
effect after the physical core stack is relaunched. The drivetrain profile is
not modified during operation and remains an independent ceiling at every
merge/load boundary.

The active soft-limit, shared, and per-wheel files remain package configs so
the existing `--symlink-install` workflow uses them directly and edits are
visible to Git. Immutable default copies preserve the settings present when
this feature is introduced.

## Implementation steps

### 1. Add soft limits and defaults

- Add the active soft-limit config with velocity and acceleration initially set
  to the current drivetrain hard caps.
- Add immutable default copies of the soft limits, shared motor config, and four
  wheel overlays.
- Add one loader that validates the soft values against the selected hard
  profile and derives the corresponding joint limits.
- Pass the same effective values into physical core controller, drive, and
  commissioning launch paths.
- Generate protected velocity and ramp assignments after the editable shared
  and per-wheel content so an overlay cannot bypass the limits.

### 2. Complete the lower-level commissioning operations

- Add an explicit `--off-ground-confirmed` commissioning flag. Manual CLI use
  without the flag retains the current interactive prompt.
- Keep the rule that one CLI invocation may calibrate only one motor.
- Add per-wheel save services to `drive_manager`.
- Change its calibration operation to apply the active config, run full
  calibration, and save the result to ODrive NVRAM.
- Put all core wheels in IDLE before an operation, retain the existing global
  drive-operation mutex, and leave commissioned motors disabled afterward.
- Always use the motor ROS namespace from the browser path. Do not add bench or
  “ROS is running” questionnaires; surface unavailable services as errors.

### 3. Add protected configuration and job APIs

Add a backend catalog with Core, Arm, and Payload entries. It is the only source
of paths, motor IDs, namespaces, operation order, and availability; API clients
must never supply arbitrary filesystem paths or shell arguments.

Planned HTTP interface:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/commissioning/catalog` | List subsystems, availability, and motors |
| `GET`, `PUT` | `/api/commissioning/configs/{subsystem}/{scope}` | Read or save shared/individual config content |
| `GET`, `PUT` | `/api/commissioning/soft-limits/{subsystem}` | Read or save the soft-limit file and report hard maxima |
| `POST` | `/api/commissioning/jobs` | Start a save or calibration job for ordered motor IDs |
| `GET` | `/api/commissioning/jobs/{job_id}` | Read queue and per-motor status |
| `POST` | `/api/commissioning/jobs/{job_id}/confirm` | Confirm the current motor is off the ground |
| `POST` | `/api/commissioning/jobs/{job_id}/cancel` | Cancel work that is waiting for confirmation |

When a PIN is configured, all commissioning reads and writes require the
existing authenticated session. The old per-wheel calibration REST route will
remain as a compatibility shim, but it must require explicit off-ground
acknowledgement and create a one-motor job.

Motor config saves must:

- use catalogued files only;
- be atomic and include a content revision/hash to reject stale writes;
- reject changes while a commissioning job is active;
- parse configs as declarative Python assignments;
- allow literals, supported enums, `math.inf`, injected limit constants, and
  `odrv.*` assignment targets only;
- reject imports, calls, control flow, and direct protected-limit overrides;
- require a literal non-empty serial in each motor overlay; and
- keep node IDs fixed to the launch mapping and serials unique.

Soft-limit saves must parse as YAML and validate both values against the
unchanged drivetrain-profile maxima before atomically replacing the file.

Only one commissioning job may be active. Save All and Calibrate All use the
established order `fl -> bl -> br -> fr` and stop at the first failure.
Calibration waits for a fresh confirmation before every motor. While a job is
active, the server rejects drive enable, drivestop release, config writes, and
non-zero browser drive commands; asserting drivestop and requesting IDLE remain
available.

Each motor reports one of `pending`, `awaiting_confirmation`, `running`,
`succeeded`, `failed`, or `cancelled`. Jobs are runtime state and do not need to
survive a basestation-server restart.

### 4. Build the page

- Add a protected navbar entry and `/commissioning` route.
- Populate subsystem and motor dropdowns from the backend catalog.
- Show Arm and Payload as unavailable and disable their controls.
- Provide the same simple monospace text editor for shared, individual, and
  soft-limit configuration files.
- Keep file persistence separate from hardware actions:
  - **Save File** writes the editor content.
  - **Reset** returns to the last server-saved content.
  - **Restore Defaults** stages the immutable baseline and still requires Save.
  - **Apply & Save Motor** and **Save All** write configs to ODrive NVRAM.
  - **Calibrate & Save Motor** and **Calibrate All** calibrate and persist.
- Warn before changing selection or leaving the page with unsaved edits.
- Before every calibration, name the exact motor in a modal; clicking
  **Confirm & Calibrate** is the fresh off-ground acknowledgement for that
  motor.
- Poll job status and display the ordered queue, current operation, results, and
  failure messages.

## Test plan

Automated coverage:

- soft-limit parsing, derived values, hard-cap rejection, and unchanged hard
  profile;
- config merge ordering and protected final assignments;
- config syntax/AST validation, serial uniqueness, fixed node IDs, defaults,
  atomic writes, and revision conflicts;
- authenticated catalog/config endpoints;
- individual and bulk job ordering, per-motor confirmation, cancellation,
  single-job locking, and stop-on-first-failure;
- drive/config operations rejected while commissioning is active; and
- frontend selector, editor, default/reset, validation, confirmation, and job
  progress behavior.

Run frontend lint/build and the affected colcon tests. Physical acceptance must
then verify individual save, sequential Save All, individual calibration,
four separate Calibrate All confirmations, NVRAM persistence, useful failure
reporting, and the new soft limits after core relaunch.

## Explicit boundaries

- No browser editing of the launch-time drivetrain-profile YAML.
- No live dynamic ROS parameter update; relaunch is required.
- No functional Arm or Payload commissioning until those domains provide their
  hardware contracts.
- No elaborate schema-driven motor-config GUI; the initial editor is text.
- No bench or ROS-running confirmation dialogs beyond operational error output.
