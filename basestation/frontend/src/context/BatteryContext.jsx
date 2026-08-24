import React, { createContext, useContext, useState } from "react";

const BatteryContext = createContext(null);

const INITIAL_BATTERY = {
  charge_pct: 0,
  current_draw: 0,
  temperature: 0,
  timestamp: 0,
  temperature_max: 0,
  temperature_min: 0,
  temps: [],
  total_voltage: 0,
  measured_voltage: 0,
  capacity: 0,
  cell_voltages: [],
  cell_voltages_v: [],
  charge_state: 0,
  fault_bits: [],
  source_timestamp: null,
};

/** Battery widgets stay visible; live feed wires in when telemetry includes pack data. */
export function BatteryProvider({ children }) {
  const [batteryInfo] = useState(INITIAL_BATTERY);
  return (
    <BatteryContext.Provider value={batteryInfo}>
      {children}
    </BatteryContext.Provider>
  );
}

export function useBattery() {
  const ctx = useContext(BatteryContext);
  if (!ctx) throw new Error("useBattery must be used within BatteryProvider");
  return ctx;
}
