# Core rover readiness review and delivery plan

Reviewed 2026-09-09 against the repository source, package READMEs, migration
plans, installation guides, launch-manager plan, commissioning plan, and logs
plan. This is a source review and proposed implementation sequence, not a
hardware qualification report. No motors, services, or deployments were changed.

## Outcome and scope

On a Linux rover computer, boot the onboard runtime and basestation, open the
webpage from a second computer on the same LAN, deliberately start and enable
Core, drive it, inspect fresh feedback, and see the articulated rover model.
Recover predictably from lost input, network loss, process failure, and reboot.

Cameras are excluded. Payload implementations and autonomy are outside this
milestone; shared startup, diagnostics, telemetry, and commissioning mechanisms
should remain reusable by later payloads. ROO release and drive lock need an
explicit hardware requirement before they can be included in acceptance.

## Architecture assessment

Keep the existing package and runtime boundaries. A rewrite is unnecessary:

- `kanga_core_controller` owns chassis-to-wheel mapping and command shaping.
- `kanga_core_drive` owns wheel-to-motor conversion, limits, commissioning, and
  the physical ODrive boundary. Simulation substitutes that boundary.
- `kanga_core_description` owns geometry and validated drivetrain/limit inputs.
- The ESP32 firmware and host bridge own sensor transport; separate adapters
  produce suspension state and the preliminary body visualization transform.
- `kanga_whs` owns the whole-rover software motion inhibit.
- `kanga_launch_agent` owns allowlisted launch processes. FastAPI forwards
  lifecycle requests and serves the built React UI and WebSockets.
- Production uses `kanga-onboard` plus `basestation-server` on one host.
  Development substitutes `kanga-dev` for `kanga-onboard`.

The primary gaps are failure handling, deployment consistency, freshness,
hardware integration, and a supported remote visualization workflow.

## Review disposition

Updated after operator review on 2026-09-09. These three sections replace the
original P0/P1 ranking. Accepted test conditions and deferred hardware work are
not blockers for the current development scope. Original finding numbers are
retained for traceability.

### Accepted for current testing

| Finding | Disposition |
| --- | --- |
| 1 — Disabled watchdog | Intentional during commissioning tests to avoid interrupting the current workflow. Leave the configuration unchanged; watchdog changes are outside current work. |
| 3 — Direct drive endpoint access | The original finding concerns direct HTTP/WebSocket calls, not ordinary navigation around a configured PIN. The user accepts this direct-access behavior; endpoint hardening is outside current work. |
| 4 — CAN naming | The `can0` profile versus `can_core` host setup difference is accepted for the current setup. Do not make renaming or consolidation a prerequisite. |
| 8 — RViz | Use the operator computer's local `docker_shell`, launch the description/view locally, and consume rover joint states over LAN. Keep this workflow; optimization and browser embedding are outside the milestone. |

PIN source check: [App](../../basestation/frontend/src/App.jsx) wraps the operator
pages in [ProtectedRoute](../../basestation/frontend/src/components/ProtectedRoute/ProtectedRoute.jsx).
With a configured PIN and no authenticated session, the route redirects to
`/pin`; an auth-check failure also blocks entry. No normal initial-navigation
bypass of a configured PIN was found in this source review. When no PIN is
configured, the webpage deliberately allows entry. An existing authenticated
session also avoids another PIN prompt. Confirm those deployment conditions
when checking the actual webpage; no authentication implementation change is
currently scheduled.

### Follow-up to clarify and resolve

**6 — Stale feedback: distinguish last received from currently measured.**

[Telemetry state](../../basestation/server/ros.py) caches wheel velocities,
motor state, body state, and WHS state. For example, a wheel reports CLOSED_LOOP
and a velocity, then its feedback publisher disappears while the basestation
continues running. The server can keep sending the old values over a healthy
WebSocket, so the browser connection is live but that wheel measurement is old.
`whs_online()` also accepts a previously received stop value as evidence of
liveness. This is a display/state-inference issue, separate from adding the
full Startup health monitor deferred in finding 5.

Proposed bounded fix, pending discussion: timestamp receipt per feedback source;
return its age and freshness; render expired values as “stale — last received
N seconds ago” or unknown. Do not continue inferring current CLOSED_LOOP from
expired motor feedback. The UI may retain last-known values if clearly labelled.
Do not introduce new automatic motion-stop policy as part of this display fix.

**9 — Commissioning: qualify interruption and recovery of the existing workflow.**

Save, calibration, per-wheel confirmation, Retry/Skip/Cancel, and a browser
motion interlock already exist in [jobs](../../basestation/server/commissioning_jobs.py)
and the [page](../../basestation/frontend/src/pages/Commissioning/Commissioning.jsx).
This is not a request to reimplement them or a claim that normal commissioning
is broken. Specific follow-up cases are:

- Start FL calibration, then restart the basestation container. Jobs and the
  interlock are in memory and do not survive that restart. The ROS-side operation
  may still be running. Determine how the restarted UI reports the uncertain
  outcome and prevents an overlapping operation until state is reconciled.
- A save/calibration service response times out. That does not establish whether
  the motor operation completed or stopped. Verify that Retry does not overlap
  a still-running operation, and that restoration failures remain visible.
- Stop/restart Core from Startup while a commissioning job is active. Verify
  rejection or a coordinated outcome, so the job cannot silently continue
  against a replaced process.
- Edit operating limits and save a motor. Already running ROS nodes may retain
  their launch-time limits. Make the distinction between edited, loaded, and
  motor-saved settings clear, including any required relaunch.

The runtime already attempts to reassert drivestop after ordinary operation
success/failure/timeout. A killed process cannot be assumed to execute that
cleanup. These are validation scenarios and potential follow-up fixes, not
reproduced hardware failures. Their implementation scope remains to be agreed.

### Deferred pending hardware or later integration

| Finding | Dependency / next decision |
| --- | --- |
| 2 — Physical stop input | Wait for mechanical mounting before GPIO integration and validation. |
| 5 — Startup health monitoring | Later work; retain independent process state and `NOT_CHECKED` health for now. |
| 7 — Battery | Blocked on BMS hardware decisions. No driver/protocol or replacement plan is selected; do not prescribe one yet. |

The `/core` namespace is established for Core-owned ROS objects. Future payloads
use their own namespace; implementing their migrations is outside this change.
Diagnostics navigation and LAN validation remain current work.

## 1. ROS naming contract

Each payload or subsystem owns its ROS namespace. Core uses `/core`. Core nodes
use relative topic and service names; launch files assign the `/core` namespace
with `PushRosNamespace`. Parameter files continue to load by node name
(`wheel_command_mapper`, `drive_manager`, …) and are unaffected by the namespace
prefix.

| Interface | Contract |
| --- | --- |
| Chassis command | `/core/cmd_vel` |
| Wheel vector and feedback | `/core/wheel_joint_velocity_command`, `/core/wheel_joint_states` |
| Drive operations | `/core/drive_manager/{set_closed_loop,clear_errors,save_*,calibrate_*}` |
| ODrive nodes/topics/services | `/core/wheel_{fl,bl,br,fr}/...` |
| Core sensor state | `/core/suspension_joint_states`, `/core/diff_bar_angle`, `/core/imu/data`, `/core/body/pose`, `/core/body/twist` |
| Simulation odometry | `/core/odom` (simulation only; not a TF authority) |
| Battery | Core-owned `/core/battery/...` when implemented, with a documented message and freshness contract |
| Whole-rover stop | Preserve `/drivestop` and `/whs_node/set_drivestop` |
| Shared infrastructure | Preserve `/tf`, `/tf_static`, `/rosout`, `/clock`, launch-agent services, SocketCAN transport (`from_can_bus` / `to_can_bus`), and deliberate whole-rover model/joint-state aggregation on `/joint_states` and `/robot_description` |

Shared exceptions stay at the root namespace on purpose:

- `kanga_whs` publishes `/drivestop` and serves `/whs_node/set_drivestop`.
- `ros2_socketcan` (`socket_can_receiver`, `socket_can_sender`) and the launch
  agent remain un-namespaced on `/from_can_bus` and `/to_can_bus`. Core CAN
  consumers such as `core_can_bridge` live under `/core` but remap
  `from_can_bus` → `/from_can_bus` at launch. Wheel ODrives use the host
  SocketCAN interface directly and do not use those ROS topics.
- `joint_state_publisher` and `robot_state_publisher` aggregate the rover model at `/joint_states` and `/robot_description`, subscribing to `/core/wheel_joint_states` and `/core/suspension_joint_states`.
- Joint names (`wheel_fl_joint`, …) and TF frame IDs (`base_link`, `body_origin`, …) are unchanged; ROS namespaces do not namespace frame IDs.

Physical and simulation contracts were migrated together. The basestation maps
Core names centrally in `basestation/server/ros.py`; browser components do not
construct ROS names. Deploy matching ROS and basestation versions together.

Acceptance: compare physical and simulated ROS graphs; all Core-specific objects
use `/core`; global stop, model aggregation, startup detection, commissioning,
and shared TF connections still resolve correctly. Hardware-specific differences
between physical ODrive feedback and simulation stubs remain expected.

## 2. Control follow-up scope

Leave the accepted watchdog settings and direct-endpoint access unchanged.
Defer physical-switch work until mounting is ready. Discuss the bounded
freshness and commissioning cases above before expanding their implementation.

Additional source-review suggestions, not newly approved requirements, are
checking command takeover/reconnect behavior and tuning controller limits.
Preserve existing behavior unless a concrete issue is established or the user
selects that work. In particular, do not turn deferred Startup health checks
into a prerequisite through lifecycle or telemetry work.

## 3. Make deployment and LAN operation repeatable

The base HTTP plumbing already exists: FastAPI binds `0.0.0.0:8000`, Compose
exposes the service, and [frontend configuration](../../basestation/frontend/src/config.js)
uses the browser's origin for HTTP and WebSockets.

Target topology:

```text
Operator computer                         Rover Linux computer
Browser -- HTTP/WebSockets, port 8000 --> basestation-server
                                         | ROS, same host/domain
                                         kanga-onboard / launch agent
                                         | managed Core launch
                                         CAN + ESP32 + motors (other hardware deferred)
RViz desktop -- ROS discovery/topics ---> model + TF + state
```

- Document the current CAN selection, ROS domain, network interface, session
  secret, and speed settings without changing accepted CAN naming. Pass required values
  into containers: a host environment variable is not automatically forwarded
  by the current Compose environment list.
- Verify the selected CAN interface and bitrate on the target using the current
  setup. Enhanced missing-hardware reporting in Startup is deferred.
- Build ROS artifacts on the target architecture or through a documented target
  build; do not copy a laptop's compiled `install/` onto a different architecture.
- Prebuild runtime images and frontend, verify vendor pins and persistent config
  paths, then test offline boot with no dependency downloads.
- Verify configured-PIN webpage navigation from a fresh browser session.
  Direct HTTP/WebSocket endpoint hardening is explicitly outside current scope.
- Document a stable LAN address/hostname and required host firewall access.
  Validate the actual operator OS/browser, including keyboard and gamepad use
  over the chosen HTTP/HTTPS origin.
- Cold boot into an accessible UI with Core stopped; start Core deliberately
  from Startup. Maintain this existing lifecycle unless autostart is explicitly
  selected later. Retire the legacy services after parity testing.

Acceptance: from a second LAN computer, log in, start Core, release/arm, drive,
receive feedback, use diagnostics, disconnect/reconnect safely, and repeat after
a cold reboot without an interactive shell on the rover.

## 4. Validate the existing operator-side RViz workflow

Use the operator computer's local `docker_shell` with matching workspace/model
assets, launch the description/view there, and subscribe to the rover's joint
states over LAN. No browser viewer or optimization is required now.

Validate discovery, ROS domain, container networking, topic names, and actual
wheel/suspension updates on the two computers. The current
[description launch](../../src/kanga_core/kanga_core_description/launch/view_core_2026.launch.py)
starts local robot-state publishing and defaults to joint sliders. Select live
joint-state input rather than sliders for this workflow. Because rover bringup
also publishes model TF and aggregated joint states, document/remap the local
visualization publishers so they do not compete on shared topics. This is a
small launch-configuration integration check, not a visualization redesign.

Joint states provide articulation; body orientation additionally requires the
rover's body transform (or a local adapter reading body pose). Use the existing
`body_origin` convention rather than implying measured global position.

Acceptance: the operator opens the local container/view and sees real wheel and
suspension movement across the LAN. Confirm orientation separately if included.
Late join and reconnect work. Further optimization is deferred.

## 5. Current implementation sequence

1. Move Commissioning, Logs, and Terminal under **Diagnostics**, keeping Drive
   and Startup top level and preserving routes. Check keyboard/mobile use,
   active selection, and direct page reloads.
2. Validate same-host operation and second-computer LAN browser control/feedback,
   then the operator-side Docker/RViz workflow described above.
3. Resolve the scope of findings 6 and 9, then implement only the agreed fixes.
4. Reconcile the docs with the accepted setup and record the actual deployment
   procedure, versions, settings, and test results.

Watchdog changes, physical-switch integration, endpoint hardening, CAN renaming,
Startup health monitoring, BMS implementation, and RViz optimization are not
required gates for this sequence.

Use existing backend unittest coverage and relevant ROS package tests for code
changes, plus the documented frontend build/lint scripts. Add behavioral tests
only for agreed changes. Two-computer networking and actual commissioning
recovery need integration evidence; this document records a source review,
not completed runtime/hardware qualification.

## Documentation reconciliation

Update these alongside the implementation they describe:

- [Architecture](README.md): speed mapping and acceleration shaping are no
  longer wholly future work; describe the remaining controller limits/mode work.
- [Basestation migration](../migration/basestation.md) and
  [installation guide](../install/basestation.md): commissioning is no longer
  just a frontend mockup.
- [Basestation README](../../basestation/README.md): calibration controls exist
  in source; replace the disabled-controls statement with validation status.
- [Core bringup README](../../src/kanga_core/kanga_core_bringup/README.md): remove
  the outdated closing instruction to add the already included ESP32 bridge.
- [Controller README](../../src/kanga_core/kanga_core_controller/README.md):
  distinguish C++ defaults from the lower acceleration values in shipped YAML.
- [Rover checklist](../testing/rover_session_checklist.md): replace historical
  feature-branch/merge instructions, old rates, and outdated interface names
  with the accepted deployment procedure and agreed validation cases.
- [Launch-manager plan](../launch-manager/README.md) and
  [logs plan](../logging/README.md): promote only implemented and verified slices;
  keep software completion and target-hardware qualification separate.
