# Basestation logs

Canonical plan for the operator Logs page. One page, several log sources,
selected from a folder-style tree. Independent of System Startup and
`kanga_launch_agent`. It can land on its own branch from `develop`.

## Status

**Stages 1–5 implemented.** `/logs` is a folder tree (ROS `/rosout` live,
HTTP uvicorn poll, Docker and launch stdout stubs). Namespace folders
split logger names on `.` and `/` and start collapsed. Track remaining
work in [Implementation record](#implementation-record). **Current
limits** of the ROS page are in [Limitations (today)](#limitations-today).
**Docker follow** is specified but not built:
[Future work: Docker / supervisor](#future-work-docker--supervisor).

## Goal

A **single** `/logs` page. The main pane shows one selected stream. A
folder-style tree (expandable dropdowns) picks what to view. First slice
wires **ROS** and **HTTP**. **Docker** and **launch stdout** sit in the tree
as later leaves so they can be added without a new page.

Record continuously on the server. Paint in the browser only while Logs is
open. Save downloads the current view.

## Source tree

The tree is the navigator, not a dump of every line into one list. Click a
folder to expand; click a leaf to view that stream. Filters in the pane
apply only to the selected leaf.

```text
Logs
  ROS
    All
    /drive_manager
    /wheel_bl/can_node
    …
  HTTP
    uvicorn
  Docker          (later)
  Launch stdout   (later)
```

| Leaf | This slice | Stream |
| --- | --- | --- |
| `ROS / All` and `ROS / <graph name>` | Yes | `/rosout` |
| `HTTP / uvicorn` | Yes | Existing `log_buffer.py` / `/api/django-logs/` |
| `Docker / …` | Tree stub only | `docker logs` later |
| `Launch stdout / …` | Tree stub only | owned `ros2 launch` stdout later |

ROS children under `ROS` come from `/rosout` logger names, not launch
process labels (`custom_odrive_node-13`). ROS 2 writes those names with
dots (`wheel_bl.can_node`), which is the same namespace as
`/wheel_bl/can_node`. The tree splits on `.` and `/`, so those wheels
group under `wheel_bl` automatically. Click a namespace to show every
logger under that prefix; click a leaf for that one name.

Selecting `ROS / All` shows every `/rosout` line (still subject to the
level floor).

Do not merge ROS and HTTP rows in one table. Switching leaves switches the
pane.

```text
ROS nodes --> /rosout --> always-on ring --> /ws/logs (while Logs is open)
HTTP/uvicorn --> log_buffer.py --> snapshot or poll while HTTP leaf is selected
Docker / stdout --> not wired; tree rows disabled or “coming later”
```

## When the page updates

Log volume is high. Drive and other routes must not re-render log lines.

- Server rings **always** record their streams, including while nobody is on
  Logs. Leaving the page does not drop recording.
- The browser **connects only while `/logs` is mounted.** Navigating to Drive
  closes sockets, so React holds no log state. Opening Logs again snapshots
  the selected leaf, then live-updates that leaf only.
- Do not open `/ws/logs` unless the selected leaf is ROS. HTTP can use the
  existing REST buffer until a second socket is justified.
- On the page, batch DOM updates (animation frame or about 100–200 ms),
  pause, and cap to the ring size. Auto-scroll only if already at the bottom.

No `localStorage` and no app-wide log context.

## Pane filters

Apply to the **selected leaf** only.

| Filter | ROS | HTTP |
| --- | --- | --- |
| Level floor | DEBUG … FATAL, default **WARN+** | DEBUG … CRITICAL, default **WARNING+** |
| Graph-name substring (in addition to the tree) | Optional extra box | Not used |

The tree is the primary ROS name filter. A substring box can still find
`can_node` across names when `ROS / All` is selected.

## Save

**Save** downloads the **currently visible** (selected leaf + filters) lines
as UTF-8 `.txt`, one record per line, filename like
`kanga-logs-ros-YYYYMMDD-HHMMSS.txt` or `kanga-logs-http-…`. Browser
download only; not a rover log directory.

## ROS stream

ROS 2 aggregates on `/rosout` (`rcl_interfaces/msg/Log`). The basestation
FastAPI process already participates on the same `ROS_DOMAIN_ID` as
`kanga-dev` or `kanga-onboard`. Subscribe and window that topic.

Start Core, simulation, or extra shells however you like. If it publishes
`/rosout`, it appears under `ROS`. Basestation `get_logger()` calls appear
there too once the ROS node is running.

## HTTP stream

Reuse [`basestation/server/log_buffer.py`](../../basestation/server/log_buffer.py)
(uvicorn access and error). Do not parse these as graph names. The HTTP
leaf is a separate view of that ring.

## Later leaves

**Docker** and **Launch stdout** are still stubs. Decisions for the next
slice (rover topology, what to keep vs drop, when *not* to add launch
pipes) are in
[Future work: Docker / supervisor](#future-work-docker--supervisor).

## Implementation sketch

### Server

- Subscribe to `/rosout` on the existing node in
  [`basestation/server/ros.py`](../../basestation/server/ros.py), matching
  rosout QoS (reliable, transient local, keep-last).
- ROS ring of about 2000–5000 records: `seq`, stamp, level, `name`, `msg`.
- `/ws/logs`: snapshot on connect, then push. Connect only from Logs and
  only while the ROS leaf is selected. PIN follows other operator sockets.
- HTTP continues via `/api/django-logs/` (or a thin rename later). Optional
  `GET /api/logs` for the ROS snapshot in tests.

Drop the fake Django / Arm / Drive service pills and the CSV rover-file UI.

### Page

Replace
[`basestation/frontend/src/pages/LogViewer/LogViewer.jsx`](../../basestation/frontend/src/pages/LogViewer/LogViewer.jsx):

- Left (or top) folder tree: ROS (expandable names), HTTP, Docker stub,
  Launch stdout stub
- Main pane for the selected leaf: lines, level floor, pause, Save
- `/ws/logs` only while mounted and ROS is selected
- Style like other operator pages (dark panel, existing tokens)

### Tests

- ROS ring accepts a fake `Log` and serializes level, name, and message
- Level mapping (rcl DEBUG=10 through FATAL=50) is stable for the UI
- HTTP leaf still reads the existing uvicorn buffer

## Deployment

Path A plus Path B: persistent `kanga-dev` (or `kanga-onboard`) and
`basestation-server` on the same `ROS_DOMAIN_ID`. This slice does not need
launch-manager code.

## Implementation record

A checked item means the code and its hardware-independent tests exist. Later
stages must not be started until the previous stage is checked.

### Stage 1 — ROS ring and `/ws/logs`

- [x] Subscribe to `/rosout` on the existing node in `basestation/server/ros.py`
      (rosout QoS: reliable, transient local, keep-last).
- [x] In-memory ring (~2000–5000): `seq`, stamp, level, `name`, `msg`.
- [x] `/ws/logs` sends a snapshot on connect, then new records.
- [x] PIN session applies when a PIN is configured.
- [x] Unit tests: fake `Log` serializes; rcl DEBUG=10 … FATAL=50 mapping is
      stable.

### Stage 2 — Single page and folder tree

- [x] Replace `LogViewer.jsx`; drop CSV rover files, Django/Arm/Drive pills,
      and host CPU/GPU/thermal.
- [x] Folder tree: ROS, HTTP, Docker (stub), Launch stdout (stub).
- [x] ROS expands to `All` plus a flat list of graph names (empty until Stage
      3). HTTP expands to `uvicorn`.
- [x] Docker and Launch stdout leaves are visible but disabled / “coming
      later”.
- [x] Main pane shows the selected leaf only (no combined table).
- [x] `/ws/logs` is not opened unless this page is mounted.

### Stage 3 — ROS leaf (live)

- [x] Open `/ws/logs` only while the selected leaf is under ROS; close it when
      switching to HTTP or leaving `/logs`.
- [x] Populate ROS tree children from names seen in the buffer.
- [x] `ROS / All` and `ROS / <name>` filter the pane; optional substring box
      when All is selected.
- [x] Level floor, default WARN+.
- [x] Batch DOM updates (~100–200 ms); pause; cap to ring size; auto-scroll
      only when already at the bottom.
- [x] Drive (and other routes) do not hold log state or a logs socket.

### Stage 4 — HTTP leaf

- [x] `HTTP / uvicorn` reads the existing `log_buffer.py` ring
      (`/api/django-logs/` is fine).
- [x] Level floor mapped onto Python logging levels.
- [x] Poll or snapshot only while this leaf is selected; do not use `/ws/logs`.
- [x] Test that the HTTP leaf still returns uvicorn lines.

### Stage 5 — Save

- [x] Save downloads the currently visible lines (leaf + filters) as UTF-8
      `.txt`.
- [x] Filename distinguishes source, e.g. `kanga-logs-ros-YYYYMMDD-HHMMSS.txt`
      or `kanga-logs-http-…`.

### Stage 6 — Close-out

- [x] Lint the changed frontend files; run the new/updated basestation tests.
- [x] Set Status at the top of this file to implemented for Stages 1–5.
- [ ] Confirm Drive stays smooth with Core (or sim) logging while Logs is
      closed, then that Logs shows the buffered snapshot on open.

### Later (not built)

- [x] Nested ROS folders by namespace from logger names (`wheel_bl.can_node`).
- [ ] Docker leaf: `docker logs` of the **onboard** container from
      `basestation-server` on the same host. Spec:
      [Future work](#future-work-docker--supervisor).
- [ ] Launch stdout leaf — **only if** Docker follow misses docker_shell or
      Startup. Do not build pipes just in case.
- [ ] ROS **topic** view on the webpage (`ros2 topic echo` / hz for a
      selected name). Not `/rosout`. High-rate topics would need their own
      ring, leaf, and rate cap so Drive stays smooth. Spec later if pulled
      in.

## Limitations (today)

The ROS leaf is not a substitute for the `ros2 launch` terminal.

**`/rosout` can miss crash-on-start.** rcl prints to stderr *and* publishes
`/rosout`. A node that logs ERROR then exits 255 (typical
`custom_odrive_node` + missing `can_core`) often delivers the console line
in docker_shell and **not** a DDS sample. Which wheels appear under ROS is
a race, not a filter. Example that was in the terminal but not on `/logs`:

```text
[ERROR] […] [core.wheel_fl.can_node]: Failed to initialize socket can interface: can_core
```

**The ROS tree is not `ros2 node list`.** Children are loggers seen in the
current ring. A quiet or dead node never appears. Oldest lines drop off
(~4000). Names are rcl logger names (`core.wheel_fl.can_node`), not launch
labels (`custom_odrive_node-6`).

**Launch’s own lines are not on ROS:** `process has died`,
`process started`, lifecycle `TRANSITION_CONFIGURE`, raw prints such as
`Failed to get interface index`. Those are stdout/stderr of `ros2 launch`.

**Startup is not a health view.** `kanga_launch_agent` still `Popen`s
`ros2 launch` and treats the **parent** process as Running after a grace
timer. Child `can_node`s can all be dead while Startup shows Running.
`last_error` is parent-exit text, not the ioctl line.

**HTTP default WARNING+** hides uvicorn access/startup, which is mostly
INFO. That is uvicorn, not a mapping bug.

**Stage 6 hardware confirm** (Drive smooth with Logs closed) is still
unticked.

Do not merge ROS, HTTP, and Docker into one table. Do not scrape
`basestation-server` docker logs for the HTTP leaf (uvicorn already has
`log_buffer.py`).

## Future work: Docker / supervisor

Everything that prints Core (docker_shell or Startup) runs **on the rover**
in the onboard/`kanga-dev` container. `basestation-server` is another
container on the **same host**. The webpage is only a client.

On that host, `docker logs` of the onboard container is the supervisor
stream for **both** start paths, if stdout is the container’s main log:

| How Core started | Docker leaf |
| --- | --- |
| docker_shell / `compose run` (shell is PID 1) then `ros2 launch` | Usually yes |
| Startup; launch agent in that container; children inherit stdout (current `Popen`, no pipes) | Same log |
| `docker exec` into a long-lived onboard container | Often **empty** — exec TTY is not `docker logs` |

Do not assume a second Docker daemon on the operator’s viewer machine.

### What to show (decided)

`process has died` is not enough to diagnose. Keep the rcl ERROR/WARN
lines even if they also appear under ROS. Duplicates are accepted.

- **Keep** rcl-shaped `[WARN|WARNING|ERROR|FATAL] [stamp] [logger]: …`
  (optional `[custom_odrive_node-6]` prefix).
- **Drop** rcl-shaped `DEBUG` and `INFO` so the pane is not every chatter
  line twice.
- **Keep** `process has died`, `process started`, lifecycle `TRANSITION_*`.
- **Keep** non-rcl prints (`Failed to get interface index`).

No `/rosout` ring lookup and no delay. Living-node WARNs may show on both
leaves.

### How to build it

- Record always on basestation; paint only while the Docker leaf is
  selected. Do not send these frames on `/ws/logs`.
- Mount the host Docker socket read-only on `basestation-server`
  ([`docker/compose.basestation.yaml`](../../docker/compose.basestation.yaml)).
  Follow `docker logs -f --timestamps <name>`. Configurable name, default
  `kanga-dev`. Missing container: empty pane + status, not a crash. May
  need the Docker CLI (or SDK) in the basestation image.
- Ring ~4000: `seq`, stamp, launch label if present, `msg`. Pause + Save
  `kanga-logs-docker-….txt`.
- Tests: keep an FL CAN ERROR rcl line; keep `process has died`; drop a
  sample rcl INFO.
- Rough size: 500–900 new lines plus 150–250 edits. Same order of work as
  the `/rosout` leaf. No launch-agent change in this slice.

**Launch stdout** (tee `Popen` pipes, publish over ROS) stays a stub
unless Docker follow fails in the field (no socket, or exec sessions
invisible). Do not build it just in case.

Out of scope for that slice: combining ROS+Docker into one table, docker
logs of `basestation-server`, health probes, replacing `Popen` with
in-process launch events.

## Out of scope for Stages 1–6

- Implementing Docker or launch-stdout capture (tree stubs only)
- Mixing all sources into one combined table
- Launch-profile prefixes or Core vs Manipulator chips
- Persistent server-side log files or the old CSV rover directory
- Host CPU / GPU / thermal widgets
- Health checks
- Live `ros2 topic echo` (or equivalent) in `/logs`. The ROS leaf is
  logger lines on `/rosout` only. A topic inspector would be a new leaf
  or page, not an extra column on the log stream.
