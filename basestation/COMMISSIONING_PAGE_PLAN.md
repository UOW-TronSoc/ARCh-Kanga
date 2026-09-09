# Motor Commissioning Page Plan

Status: **backend Steps 1–3 implemented and rover-tested; Step 4a–4c frontend
config editing and save jobs implemented**. Last reviewed 2026-08-25.

This document defines the next basestation feature slice: a protected browser
page for editing motor configuration, applying and saving it to ODrives, and
calibrating motors individually or as a controlled sequence.

The `/commissioning` route now reads its subsystem and motor definitions from
the protected backend catalog. It loads the complete active and immutable
default content for shared, individual, and soft-limit configs. Editors now
support revision-protected writes, Reset, Restore Defaults, validation feedback,
and unsaved-change protection. Individual Save and sequential Save All now use
real backend jobs; calibration remains disabled until its final Step 4 slice.

## Current state

The repository already has the lower-level core commissioning path:

- `commission_wheels` merges the shared motor config, drivetrain-profile
  limits, and one wheel-specific overlay before invoking `custom_odrive`.
- Save operations can already process several wheels sequentially from the CLI.
- Calibration is deliberately limited to one wheel per CLI invocation.
- `drive_manager` exposes per-wheel save and calibration Trigger services. The
  calibration service applies config, calibrates, saves, and leaves the motor
  disabled.

The protected backend now supplies complete config/default content, validated
atomic writes, and ordered save/calibration jobs. The existing one-wheel route
also executes through that job coordinator and requires explicit off-ground
acknowledgement. The page now consumes the catalog, config read/write, job
creation, and job polling routes for save operations. It does not yet create or
confirm calibration jobs. Only the four core wheel motors have real configs;
Arm and Payload remain unavailable catalog entries.

## Intended result

Complete the protected `/commissioning` page with:

- subsystem and motor selectors;
- raw-text editing for the shared config, each motor overlay, and a separate
  soft-limit config;
- file Save, Reset, and Restore Defaults controls;
- Apply & Save and Calibrate & Save for one motor;
- Save All and sequential Calibrate All actions; and
- confirmation that the selected motor is free to spin before every calibration.

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

### 1. Add soft limits and defaults — implemented 2026-08-25

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

The active file is
`kanga_core_description/config/motor_limits/core.yaml`. The immutable limit
baseline is under `config/defaults/motor_limits/` in the same package; motor
config baselines are under `kanga_core_drive/config/defaults/motors/`.

### 2. Complete the lower-level commissioning operations — implemented and rover-tested 2026-08-25

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

### 3. Add protected configuration and job APIs — implemented 2026-08-25

Add a backend catalog with Core, Arm, and Payload entries. It is the only source
of paths, motor IDs, namespaces, operation order, and availability; API clients
must never supply arbitrary filesystem paths or shell arguments.

HTTP interface:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/commissioning/catalog` | List subsystems, availability, and motors |
| `GET`, `PUT` | `/api/commissioning/configs/{subsystem}/{scope}` | Read or save shared/individual config content |
| `GET`, `PUT` | `/api/commissioning/soft-limits/{subsystem}` | Read or save the soft-limit file and report hard maxima |
| `POST` | `/api/commissioning/jobs` | Start a save or calibration job for ordered motor IDs |
| `GET` | `/api/commissioning/jobs/{job_id}` | Read queue and per-motor status |
| `POST` | `/api/commissioning/jobs/{job_id}/confirm` | Confirm the current motor is free to spin |
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
established order `fl -> bl -> br -> fr`. A failure pauses the same active job
and offers Retry, Skip, or Cancel. Retry repeats the failed motor and then
continues the sequence after success. Skip is available only for multi-motor
sequences and advances to the next motor; Cancel ends the remaining sequence.
Calibration waits for a fresh free-to-spin confirmation before every motor. While a job is
active, the server rejects drive enable, drivestop release, config writes, and
non-zero browser drive commands; asserting drivestop and requesting IDLE remain
available. The backend temporarily releases drivestop around each save or
calibration service call and attempts to reassert it after every success,
failure, exception, or timeout. Calibration only reaches that release after the
operator confirms the current motor is free to spin. Both operations fail
closed if WHS cannot be reached to release the stop, and a failed stop
restoration is reported as a job failure requiring immediate operator
attention.

Each motor reports one of `pending`, `awaiting_confirmation`, `running`,
`succeeded`, `failed`, `skipped`, or `cancelled`. A calibration retry requires
another free-to-spin confirmation. Jobs are runtime state and do not need to
survive a basestation-server restart.

Implementation is split by responsibility under `basestation/server/`:

- `commissioning_catalog.py` owns the fixed Core/Arm/Payload catalog, permitted
  source-tree paths, motor order, ROS namespaces, and CAN node IDs;
- `commissioning_config.py` owns raw file reads, immutable-default content,
  SHA-256 revisions, declarative AST validation, soft-limit validation, and
  atomic replacement;
- `commissioning_jobs.py` owns the single active job, sequential operation
  state, per-motor calibration confirmation, and commissioning interlock; and
- `commissioning_api.py` exposes authenticated routes and keeps the legacy
  one-wheel calibration route as a job-backed compatibility path.

The server now rejects non-zero browser motion, drive enable, drivestop release,
error clearing, and config writes while a job is active. Asserting drivestop,
requesting IDLE, reading configs, and polling job state remain available. Step
3 is covered offline with injected ROS fakes and has been exercised on the
rover for individual Save, individual calibration, and sequential Save All.

### 4. Build the page — Steps 4a–4d implemented 2026-08-25

Completed in the catalog, loading, and file-editing slices:

- Use the protected navbar entry and `/commissioning` route.
- Populate subsystem and motor dropdowns from the backend catalog.
- Show Arm and Payload as unavailable and disable their controls.
- Load complete active and default shared, individual, and soft-limit files in
  parallel, with loading, failure, and retry feedback.
- Show active content in the existing monospace editor without permitting
  simulated jobs or hardware actions.
- Keep editable drafts separate from server-saved content, and protect them
  when changing motor, tab, subsystem, or leaving the browser page.
- Connect **Save File** with the loaded revision token, retain rejected drafts
  for correction, and refresh content and revision after successful writes.
- Connect **Reset** to the last server-saved content and **Restore Defaults** to
  the immutable baseline without saving it automatically.
- Connect individual **Save Motor** and sequential **Save All** to backend jobs,
  disabling them while configs are dirty or another operation is active.
- Poll save-job status and show catalog order, per-motor state and messages,
  overall completion, and stop-on-first-failure feedback.
- Before every calibration, ask whether the exact named motor is free to spin;
  clicking **Confirm & Calibrate** is the fresh acknowledgement for that motor.
- Connect individual **Calibrate & Save Motor** and sequential **Calibrate All**
  to backend jobs, including cancellation while awaiting confirmation.
- Keep drivestop asserted while a calibration waits, release it only for the
  confirmed motor operation, and reassert it before advancing or finishing.

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
