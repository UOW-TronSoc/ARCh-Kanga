# kanga_core_microcontroller

Firmware and host-side ROS integration for the rover-base ESP32. Keeping both
ends of the device protocol in one package makes protocol changes easy to
review, but does not mean they should become one monolithic program.

## Owns

- The `.ino` firmware that runs on the rover-base microcontroller
- Its CAN protocol and host-side translation where required
- ROO release and drive-lock commands and status
- Differential-bar encoder sampling and raw count reporting
- Host-side publication of IMU, encoder, servo command/status, and other typed
  ROS interfaces carried by the ESP32 CAN protocol
- Testable conversion of differential-bar angle into suspension joint state
- Core internal status reported by the microcontroller

## Boundary

Payload-specific firmware belongs to its payload package. The ESP32 firmware
reports raw encoder values and timing without embedding rover geometry. A
separate executable in this package owns the suspension kinematics so that the
equation remains independent of CAN framing and can be tested offline. Link TF
generation remains with `robot_state_publisher` or a dedicated estimator. The
GPIO motion-stop input belongs to `kanga_whs`, not this firmware.

## Source layout

```text
kanga_core_microcontroller/
├── firmware/
│   └── kanga_core_esp32/       Arduino sketch and firmware-only .h/.cpp files
├── include/                    Testable host-side C++ libraries
├── src/
│   ├── esp32_can_bridge.cpp    Future CAN-to-ROS executable
│   └── suspension_*.cpp        Suspension mapping executable and library
├── config/                     Host-side ROS parameters
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
| ESP32 firmware | Sensor sampling, encoder counts, IMU access, servo I/O, CAN framing, device timestamps and status | ROS, TF, URDF geometry, or suspension kinematics |
| ESP32 CAN bridge | SocketCAN transport, protocol validation, unit conversion/calibration, typed ROS topics and servo command forwarding | Robot geometry or TF |
| Suspension state node | Diff-bar angle limits and the replaceable diff-bar-to-suspension equation | CAN framing, encoder drivers, or TF |

The intended state path is:

```text
diff-bar encoder → ESP32 firmware → CAN → ESP32 CAN bridge
  → calibrated diff_bar_angle → suspension_joint_state_publisher
  → suspension_joint_states → robot_state_publisher integration
```

The IMU and servo paths share the firmware and CAN bridge, but not the
suspension kinematics executable. This keeps hardware reconnection or protocol
changes separate from the mechanism equation and makes that equation testable
without an ESP32.

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

The future ESP32 CAN bridge will only decode the finished body state and publish
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

The ESP32 will calculate the body pose and twist and transmit the finished
values over CAN. The future CAN bridge must publish both samples without
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

## Suspension joint state

`suspension_joint_state_publisher` currently subscribes to a calibrated
`std_msgs/msg/Float64` angle in radians on `diff_bar_angle`. Raw encoder counts,
calibration, and ESP32 CAN transport are deferred to the future bridge node.

The temporary linear model clamps the differential bar to ±70°, maps that
range to ±30°, and assigns the same angle to both suspension joints:

```text
left_suspension_joint = right_suspension_joint = diff_bar_joint × 30/70
```

It publishes the three positions as `sensor_msgs/msg/JointState` on
`suspension_joint_states`. Replace the pure kinematics implementation when the
physical relationship is solved; the ROS node boundary can remain unchanged.

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
