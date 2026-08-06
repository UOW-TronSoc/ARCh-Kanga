# One atomic four-wheel command from the chassis controller to the drive layer.
# All values are wheel-joint velocities before gearbox conversion, in rad/s.
std_msgs/Header header
float64 front_left_rad_s
float64 back_left_rad_s
float64 back_right_rad_s
float64 front_right_rad_s
