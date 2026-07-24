std_msgs/Header header
uint32[2] temps           # Max and min BMS temperatures [C]
uint32[7] cell_voltages   # Per-cell voltages [mV]
uint32 charge_state       # Daly charge/discharge state code
uint32[8] fault_bits      # Raw Daly fault status bytes
