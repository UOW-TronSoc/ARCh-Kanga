# kanga_core_microcontroller

Firmware and host-side ROS integration for the rover-base ESP32. Keeping both
ends of the device protocol in one package makes protocol changes easy to
review, but does not mean they should become one monolithic program.

## Owns

- The `.ino` firmware that runs on the rover-base microcontroller
- Its CAN protocol and host-side translation where required
- ROO release and drive-lock commands and status
- Differential-bar encoder sampling and raw count reporting
- Host-side publication of IMU, encoder, and other typed ROS state interfaces
  carried by the ESP32 CAN protocol
- Testable conversion of differential-bar angle into suspension joint state
- Core internal status reported by the microcontroller

## Boundary

Payload-specific firmware belongs to its payload package. The ESP32 firmware
reports raw encoder values and timing without embedding rover geometry. A
separate executable in this package owns the suspension kinematics so that the
equation remains independent of CAN framing and can be tested offline. Link TF
generation remains with `robot_state_publisher` or a dedicated estimator. The
GPIO motion-stop input belongs to `kanga_whs`, not this firmware.

## Rover validation status

The current sensing and visualization scope was validated on the physical
rover on 2026-08-23:

- Differential-bar encoder feedback passed through the ESP32, CAN bridge, and
  suspension kinematics, and the resulting visualization matched the rover's
  real differential-bar and suspension movement.
- IMU orientation, axis directions, and units produced a body visualization
  that matched the rover's observed orientation.
- Together these checks validate the implemented ESP32 -> CAN -> ROS -> TF /
  JointState visualization path for the current merge scope.

This validation does not promote the preliminary body pose to production
odometry or closed-loop control feedback; the covariance, freshness, drift,
and sensor-fusion requirements described below still apply to those future
uses.

Auxiliary servo control is explicitly deferred and is not an acceptance
requirement for this merge. The current firmware can decode and log the
reserved servo command frame, but its PWM pins are unassigned and commands are
not applied to hardware. Servo topic ownership, limits, failsafe behaviour,
pin assignment, actuation, and hardware validation will be added as a separate
reviewed feature.

## Source layout

```text
kanga_core_microcontroller/
├── firmware/
│   └── kanga_core_esp32/       Arduino sketch and firmware-only .h/.cpp files
├── include/                    Shared and host-side C++ headers (CAN protocol)
├── src/
│   ├── core_can_bridge.cpp     CAN-to-ROS executable
│   ├── body_pose_tf_*.cpp      Visualization-only pose-to-TF adapter
│   └── suspension_*.cpp        Suspension mapping executable and library
├── config/                     Host-side ROS parameters and launch-time frame constants
├── launch/                     Host-side ROS launch files
└── test/                       Host-side unit and protocol tests
```

The proposed firmware sketch path is
`firmware/kanga_core_esp32/kanga_core_esp32.ino`; Arduino requires the sketch
and its containing directory to have the same base name. Supporting firmware
code can live beside it as `.h` and `.cpp` files.

### Responsibility split

| Part | Owns | Does not own |
|---|---|---|
| ESP32 firmware | Sensor sampling, encoder counts, IMU access, CAN framing, device timestamps and status; reserved inactive servo command decoding | ROS, TF, URDF geometry, suspension kinematics, or production servo actuation |
| ESP32 CAN bridge | SocketCAN transport, protocol validation, unit conversion/calibration, and typed ROS state topics | Robot geometry, TF, or the deferred servo control interface |
| Body pose TF node | Mirror an already-processed `body/pose` sample into a development TF | Pose estimation, sensor fusion, twist processing, or production odometry |
| Suspension state node | Diff-bar angle limits and the replaceable diff-bar-to-suspension equation | CAN framing, encoder drivers, or TF |

The intended state path is:

```text
diff-bar encoder → ESP32 firmware → CAN → ESP32 CAN bridge
  → calibrated diff_bar_angle → suspension_joint_state_publisher
  → suspension_joint_states → robot_state_publisher integration
```

The IMU path shares the firmware and CAN bridge with the reserved servo frame,
but not the suspension kinematics executable. Servo actuation remains deferred.
This keeps hardware reconnection or protocol changes separate from the
mechanism equation and makes that equation testable without an ESP32.

### Who publishes body state

`body/pose`, `body/twist`, and `diff_bar_angle` describe the rover rather than
the thing measuring it, so nothing in those messages is CAN-specific. On the
real rover `core_can_bridge` fills them in from ESP32 frames; a simulator can
publish the same topics instead and everything downstream —
`body_pose_tf_broadcaster` and `suspension_joint_state_publisher` — keeps
working untouched. Only one source may run at a time, or the two end up
fighting over the same topics.

Whoever publishes the pose has to stamp it with the frame the TF broadcaster is
expecting, or the broadcaster quietly drops every sample. That is why
`body_origin` and `base_link` live in `config/core_frames.py`
and are applied as launch-argument defaults instead of being written into each
node's parameter file: overriding a frame in bringup then moves the publisher
and the subscriber together.

## IMU feedback

The likely device is a BNO086, but competition operation treats it as a
six-axis accelerometer/gyroscope IMU. The ESP32 firmware must enable the BNO08X
**Game Rotation Vector** and must not enable the ordinary Rotation Vector,
Geomagnetic Rotation Vector, or any other output that incorporates the
magnetometer. Magnetometer calibration and magnetic-field reports should also
remain disabled so this is an explicit firmware property rather than only a
ROS-topic convention. See the manufacturer's
[BNO08X datasheet](https://www.ceva-ip.com/wp-content/uploads/BNO080_085-Datasheet.pdf),
section 2.2.

The ESP32 must issue the SH-2 calibration command to disable magnetometer
calibration after every BNO086 reset. The setting does not persist, and the
datasheet states that magnetometer calibration is enabled by default for most
interface modes. No magnetometer, Rotation Vector, or Geomagnetic Rotation
Vector report should be configured.

The BNO08X Game Rotation Vector is already a quaternion derived from the
accelerometer and gyroscope. Roll and pitch are gravity-referenced; yaw has no
absolute heading reference and will drift. Quaternion generation, tare/reference
handling, and BNO086 axis processing belong on the ESP32.

The ESP32 CAN bridge only decodes the finished body state and publishes
the pose/twist contract below. If the firmware also transmits acceleration and
raw IMU diagnostics, the bridge may additionally publish them as
`sensor_msgs/msg/Imu`; it must not repeat sensor fusion or Euler-angle processing
on the ROS computer. The bridge still owns the mechanical axis and unit
conversion needed to satisfy ROS body/ENU conventions, unless the firmware
protocol is explicitly defined to transmit those conventions already.

A later visualization or fused-estimation package may consume that standard IMU
topic. An IMU provides orientation and inertial measurements, not translational
position; the authoritative `odom -> base_link` transform remains the
responsibility of a fused estimator.

### Planned body feedback contract

The ESP32 calculates the body pose and twist and transmits the finished
values over CAN. The CAN bridge publishes both samples without
repeating sensor fusion:

| Topic | Type | Frame contract |
|---|---|---|
| `body/pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Pose of `base_link` relative to `body_origin`; `header.frame_id=body_origin` |
| `body/twist` | `geometry_msgs/msg/TwistWithCovarianceStamped` | Body linear and angular velocity expressed in `base_link`; `header.frame_id=base_link` |

Both messages must carry the same ESP32 measurement timestamp. Position is in
metres, orientation is an `x/y/z/w` quaternion, linear velocity is in m/s, and
angular velocity is in rad/s. The firmware protocol should transmit quaternion
orientation directly so the ROS computer does not reconstruct it from Euler
angles.

If the ESP32 has only BNO086 data, pose position and twist linear velocity are
not observable reliably. Publish zeros for those fields only when their
covariance marks them as unavailable/highly uncertain; do not present
double-integrated accelerometer values as measured position or velocity. A
future external or fused estimator may replace those components.

`body_origin` is deliberately not `odom`. It is an arbitrary ESP32
tare/startup reference suitable for diagnostics and visualization. The CAN
bridge must not publish `odom -> base_link`; ownership of that transform remains
with the future localisation estimator.

### Preliminary pose visualization

`body_pose_tf_broadcaster` subscribes to `body/pose` and broadcasts its
orientation as `body_origin -> base_link`. Translation is always ignored and
forced to zero: BNO086 Game Rotation Vector has no reliable position, and this
adapter must not invent one. It does not subscribe to `body/twist`, calculate
pose, integrate velocity, or perform IMU processing. It rejects unexpected
parent frames and badly formed quaternions; the small final quaternion
normalization is only TF input hygiene. While waiting for its first valid pose
after launch, it publishes an identity `body_origin -> base_link` transform. It
then republishes the latest accepted pose at 10 Hz so a one-shot test message
remains visible and the dynamic TF does not expire. This last-known TF
deliberately does not represent sensor freshness; consumers that need freshness
must inspect the timestamped `body/pose` topic.

Start it directly:

```bash
ros2 launch kanga_core_microcontroller body_pose_tf.launch.py
```

Publish a preliminary pose with 90° yaw (translation is ignored by the
broadcaster):

```bash
ros2 topic pub /body/pose geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: body_origin}, pose: {pose: {orientation: {z: 0.7071067811865475, w: 0.7071067811865476}}}}" \
  --rate 10
```

Use `Ctrl+C` to stop the simulated stream. The real ESP32 bridge will publish
continuously with its measurement timestamps.

This broadcaster is disabled by default in unified bringup. It must not run at
the same time as another TF authority publishing a different parent for
`base_link`.

### Future closed-loop use

The ESP32 body state is not inherently limited to visualization. Roll, pitch,
angular velocity, and later fused motion estimates may support terrain-aware
drive control, slope compensation, rollover limits, slip handling, payload
stabilization, or a controller that no longer assumes perfectly planar motion.

Controllers should normally consume the timestamped `body/pose`, `body/twist`,
or a later fused `nav_msgs/msg/Odometry` topic directly rather than reading TF
as their feedback interface. Topics preserve covariance and make freshness and
failure handling explicit. TF remains the shared geometric representation for
visualization and frame conversion.

Before this state becomes authoritative control feedback, it needs measured
axis alignment, latency, update rate, covariance, dropout/staleness handling,
and fusion with the appropriate wheel, visual, SLAM, or other position source.
The BNO086-only pose cannot provide reliable translational position, and its
magnetometer-free relative yaw will drift. Once a fused estimator is selected,
that estimator—not `body_pose_tf_broadcaster`—should own `odom -> base_link`.

## Core CAN bridge

`core_can_bridge` is the real-rover producer of the topics above. It subscribes
to `from_can_bus` (`can_msgs/msg/Frame`, published by `ros2_socketcan`), decodes
the frames defined in `include/kanga_core_microcontroller/can_ids.hpp` and
`can_protocol.hpp`, and republishes them as typed ROS messages:

| CAN ID | Publishes |
|---|---|
| 812 | `diff_bar_angle` (`std_msgs/msg/Float64`, radians) |
| 820, 821, 822 | `body/pose`, `body/twist`, `imu/data` |

The IMU triple is published once per cycle, after the accelerometer frame
arrives and only when its sequence byte matches the pending gyro frame. Frames
shorter than their struct, extended-ID frames, RTR frames, and error frames are
dropped; malformed input is reported with throttled warnings rather than
publishing a partial sample.

Those same headers are compiled into the firmware, so a protocol change cannot
land on one side only. Encoder calibration and covariances live in
`config/core_can_bridge.yaml`; `diff_bar_encoder_counts_per_rad` is still a
placeholder until the encoder is characterised.

The bridge does not start `ros2_socketcan` by default, because core bringup owns
one shared SocketCAN bridge for all core CAN devices. To run it standalone
against a real bus:

```bash
ros2 launch kanga_core_microcontroller core_can_bridge.launch.py \
  launch_socketcan:=true can_interface:=can0
```

The interface must already be up at the ESP32 bit rate (250 kbit/s):

```bash
./scripts/setup_can.bash can0 250000
```

## Suspension joint state

`suspension_joint_state_publisher` subscribes to a calibrated
`std_msgs/msg/Float64` angle in radians on `diff_bar_angle`. Raw encoder counts,
calibration, and ESP32 CAN transport are owned by `core_can_bridge`, so this
node is unchanged whether the angle comes from CAN or from simulation.

The linkage model clamps the differential bar (`beta`) to ±70°, solves the
three-link closure equation using the drivetrain profile's L1/L2/L3 geometry
and beta-zero theta reference, and returns
the suspension displacement from the 30° physical reference. The returned
suspension angle uses the opposite sign to physical `theta` and is limited to
±30°. The same solved angle is assigned to both suspension joints. The current
values live in `kanga_core_description/config/drivetrains/drivetrain_2025.yaml`
so a later drivetrain iteration can replace them in its own profile.

It publishes the three positions as `sensor_msgs/msg/JointState` on
`suspension_joint_states`. Replace the pure kinematics implementation when the
linkage geometry changes; the ROS node boundary can remain unchanged.
While waiting for the first valid encoder angle after launch, it publishes all
three joints at zero. The neutral fallback stops once encoder data arrives and
is not reinstated after a subsequent sensor dropout.

Run without hardware in three terminals after sourcing the workspace:

```bash
# Terminal 1
ros2 launch kanga_core_microcontroller suspension_state.launch.py

# Terminal 2 (start this before publishing)
ros2 topic echo /suspension_joint_states --once

# Terminal 3
ros2 topic pub /diff_bar_angle std_msgs/msg/Float64 \
  "{data: 1.2217304763960306}" --once
```

For a continuous visualization test, run the manual sweep publisher from the
workspace source tree:

```bash
python3 src/kanga_core/kanga_core_microcontroller/test/sweep_diff_bar_angle.py
```

It publishes a triangle wave on `/diff_bar_angle` from -60° to +60° in five
seconds and back to -60° in another five seconds. The ten-second cycle repeats
until stopped with `Ctrl+C`.
