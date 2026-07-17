# kanga_core_microcontroller

Firmware and communication protocol for the Kanga rover-base microcontroller.

## Owns

- The `.ino` firmware that runs on the rover-base microcontroller
- Its CAN protocol and host-side translation where required
- ROO release and drive-lock commands and status
- Differential-bar encoder sampling and raw count reporting
- Core internal status reported by the microcontroller

## Boundary

Payload-specific firmware belongs to its payload package. Differential-bar
calibration, suspension kinematics, joint-state publication, and TF generation
remain outside the firmware. It should report the raw encoder count and timing
information without embedding rover geometry. The GPIO motion-stop input
belongs to `kanga_whs`, not this firmware.
