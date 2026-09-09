# Shared ODrive Fibre settings for Kanga drive wheels.
# Concatenated before each wheel_*_motor_config.py at commission time.
# Do not put SERIAL_NUMBER or node_id here (those live in per-wheel overlays).
#
# kanga_core_controller normally streams setpoints at roughly 50 Hz while
# CLOSED_LOOP. The watchdog below is currently disabled; timeout only takes
# effect if enable_watchdog is set true and the configuration is recommissioned.

# commission_wheels appends validated velocity and acceleration assignments
# after this shared file and the individual wheel overlay. Keep those protected
# fields out of both editable motor files.

odrv.config.dc_bus_overvoltage_trip_level = 36
odrv.config.dc_bus_undervoltage_trip_level = 21
odrv.config.dc_max_positive_current = math.inf
odrv.config.dc_max_negative_current = -math.inf
odrv.config.brake_resistor0.enable = True
odrv.axis0.config.motor.motor_type = MotorType.PMSM_CURRENT_CONTROL
odrv.axis0.config.motor.pole_pairs = 20
odrv.axis0.config.motor.torque_constant = 0.0827
odrv.axis0.config.motor.current_soft_max = 50
odrv.axis0.config.motor.current_hard_max = 70
odrv.axis0.config.motor.calibration_current = 10
odrv.axis0.config.motor.resistance_calib_max_voltage = 2
odrv.axis0.config.calibration_lockin.current = 10
odrv.axis0.motor.motor_thermistor.config.enabled = False
odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
odrv.axis0.controller.config.input_mode = InputMode.VEL_RAMP
odrv.axis0.controller.config.vel_limit_tolerance = 1.1363636363636365
# Spinout detection power filters (bandwidth in 1/s, thresholds in watts).
odrv.axis0.controller.config.spinout_mechanical_power_bandwidth = 20
odrv.axis0.controller.config.spinout_electrical_power_bandwidth = 20
odrv.axis0.controller.config.spinout_mechanical_power_threshold = -30
odrv.axis0.controller.config.spinout_electrical_power_threshold = 30
odrv.axis0.config.torque_soft_min = -math.inf
odrv.axis0.config.torque_soft_max = math.inf
odrv.axis0.trap_traj.config.accel_limit = 40
odrv.can.config.protocol = Protocol.SIMPLE
odrv.can.config.baud_rate = 250000
# Keep state feedback responsive at 50 Hz while retaining bus headroom.
odrv.axis0.config.can.heartbeat_msg_rate_ms = 20
odrv.axis0.config.can.encoder_msg_rate_ms = 10
# Retain current and torque telemetry at 10 Hz for mechanical logging.
odrv.axis0.config.can.iq_msg_rate_ms = 100
odrv.axis0.config.can.torques_msg_rate_ms = 100
odrv.axis0.config.can.error_msg_rate_ms = 100
odrv.axis0.config.can.temperature_msg_rate_ms = 100
odrv.axis0.config.can.bus_voltage_msg_rate_ms = 100
odrv.axis0.config.enable_watchdog = False
# Firmware setpoint watchdog (seconds). kanga_core_controller streams ~50 Hz in CLOSED_LOOP.
odrv.axis0.config.watchdog_timeout = 1
odrv.axis0.config.load_encoder = EncoderId.ONBOARD_ENCODER0
odrv.axis0.config.commutation_encoder = EncoderId.ONBOARD_ENCODER0
odrv.config.enable_uart_a = False
