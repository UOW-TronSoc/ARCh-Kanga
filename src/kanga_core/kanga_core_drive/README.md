# kanga_core_drive

Drive-domain control for the Kanga rover base.

## Owns

- Wheel configuration and geometry
- Chassis-to-wheel velocity mapping
- Drive limits and command validation
- Conversion of ODrive wheel feedback into wheel joint states
- Conversion of differential-bar encoder feedback into differential-bar and
  suspension joint states
- Optional wheel-derived odometry for diagnostics or sensor fusion
- Drive feedback interpretation and ROS node glue

## Does not own

- SocketCAN or ODrive endpoint state management
- General joystick policy
- Whole-rover bringup

Drive commands must be rejected while the shared `kanga_whs` motion-inhibit
state is active or unavailable.

Wheel motor feedback and differential-bar feedback are separate pipelines. The
wheel positions come from the motor controllers. The core microcontroller
reports the raw differential-bar encoder count and timestamp; this package
applies its calibration and mechanical mapping to the differential-bar and
suspension joint angles.

Both pipelines publish `sensor_msgs/JointState`. `robot_state_publisher` uses
those values with `kanga_core_description` to produce wheel, differential-bar,
and suspension link transforms. This package should not broadcast those link
transforms manually.

Loose sand and skid-steer slip make integrated wheel odometry unsuitable as the
sole localisation source. It may still be published as `nav_msgs/Odometry` for
short-term velocity information, diagnostics, slip detection, or cautiously
weighted sensor fusion. A visual, inertial, SLAM, or fused estimator should own
the authoritative `odom` to `base_link` transform.

The wheel mapping mathematics should live in a ROS-independent library with
unit tests.
