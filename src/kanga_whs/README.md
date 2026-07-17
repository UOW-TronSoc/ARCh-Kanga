# kanga_whs

Whole-robot motion-stop software for Kanga.

The minimum 2027 goal is deliberately simple: a physical stop switch connected
to an NVIDIA Jetson GPIO, plus a software override script for exceptional
mid-competition recovery. The stop applies to every motor on the rover core and
attached payloads, so interfaces should not call it a drive-only stop.

## Owns

- Reading and publishing the GPIO stop-switch state
- A whole-robot motion-inhibit state used by core and payload controllers
- The deliberate competition override command or script
- Clear operator-visible indication when the override is active

## Initial behaviour

- An active GPIO switch inhibits core and payload motor commands.
- Controllers reject motion while the inhibit is active.
- The override explicitly bypasses the GPIO-triggered software inhibit.
- The override is a manual competition recovery action, not an automatic fault
  response or general operating mode.
- The override state should be obvious to the operator and cleared deliberately
  when it is no longer required.

## Safety boundary

In this initial design the physical switch is an input to software; it does not
directly interrupt motor power or hardware enables. Stopping therefore depends
on the Jetson, GPIO monitoring, and motor-control software functioning. Do not
describe this implementation as a hardwired or safety-rated emergency stop.

A future hardwired interruption can be added if competition rules or risk
assessment require one, but it is outside the minimum implementation.

Transport-neutral state and override interfaces belong in `kanga_interfaces`.
Exact GPIO electrical configuration, default state, startup behaviour, and
controller response must be defined and tested during implementation.
