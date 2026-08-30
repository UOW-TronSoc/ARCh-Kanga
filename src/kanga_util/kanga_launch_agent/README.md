# Kanga launch agent

This package runs in the onboard ROS container and is the only component that
owns rover launch processes. The basestation communicates with it over typed
ROS services; it never sends a shell command and does not require access to the
Docker socket.

Start the agent as part of onboard container boot:

```bash
./scripts/onboard_up.bash
```

For a sourced, container-internal diagnostic it can also be launched directly
with `ros2 launch kanga_launch_agent launch_agent.launch.py`.

Runtime usage:

- Development/simulation: run the agent inside the persistent `kanga-dev`
  container. Additional `docker_shell.bash` terminals enter that same container.
- Rover production: systemd starts the agent inside `kanga-onboard`.
- Never run `kanga-dev` and `kanga-onboard` as simultaneous ROS runtimes.
- `basestation_up.bash` starts only the separate web/API container.

The current allowlist contains one physical profile, `core`, which starts the
fixed `kanga_core_bringup/rover.launch.py` command. The agent detects the Core
sentinel nodes before starting it and reports an externally started stack as
`UNMANAGED`. It will never stop or restart an unmanaged stack.

To add a subsystem later, add one reviewed `LaunchProfile` to
`kanga_launch_agent/profiles.py` and append it to `PROFILES`. Its command,
arguments, and sentinel nodes remain code-owned. No new ROS service or manager
implementation is needed.

Services:

- `/launch_manager/list` (`kanga_interfaces/srv/ListManagedLaunches`)
- `/launch_manager/change` (`kanga_interfaces/srv/ChangeManagedLaunch`)

The basestation maps these services to `GET /api/systems` and the three fixed
`POST /api/systems/{system_id}/{start|stop|restart}` routes. HTTP callers cannot
provide a process command or launch argument.

Simulation is intentionally not an owned profile yet. A locally started sim is
visible through the same ROS graph and remains externally managed.
