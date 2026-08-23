import React from "react";
import styles from "./DataDisplayCard.module.css";

export default function DataDisplayCard({
  battery,
  telemetry,
  linkLatencyMs,
  linkClientIp,
}) {
  const safeNumber = (value, fractionDigits = 1) =>
    typeof value === "number" && !Number.isNaN(value)
      ? value.toFixed(fractionDigits)
      : "--";

  const formatAh = (capacityMah) =>
    typeof capacityMah === "number" && !Number.isNaN(capacityMah)
      ? `${(capacityMah / 1000).toFixed(2)} Ah`
      : "--";

  const voltage =
    typeof battery.total_voltage === "number" && battery.total_voltage > 0
      ? battery.total_voltage
      : battery.measured_voltage;

  const formatFaultBits = (bits) => {
    if (!Array.isArray(bits)) return "--";
    const setBits = bits
      .map((b, i) => (b ? i : null))
      .filter((v) => v !== null);
    return setBits.length > 0 ? setBits.join(", ") : "None";
  };

  return (
    <div className={`card p-3 ${styles.card}`}>
      <h4 className={styles.title}>Data Display</h4>

      <section className={styles.section}>
        <h6 className={styles.sectionTitle}>Rover feedback</h6>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Telemetry</span>
          <span className={styles.rowValue}>{telemetry?.connected ? "live" : "offline"}</span>
        </div>
        {telemetry?.wheels && (
          <div className={styles.row}>
            <span className={styles.rowLabel}>Wheels rad/s</span>
            <span className={styles.rowValue}>
              {["fl", "bl", "br", "fr"]
                .map((k) => {
                  const v = telemetry.wheels[k];
                  return v == null ? "?" : v.toFixed(2);
                })
                .join(" / ")}
            </span>
          </div>
        )}
        {telemetry?.body?.yaw_deg != null && (
          <div className={styles.row}>
            <span className={styles.rowLabel}>Body yaw</span>
            <span className={styles.rowValue}>{telemetry.body.yaw_deg.toFixed(1)}°</span>
          </div>
        )}
        {telemetry?.body?.vx_mps != null && (
          <div className={styles.row}>
            <span className={styles.rowLabel}>Body speed</span>
            <span className={styles.rowValue}>{telemetry.body.vx_mps.toFixed(2)} m/s</span>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h6 className={styles.sectionTitle}>Link latency</h6>
        {linkLatencyMs != null ? (
          <>
            <div className={styles.row}>
              <span className={styles.rowLabel}>RTT</span>
              <span className={styles.rowValue}>{linkLatencyMs} ms</span>
            </div>
            {linkClientIp && (
              <div className={styles.row}>
                <span className={styles.rowLabel}>Client</span>
                <span className={styles.rowValue}>{linkClientIp}</span>
              </div>
            )}
          </>
        ) : (
          <div className={styles.measuring}>Not available</div>
        )}
      </section>

      <section className={styles.section}>
        <h6 className={styles.sectionTitle}>Battery</h6>
        <div className={styles.batteryGrid}>
          <div className={styles.batteryItem}>
            <span className={styles.rowLabel}>Ah</span>
            <span className={styles.rowValue}>{formatAh(battery.capacity)}</span>
          </div>
          <div className={styles.batteryItem}>
            <span className={styles.rowLabel}>Current</span>
            <span className={styles.rowValue}>{safeNumber(battery.current_draw)} A</span>
          </div>
          <div className={styles.batteryItem}>
            <span className={styles.rowLabel}>Voltage</span>
            <span className={styles.rowValue}>{safeNumber(voltage, 2)} V</span>
          </div>
          <div className={styles.batteryItem}>
            <span className={styles.rowLabel}>Max temp</span>
            <span className={styles.rowValue}>{safeNumber(battery.temperature_max)} °C</span>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <h6 className={styles.sectionTitle}>State</h6>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Fault bits</span>
          <span className={`${styles.rowValue} ${styles.faultBits}`}>
            {formatFaultBits(battery.fault_bits)}
          </span>
        </div>
      </section>
    </div>
  );
}
