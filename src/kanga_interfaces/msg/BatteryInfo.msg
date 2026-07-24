std_msgs/Header header
float32 total_voltage     # Pack total voltage [V]
float32 measured_voltage  # Measured pack voltage [V]
float32 current           # Pack current; positive discharge, negative charge [A]
float32 soc               # Battery State of Charge (SOC) [%]
uint32 capacity           # Remaining pack capacity [mAh]
