# ODrive S1 — wheel_br (back right)
# Merged after shared_motor_config.py by commission_wheels.
# Keep node_id in sync with config/wheels.yaml and launch.

SERIAL_NUMBER = "394E353B3231"

odrv.config.brake_resistor0.resistance = 2.2
odrv.axis0.config.can.node_id = 3
