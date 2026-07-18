# Basestation migration

## Status

Scaffold only in this repository: Docker compose, health-stub services, and
docs. Real operator application code has not been migrated yet.

## Primary reference (application code)

```text
Local tree (current systemd stack):
  /home/kanga/kanga/basestation/basestationproject/

Live ports today:
  Django          8000
  Arm FastAPI     8001
  cmd_vel FastAPI 8080
  Vite frontend   3000
```

The old basestation also contained unused `process_manager/` and
`robot_controller/` trees (Docker `:8081` script manager). Do **not** migrate
those in early PRs.

## Provenance notes from the live stack

- `fastapi_server` publishes `geometry_msgs/Twist` on `/cmd_vel`
- `arm_fastapi_app` publishes arm joint / EE / mode topics and subscribes
  feedback
- `backendapi/views.py` runs `rclpy` nodes (science bridge, arm, battery) and
  imports `kanga_interfaces.msg` types such as `BatteryInfo` / `BmsStatus` when
  available

## Replacement order (after scaffold)

1. Replace `basestation/fastapi_server` stub with real cmd_vel FastAPI.
2. Replace `basestation/arm_fastapi_app` stub with real arm FastAPI.
3. Replace `basestation/django_app` stub with real Django (keep port 8000).
4. Replace nginx scaffold frontend with the Vite app on port 3000.
5. Add a prod-oriented compose profile for Orin when behaviour matches the
   current systemd stack.

Validate each slice against ROS nodes started from Path A
(`./scripts/docker_shell.bash`) on the same `ROS_DOMAIN_ID`.

## Interface rule

`src/kanga_interfaces` is the single source of truth. Basestation containers
must source `/workspace/install/setup.bash`; do not vendor generated Python
message modules under `basestation/`.
