# Basestation Ground-Up Redesign (Co-located with Robot)

Status: **ready to start** — plan agreed 2026-07-18; updated 2026-08-23
against what actually landed on `develop`: WHS/`/drivestop` authority, core
drive + controller (with its own `/cmd_vel` timeout — the carried requirement
is satisfied), the ESP32 CAN bridge, a Gazebo core simulation, and health-stub
services under `basestation/`. Camera details expanded in
[CAMERAS.md](CAMERAS.md).

Phase 1: replace the four-service basestation stack (Django + two FastAPI apps
+ Vite dev server) with a single FastAPI backend embedding one rclpy node,
WebSocket teleop/telemetry with dead-man stop, a statically built frontend,
and one bringup path that is the same in dev and on the rover. Phase 2:
replace the JPEG-polling camera pipeline with MediaMTX + hardware H.264 +
WebRTC, with exactly one owner per video device.

## Use cases this is built around

Operators (competition / field):

- Open one browser on a laptop and drive/control the rover over Wi-Fi.
- See live robot state (battery, arm, science) without juggling refreshes.
- Keep the competition UI (drive, arm + 3D, science, cameras, checklist, logs,
  PIN) — rebuild plumbing, keep the product.
- Video that stays usable at range (less lag / freezing on a bad link).
- If the laptop, tab, or link drops mid-drive, the rover must stop — not keep
  rolling.

Developers (club members):

- Work on robot software with a simple Docker setup (minimal host install
  pain).
- Optionally start the operator UI against that same robot software to test
  control end-to-end.
- Same story on a laptop in dev and on the rover in prod.
- No messy multi-app stack just to try something.

Team / product:

- One ongoing codebase for rover + operator UI; migrate carefully — keep
  known-good behaviour first, replace pieces when validated.
- The operator UI uses the ROS interfaces and topic contracts defined on the
  robot (`src/`) side — one source of truth, never a parallel copy of
  message/topic definitions.

## Context needed to work on this from any machine

Source repositories:

- **This repo (target):** https://github.com/UOW-TronSoc/ARCh-Kanga
- **Legacy basestation (porting reference for UI + REST endpoints):**
  https://github.com/UOW-TronSoc/ARCh2026-BaseStation — running live on the
  rover at `/home/kanga/kanga/basestation`.
- **Legacy robot code (topic-contract reference):** `ARCH2026-Kanga` at the
  commit pinned in the repo root README; the live (possibly diverged) copy is
  the rover's workspace at `/home/kanga/kanga/kanga`.

**Sequencing: rover code merges in first — the core half of that is done.**
As of 2026-08-23 (`develop`), the core rover stack is implemented in `src/`
and builds via Path A: `kanga_interfaces` (now only `WheelVelocityCommand`,
`BatteryInfo`, `BmsStatus` — ODrive contracts such as `ControllerStatus`,
`ODriveStatus`, and `AxisState.srv` moved to the vendored `custom_odrive`
repo), `kanga_whs` (software motion-stop authority), the `kanga_core_*`
packages (drive, controller, description, bringup, microcontroller CAN
bridge), and a Gazebo core simulation. The manipulator, science, excavator,
and camera packages are still architecture placeholders — no arm or science
topics or interfaces exist in this tree yet; they arrive as separate payload
migration slices. Phase 1 therefore targets the live core contract first and
ports the arm/science UI pages only when those payloads land.

### Operator contract (as implemented in `src/` on `develop`, 2026-08-23)

Live once `kanga_core_bringup/launch/core.launch.py` (rover) or
`kanga_sim/launch/core_simulation.launch.py` (dev, Gazebo) is up. Snapshot
only — the code in `src/` stays the source of truth.

| Name | Type | Direction |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | UI -> robot |
| `/drivestop` | `std_msgs/Bool` | robot -> UI |
| `/whs_node/set_drivestop` | `std_srvs/SetBool` (srv) | UI -> robot |
| `/drive_manager/set_closed_loop` | `std_srvs/SetBool` (srv) | UI -> robot |
| `/drive_manager/clear_errors` | `std_srvs/Trigger` (srv) | UI -> robot |
| `/drive_manager/calibrate_{fl,bl,br,fr}` | `std_srvs/Trigger` (srv) | UI -> robot |
| `/wheel_joint_states` | `sensor_msgs/JointState` | robot -> UI |
| `/suspension_joint_states` | `sensor_msgs/JointState` | robot -> UI |
| `/diff_bar_angle` | `std_msgs/Float64` | robot -> UI |
| `/body/pose` | `geometry_msgs/PoseWithCovarianceStamped` | robot -> UI |
| `/body/twist` | `geometry_msgs/TwistWithCovarianceStamped` | robot -> UI |
| `/imu/data` | `sensor_msgs/Imu` | robot -> UI (physical only) |
| `/wheel_{fl,bl,br,fr}/controller_status` | `custom_odrive/ControllerStatus` | robot -> UI |
| `/wheel_{fl,bl,br,fr}/odrive_status` | `custom_odrive/ODriveStatus` | robot -> UI |

Contract rules the server must respect:

- `/cmd_vel` is now in physical units (linear m/s, yaw rad/s). The operator
  0-100% speed setting is a UI-level scale mapped onto configurable maximum
  chassis speeds (see "Drive command and limit model" in
  [docs/architecture/README.md](../docs/architecture/README.md)); the legacy
  arbitrary `MAX_TWIST = 20` does not carry over.
- **Never publish `/drivestop`** — `whs_node` is its sole publisher; the UI
  changes it only through `/whs_node/set_drivestop`, and subscribes with
  reliable + transient_local QoS to latch current state. WHS starts asserted
  (fail-closed), and clearing it does not re-enter closed loop.
- Arming sequence: clear drivestop -> `set_closed_loop true` -> stream
  `/cmd_vel`. Stop and closed-loop are independent states; the UI must show
  both.
- QoS: `controller_status` is best-effort; `/body/*` and `/imu/data` are
  SensorDataQoS.

Not live yet (do not block Phase 1 on these):

- **Battery** — `BatteryInfo` / `BmsStatus` messages exist but
  `kanga_core_battery` is a stub; the legacy `/battery/*` topics are not
  published in this tree yet.
- **Arm / science** — the legacy 2026 contract (`/kanga_arm/joint_control`,
  `kanga_arm/ee_state_control`, `kanga_arm/control_mode_joint`,
  `kanga_science/*`) is not implemented here; it returns (possibly revised)
  with the `kanga_manipulator_*` / `kanga_science_*` migration slices.

Rover-only items (everything else runs on a laptop via Path A + the core
simulation): real CAN hardware (`can_core` — so per-wheel ODrive telemetry,
`/imu/data`, and battery), real cameras (IP cams at `10.0.0.5`/`10.0.0.6`,
`/dev/video*`), and final parity verification against the legacy stack.

## What stays the same

The operator still opens a browser on a separate laptop, so a web stack on the
rover is still the right shape. The React UI (drive, arm + 3D URDF, science,
cameras, checklist, logs, PIN) is worth keeping — it gets rebuilt, not
rewritten.

## Ground-up design

```mermaid
flowchart LR
    Browser["Operator browser (laptop over Wi-Fi)"]
    Browser -->|"HTTP + WebSocket, single port :8000"| Server

    subgraph rover [Rover computer or dev machine]
        Server["basestation-server container (one FastAPI app)"]
        Server --- Static["Built React frontend (static files)"]
        Server --- Node["Single rclpy node"]
        Node <-->|"DDS (host networking, shared ROS_DOMAIN_ID)"| Robot["Robot stack from src/ (Path A container or native)"]
    end
```

The legacy four-service stack on the current rover
(`/home/kanga/kanga/basestation`: Django :8000, drive FastAPI :8080, arm
FastAPI :8001, Vite :3000) stays untouched and running as the fallback until
this stack reaches parity — cameras included. Nothing needs to be carved out
of it mid-migration.

### 1. One backend service instead of three

A single FastAPI app (new `basestation/server/`) replaces Django (:8000), drive
FastAPI (:8080), and arm FastAPI (:8001). It embeds **one** `rclpy` node on a
background executor thread with all publishers/subscribers:

- **WebSocket `/ws/control`** — gamepad drive (`/cmd_vel`, physical units,
  with the 0-100% speed scale applied against configured chassis limits) and,
  once the manipulator migration lands, arm commands. Replaces HTTP POST per
  gamepad tick — the current UI fires 10-100 POSTs/sec
  (10 ms interval on ArmControlCompact, 50 ms on Dashboard) with no ordering
  guarantee, so on a Wi-Fi hiccup a stale "full speed" command can be applied
  after a newer "stop". Browser still polls the gamepad (~50 Hz — the Gamepad
  API is polling-only, that part is fine and universal) but sends at a fixed
  20-30 Hz with change-detection and a keepalive over one ordered WebSocket.
  **Dead-man stop:** the server publishes a zero Twist if no message arrives
  within ~300-500 ms, covering frozen tabs, dropped Wi-Fi, and closed laptops.
  **Eyes off = hands off (UI rule, found in field-testing 2026-08-23):** the
  client must drop all input and send a stop whenever the tab loses focus or
  visibility — a backgrounded tab never receives the `keyup` for a held key
  (it looks held forever) and browsers throttle its timers to ~1/s, which
  otherwise drips stale "full speed" frames that repeatedly re-arm the
  dead-man. A hidden tab may only ever send zeros. The React UI (task 7)
  must keep this behaviour.
- **Carried requirement: satisfied.** The rebuilt drive stack has its own
  timeouts: `wheel_command_mapper` streams zero wheel commands after 0.5 s of
  `/cmd_vel` silence (`cmd_vel_timeout_s` in
  `kanga_core_controller/config/controller.yaml`), `wheel_actuator` stops
  publishing motor commands on a stale joint stream, and the sim drive
  boundary drops to IDLE on silence. The server-side dead-man stays as the
  second layer of defence, and WHS `/drivestop` sits above both as the
  operator-facing stop authority.
- **WebSocket `/ws/telemetry`** — pushes `/drivestop` state, wheel and
  suspension joint states, `/body/pose` / `/body/twist`, per-wheel
  `controller_status` / `odrive_status`, and — once their packages land —
  battery and `kanga_science/*` at a fixed rate. Replaces frontend REST
  polling and removes the need for Redis caching entirely.
- **REST** — one-shot actions only: drivestop set/clear
  (`/whs_node/set_drivestop`), closed-loop enter/exit, error clearing, and
  per-wheel calibration (`/drive_manager/*` — the "basestation motor page"
  expected by [docs/migration/core_drive.md](../docs/migration/core_drive.md)),
  science controls, checklist, logs, PIN. The legacy NIR servo / "Roo
  release" GPIO scripts are superseded by `kanga_core_microcontroller`
  (servo and ROO interfaces over CAN) once that firmware lands.
- **Drivestop is a first-class UI element**: current `/drivestop` and
  closed-loop state always visible, one prominent stop control, and the WHS
  manual override (an exceptional mid-competition recovery mechanism) clearly
  indicated when active — required by the WHS contract in
  [docs/architecture/README.md](../docs/architecture/README.md).

**Cameras: handled in Phase 2 (see [CAMERAS.md](CAMERAS.md)).** During Phase 1
camera feeds keep coming from the legacy stack on the rover; the new server
does not touch video. In Phase 2 MediaMTX takes over feed by feed.

**Topic contracts come from `src/`.** The server imports `kanga_interfaces`
(and topic names) from the bind-mounted workspace `install/` — the same
overlay the robot nodes use — via the existing container entrypoint that
sources `/opt/ros/humble` then `/workspace/install/setup.bash`
([docker-entrypoint.bash](docker-entrypoint.bash)). No message or topic
definitions are ever duplicated on the basestation side.

**Why rclpy and not rclcpp:** the rover-side packages are rclcpp, but ROS 2 is
language-agnostic over DDS (`kanga_interfaces` generates both bindings), so
mixing is the normal pattern. The basestation node only moves small messages at
low rates (~30-60 Hz commands, few-Hz telemetry); the ~0.5 ms rclpy overhead
per message is negligible next to the Wi-Fi hop to the operator laptop. rclcpp
would matter for per-frame image work (deferred) but would make the
HTTP/WebSocket server side far more work. If a hot path emerges later, move
just that piece into a small rclcpp node.

### 2. Frontend built, not dev-served

React frontend built with `vite build` in a multi-stage Docker build (node
stage builds, output copied into the Python image) and served as static files
by the same FastAPI app. Everything is same-origin on one port, so the legacy
`config.js` per-port URL builders and CORS/`ALLOWED_HOSTS` IP hardcoding
(`10.0.0.1`/`10.0.0.2`) disappear. For frontend iteration, `vite dev` on the
host with a proxy to `:8000` still works — it just isn't the deployed shape.

### 3. Docker-first bringup — same shape in dev and prod

The existing dev workflows stay exactly as documented in the repo README; the
operator stack just collapses from four compose services to one.

- **Path A (robot / ROS work)** — unchanged:
  `docker compose -f docker/compose.dev.yaml build`, `./scripts/docker_shell.bash`,
  then `./scripts/build_workspace.bash` + `source install/setup.bash` inside.
- **Path B (operator UI)** — `./scripts/basestation_up.bash` /
  `basestation_down.bash`, unchanged commands, but
  [docker/compose.basestation.yaml](../docker/compose.basestation.yaml) shrinks
  to a single `basestation-server` service (plus MediaMTX in Phase 2). Same
  guard (refuses to start until `install/setup.bash` exists), same host
  networking / `ipc: host` / `ROS_DOMAIN_ID` env, same bind-mounted
  `/workspace`, same entrypoint sourcing pattern. UI moves from :3000 to
  `http://localhost:8000/`. The `Dockerfile.basestation-frontend` nginx
  scaffold and the three uvicorn stub services retire. The server's DDS
  transport is UDP-only ([fastdds_profile.xml](fastdds_profile.xml)):
  Fast DDS shared memory silently fails between processes owned by
  different users (dev container vs this container, or systemd rover
  processes vs this container), and loopback UDP costs nothing at our
  message sizes.
- **Path C (end-to-end control test)** — unchanged story, now with a real
  target instead of mocks: in Path A run either `kanga_core_bringup`
  (hardware) or `ros2 launch kanga_sim core_simulation.launch.py` (Gazebo
  core sim — same operator contract, checked by
  `core_simulation_contract_check`); run Path B beside it. Both are
  host-network DDS participants on the same `ROS_DOMAIN_ID`, so the full
  drive loop (clear drivestop -> closed loop -> `/cmd_vel` -> wheels moving
  in Gazebo) is testable on a laptop with no hardware.
- **Rover (prod)**: the same compose file with `restart: unless-stopped` (or a
  thin systemd unit that runs `docker compose -f docker/compose.basestation.yaml up`),
  after the robot bringup. No separate prod stack to maintain — dev and prod
  differ only in what starts it.
- Keep `ROS_LOCALHOST_ONLY=0` so Foxglove/`ros2` CLI on the operator laptop
  still see the graph.

### 4. Not migrated from the legacy basestation

- Django project, django-redis, Redis dependency
- The duplicate arm bridge (legacy had Django `/api/arm-*` *and* FastAPI
  :8001 — one implementation in the new server)
- `supervisord.conf`, `startup.sh`, and the legacy repo's own docker-compose
  (two-computer artifacts; `kanga_wip/docker/` is the replacement)
- `robot_controller/` mocks + `process_manager` (:8081) — the Gazebo core
  simulation (`kanga_sim`) now fills the "UI dev without hardware" role with
  the real contract instead of mocks

### Considered and rejected

- **rosbridge/roslibjs (browser talks ROS directly):** less backend code, but
  PIN gating, RTSP proxying, GPIO, checklists and logs still need a server, so
  it doesn't actually remove a tier — and it exposes the whole ROS graph to the
  browser.
- **Replace UI with Foxglove:** loses the purpose-built competition UI.

## Review feedback and responses

The original basestation author reviewed this plan and raised two objections:
(1) don't replace reliable REST with WebSockets — you'll forever be chasing
connection drops; (2) skip WebRTC for video — use plain TCP or RTSP instead.
Both come from real field experience; the responses below are why the plan
holds, and are recorded here so the reasoning lives with the decisions.

### REST vs WebSocket for control

Only the high-rate, safety-critical streams (drive/arm commands + telemetry)
move to WS. One-shot actions (science, checklist, logs, PIN, servo) stay REST.
It is not a wholesale switch.

The switch is not just for the dead-man. Four reasons:

1. **Ordering.** The legacy ~60 POST/sec drive loop
   ([Dashboard.jsx](https://github.com/UOW-TronSoc/ARCh2026-BaseStation) sends
   at a 16 ms interval) has no ordering guarantee — after a Wi-Fi stall a stale
   "full speed" can be applied after a newer "stop", and the 3 s command
   timeout means dozens of stale requests can still be in flight when the link
   recovers. One ordered WS stream makes out-of-order application structurally
   impossible, with zero code dedicated to preventing it.
2. **Telemetry deletes code.** WS push lets us drop Redis/django-redis
   entirely — it only exists to cache the "latest value" for REST pollers.
   Fewer moving parts, not more.
3. **Overhead.** 60 req/sec of full HTTP headers + middleware (the legacy
   stack even runs request-logging middleware per command POST) vs small
   frames on one open socket — less contention with video on a bad link.
4. **Dead-man.** The server can only tell "link dead" from "operator idle" if
   there is a live session with a liveness signal.

The real comparison is not "simple REST vs complex WS". To make REST hit the
same safety bar you need hand-rolled heartbeats, sequence numbers, timeout
tracking, and Redis — *more* custom code with subtler failure modes (cache
staleness, poller races). The simple REST version is the one running today,
which is the unsafe one.

The "chasing drops forever" pain comes from proxies, load balancers, and NAT —
none of which exist here (one browser <-> one FastAPI process, one LAN hop,
same origin). To keep connection management near-zero maintenance for whoever
takes the project over next, the plan commits to:

- Native `WebSocket` API only — no socket.io or wrapper libraries.
- Plain JSON, a handful of documented message types, no acks or custom framing.
- One fixed reconnect policy (fixed ~1 s retry on close), connection state
  shown prominently in the UI. **Newest tab wins** (added 2026-08-23 after a
  forgotten tab silently locked out the operator in testing): a new control
  connection bumps the previous holder with a dedicated close code; a bumped
  tab shows "another tab took control" and a retake button instead of
  auto-reconnecting, so tabs can never steal control back and forth.
- **Drive-enable resets to OFF on any reconnect** — the operator must
  deliberately re-arm, so a reconnect bug can never cause motion.
- Refresh always fully recovers — the server holds no session state worth
  preserving (PIN in a cookie, telemetry re-pushes immediately).

Failure direction is safe by design: a dropped control link degrades to "rover
stops + disconnected badge", never to invisible misbehaviour.

### WebRTC vs plain TCP/RTSP for video

WebRTC is genuinely painful — but that pain is NAT traversal (STUN/TURN/SDP/
signaling), which does not apply on a flat LAN with known IPs, and MediaMTX
handles the signaling (WHEP) anyway. Nobody hand-rolls `RTCPeerConnection`
plumbing.

Two blockers on the proposed alternative:

- **Browsers cannot play RTSP** (no `<video src="rtsp://...">`), so a
  server-side component must repackage the stream for the browser regardless —
  that component is exactly what MediaMTX is.
- **TCP is the actual cause of today's freezing-at-range**: retransmits stall
  the stream and latency snowballs. MJPEG (current) and RTSP-over-TCP share
  this failure mode. WebRTC rides UDP and drops frames instead of accumulating
  delay — which is the "usable at range" requirement.

RTSP is still used — as the *ingest* protocol (IP cams passthrough, GStreamer
publish into MediaMTX). The only disagreement is the last hop to the browser.
Rollout is per-camera, IP cams first (passthrough, near-zero risk), with old
MJPEG kept as fallback until each feed is verified. If WebRTC fights us on the
real rover network, the fallback is MediaMTX's LL-HLS output from the same
server (trivial in-browser, no signaling), not RTSP.

### One open question carried back to the reviewer

The sharpest version of the transport objection is **UDP for control**
(unreliable datagrams — fresh-but-lossy beats ordered-but-stale for teleop,
since a TCP-based WS can still head-of-line-block newer commands behind a
retransmit). The plan uses WS as a safe middle ground because the dead-man
makes a stalled channel degrade to "stop". If unreliable datagrams (UDP or an
unreliable WebRTC data channel) are worth the extra complexity, that remains
open for discussion.

## Phase 2: Camera pipeline redesign

Full diagnosis, hardware comparison (Orin NX vs Nano, encoder boxes), and
design details live in [CAMERAS.md](CAMERAS.md). Summary:

```mermaid
flowchart LR
    subgraph rover2 [Rover computer]
        MTX["MediaMTX (WebRTC/WHEP out)"]
        GST["GStreamer per USB cam: v4l2src -> encoder"]
        ROSDRV["ROS drivers: realsense2_camera, zed wrapper (own the device, publish depth)"]
        BRIDGE["Bridge node: color topic -> encoder"]
        GST -->|RTSP publish| MTX
        ROSDRV --> BRIDGE
        BRIDGE -->|RTSP publish| MTX
    end
    IPCams2["IP cams 10.0.0.5/6"] -->|"RTSP pull (H.264 passthrough, no transcode)"| MTX
    MTX -->|"WebRTC ~100-300ms"| Browser2["Operator browser video elements (WHEP)"]
```

- One owner per `/dev/video*` device, declared in a single camera config.
- Encoder element configurable per camera: `nvv4l2h264enc` (NVENC, Orin NX) or
  `x264enc` (software, Orin Nano — no NVENC exists on that module).
- Frontend swaps JPEG polling for WHEP `<video>` elements.
- Rollout is per-camera, IP cams first (passthrough, zero risk), old MJPEG
  endpoints kept as fallback until every feed is verified.

## Migration approach

- Phase 1: build the new server in this repo while the legacy stack keeps
  running on the rover, reach feature parity page by page (validated via
  Path C against the Gazebo core simulation on a dev machine), then deploy
  the compose stack to the rover and retire the legacy services. The React
  components mostly survive — only the API/WS client layer (`config.js` and
  axios calls) changes.
- Phase 2: bring up MediaMTX beside the legacy camera endpoints and migrate
  camera by camera, keeping the old MJPEG feeds as fallback until every feed
  is verified on WebRTC.
- Migration principle from the repo README applies throughout: preserve
  known-working behaviour first, validate it, only then remove the old path.

## Task list

### Prerequisite status (2026-08-23)

The core half is done: interfaces, WHS, core drive/controller/bringup, the
CAN bridge, and the Gazebo core simulation build via Path A on `develop`.
Manipulator, science, and camera packages remain placeholders — tasks marked
*(payload-gated)* below wait on those migration slices and must not block the
rest.

### Phase 1

1. Scaffold `basestation/server/` FastAPI app with a single rclpy node on an
   executor thread, plus static file serving. Reuse the existing entrypoint
   sourcing pattern so `kanga_interfaces` and topic contracts come from the
   bind-mounted `install/`. **Done 2026-08-23** — `/health` + latched
   `/drivestop` subscription verified in the basestation container (also
   fixed `docker-entrypoint.bash`: `set -u` broke sourcing ROS `setup.bash`,
   which had silently blocked all Path B services).
2. Collapse `docker/compose.basestation.yaml` to one `basestation-server`
   service (multi-stage Dockerfile: node stage runs `vite build`, Python stage
   serves it); retire the nginx frontend scaffold and the three uvicorn stubs;
   keep `basestation_up.bash` / `basestation_down.bash` working unchanged
   (Path B), including the `install/` guard. **Done 2026-08-23** — one
   service on :8000, stubs and nginx scaffold removed, Path B verified
   end-to-end. The node/vite build stage joins the Dockerfile when the React
   frontend is migrated (task 7); until then the server serves the
   placeholder page.
3. Implement `/ws/control`: gamepad input sent at fixed 20-30 Hz with
   change-detection and keepalive; the 0-100% speed scale mapped onto
   configured chassis limits to produce a physical-unit `/cmd_vel`;
   server-side dead-man publishes zero Twist on ~300-500 ms silence. Arm
   command topics *(payload-gated)*. **Done 2026-08-23** (drive only) —
   browser sends 20 Hz JSON frames; the node's own 20 Hz timer does all
   `/cmd_vel` publishing, doubles as the dead-man (0.4 s, verified), and
   sends a clean stop on disconnect; one tab holds control at a time;
   limits via `BASESTATION_MAX_LINEAR_MPS` / `BASESTATION_MAX_YAW_RAD_S`
   (defaults 0.3 m/s, 1.0 rad/s).
4. Implement `/ws/telemetry`: `/drivestop`, wheel + suspension joint states,
   `/body/pose` / `/body/twist`, per-wheel `controller_status` /
   `odrive_status` pushed at a fixed rate; add battery and science topics
   when their packages land. **Done 2026-08-23** — 5 Hz push on
   `/ws/telemetry` (any number of listener tabs); page shows drivestop,
   wheel rad/s, body yaw and speed from the stream instead of polling
   `/health`. Motor status subscribes when `custom_odrive` is present
   (physical rover); sim skips it gracefully.
5. Drive management REST + UI: drivestop set/clear with latched state
   display, `set_closed_loop`, `clear_errors`, per-wheel calibrate (the
   "motor page" from the core drive migration doc), with the arming sequence
   (clear stop -> closed loop -> drive) made explicit in the UI. **Done
   2026-08-23** — REST under `/api/drive/*`; test page Drive setup panel
   (release/assert stop, closed loop/idle, clear errors). Per-wheel calibrate
   endpoint exists (`POST /api/drive/calibrate/{wheel}`) but no UI button yet
   — add with the real motor page in task 7.
6. Port the remaining operator REST actions from the legacy Django app:
   logs, PIN; science controls *(payload-gated)*; NIR servo / Roo release wait
   for `kanga_core_microcontroller` firmware instead of porting the GPIO
   scripts. **Done 2026-08-23** — `/api/auth-status/`, `/api/pin-verify/`
   (file-backed PBKDF2 hash, session cookie), `/api/django-logs/`,
   `/api/list-logs/`, `/api/get-log/<file>/`; `scripts/set_pin.py`. Competition
   checklists dropped — not needed.
7. Migrate the React UI (drive + 3D URDF, logs, PIN; arm and
   science pages *(payload-gated)*) onto the same-origin API/WS client;
   verify Path C end-to-end against the Gazebo core simulation, then against
   physical core bringup.
8. Rover deployment: same compose file started on boot (restart policy or a
   thin systemd wrapper), brought up after robot bringup; legacy stack retired
   from the rover once parity is verified.

Carried requirement: **done** — the drive stack zeroes the wheels after 0.5 s
of `/cmd_vel` silence (`cmd_vel_timeout_s` in `kanga_core_controller`); the
server dead-man is the second layer, WHS `/drivestop` the third.

### Phase 2 (cameras — see CAMERAS.md)

1. Add MediaMTX as a service in `docker/compose.basestation.yaml` (official
   image, host networking); RTSP pull for IP cams 10.0.0.5/6 with WebRTC
   (WHEP) output; verify latency vs direct view.
2. Per-USB-camera GStreamer pipeline (`v4l2src -> encoder -> rtspclientsink`)
   into MediaMTX, encoder element configurable, driven by one camera-ownership
   config.
3. D435i/ZED2i via ROS drivers (depth stays in ROS); bridge color image topic
   -> encoder -> MediaMTX for the webpage.
4. Replace `VideoFeedCard` JPEG polling with a WHEP WebRTC `<video>` element;
   camera list from MediaMTX paths.
5. Retire the legacy camera path entirely: the old Django camera endpoints on
   the rover and the `kanga_cameras`-style publisher (keep a topic tee only
   where robot code needs frames).
