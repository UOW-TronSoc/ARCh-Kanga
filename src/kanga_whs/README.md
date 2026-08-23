# kanga_whs

Software whole-robot motion-stop for Kanga. This package owns the **command**
published on `/drivestop`. It does not cut motor power and is not a hardwired
or safety-rated e-stop.

## Model

One control API, one output:

```text
  CLI / future GPIO watcher / GUI / …
           |
           v
  ~/set_drivestop   (std_srvs/SetBool)
           |
        whs_node
           |
           v
      /drivestop    (std_msgs/Bool, reliable + transient_local)
           |
           v
  consumers (custom_odrive, …) latch and enforce locally
```

- `data: true` → request stop (inhibit motion)
- `data: false` → allow motion again

GPIO, joystick, and GUI are **clients of the service**, not separate inputs
inside this package. When a GPIO watcher exists, it should call
`~/set_drivestop` the same way a human does from the CLI.

Motor latching, IDLE requests, and per-axis enable stay in each consumer
(e.g. `custom_odrive`). This node only remembers and publishes the last
software-stop command so late subscribers still see it.

WHS starts with drivestop asserted by default. Startup and node restart
therefore require an explicit release before motion can be enabled. The
`initial_drivestop` parameter exists for controlled development situations,
but physical-rover bringup should keep its default value of `true`.

No custom `kanga_interfaces` messages. No joy/polarity logic here. Battery-based
stop and power interruption are out of scope for this iteration.

## Who triggers stop

`kanga_whs` does **not** subscribe to battery, drive, or other domain topics to
decide when to stop. Domain packages (or CLI/GUI/future GPIO watchers) decide
and call `~/set_drivestop`. This package only owns publishing `/drivestop`.

If several automatic sources later need to assert stop, do not use bare
last-writer-wins `SetBool` clears. Prefer named inhibit sources ORed inside
WHS, or a small policy node that is the sole caller of `set_drivestop`.

## GPIO stub

`include/kanga_whs/gpio_stop_input.hpp` is a placeholder for a future Jetson
GPIO reader. It is not wired into `whs_node` yet.

## Run

```bash
ros2 launch kanga_whs whs.launch.py

# Development-only startup override. Do not use for normal rover bringup.
ros2 launch kanga_whs whs.launch.py initial_drivestop:=false

# assert stop
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: true}"

# clear stop (allow)
ros2 service call /whs_node/set_drivestop std_srvs/srv/SetBool "{data: false}"

ros2 topic echo /drivestop
```

## Tests (no hardware)

Inside the kanga-dev container (after vendor import + build):

```bash
colcon test --packages-select kanga_whs
colcon test-result --verbose
```

The test verifies the default fail-safe startup state, transient-local delivery
to a late subscriber, service-routed state changes, and the explicit
development startup override.
