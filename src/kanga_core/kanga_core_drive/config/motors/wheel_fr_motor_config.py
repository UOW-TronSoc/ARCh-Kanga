# ODrive S1 — wheel_fr (front right)
# Merged after shared_motor_config.py by commission_wheels.
# Keep node_id in sync with config/wheels.yaml and launch.

SERIAL_NUMBER = "3964344C3331"

odrv.config.brake_resistor0.resistance = 2.4
odrv.axis0.config.can.node_id = 4
