# NEXUS on ARCh-Kanga

The frontend in `frontend/` is the operator station. This directory's server and
`docker/Dockerfile.nexus` serve it on port **8001**. The ARCh basestation on
port 8000 is a separate service and is not modified.

`npm run dev` is the explicit demo. It uses fixtures and does not join ROS.
The container image sets `VITE_NEXUS_DATA_SOURCE=live`, so the page follows the
ROS graph and does not substitute demo values.

```bash
cd nexus/frontend
npm ci
npm test
npm run dev
```

Open <http://localhost:5173/rover> for the demo. Routes: `/login`, `/rover`,
`/launch`, `/cameras`, `/mapping`, `/systems`.

## Live station

```bash
./scripts/nexus_up.bash
```

The launch uses the workspace overlay, `basestation/fastdds_profile.xml`, and
the same host-network selection as the ARCh basestation. `GET /health` reports
`backend: available` when the process answered. `ros.initialized` is true only
after the ROS client inside that process starts.

The live page asks for the same 6-digit PIN as the ARCh basestation
(`basestation/data/.pin_hash`, set with `python3 basestation/scripts/set_pin.py`).
The cookie lasts for the browser session. Each tab still has its own control
socket: taking control from a second tab revokes the first, commands zero if
the rover was moving, asserts drivestop, and grants the new tab only after a
fresh stop sample. A second claim during that confirmation is rejected. Any
signed-in tab can assert stop. Releasing drivestop requires the holder, a
current observation, and confirmation.

`/ws/telemetry` carries drivestop, drivetrain mode (`closedLoop`: true, false,
or null), and wheel-joint velocities with freshness. The shell and drive panel
show **Unknown** before the first stop sample, **Asserted** or **Released**
while WHS is publishing, and **Stale** when a cached value remains after
contact is lost. Wheel samples are timestamped when they arrive and become
stale after one second without a new message.

`/ws/control` accepts `take`, `assert`, `release`, `arm`, `disarm`, `mode`,
`clear_errors`, and `drive`. Only the holder can arm, change mode, or clear
errors. Arming requests closed loop when the drivetrain is idle, then waits
for the observed mode. Disarming leaves that mode alone. While armed, the
holder sends `{type: "drive", x, yaw, scale}` at 20 Hz. The server publishes
`/core/cmd_vel` only for that holder, with drivestop released and closed loop
confirmed. The speed slider stays on the controlling tab: 0–90% reaches
`NEXUS_MAX_LINEAR_MPS` and `NEXUS_MAX_YAW_RAD_S` (default 0.3), and 90–100%
stays there. A 400 ms watchdog publishes zero and requires the operator to arm
again.

W/S command forward and reverse, A/D command yaw, Enter or gamepad B0 arms,
and Space or B1 asserts stop. Releasing a movement key always clears that
axis, including when focus has moved to the speed slider. Disconnecting the
tracked gamepad disarms input; another pad does not drive until the operator
arms again.

The rover model is Git LFS. Run `git lfs pull` on a clean checkout before
building the image.

## Gazebo check

Inside the ROS dev container (`./scripts/docker_shell.bash`):

```bash
source /opt/ros/humble/setup.bash
source /workspace/install/setup.bash
ros2 launch kanga_whs whs.launch.py
```

In a second shell in the same container:

```bash
ros2 launch kanga_sim core_simulation.launch.py
```

Then `./scripts/nexus_up.bash` and open <http://localhost:8001/rover>.

Verified against Gazebo: forward, reverse, yaw, neutral, and 45% versus 90%
scaling on `/core/cmd_vel`; wheel joints followed the sign and settled after a
stop; takeover from a second client ended on a zero command and asserted
drivestop; the 400 ms watchdog and a dropped control socket each published
zero. On the live page, W/S/A/D matched those commands, blur disarmed input,
and releasing W after focusing the speed slider sent a neutral frame. No
physical gamepad was attached. Disconnecting one pad while another remains is
covered by the frontend tests.
