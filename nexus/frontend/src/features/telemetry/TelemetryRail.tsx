import { Activity, AlertTriangle, Battery, ChevronDown, Gauge } from 'lucide-react';
import { useConnectionState, useRoverSnapshot, useSafetyState } from '../../hooks';
import styles from './TelemetryRail.module.css';

export function TelemetryRail() {
  const rover = useRoverSnapshot();
  const connection = useConnectionState();
  const safety = useSafetyState();
  const format = (value: number | null | undefined, digits = 1) => (
    value != null && Number.isFinite(value) ? value.toFixed(digits) : '—'
  );
  const battery = rover.battery.percentage;

  return (
    <aside className={styles.rail} aria-label="Rover telemetry">
      {safety.faults.map((fault) => (
        <div className={styles.fault} key={fault.id}><AlertTriangle size={17} /><span><strong>{fault.title}</strong><small>{fault.detail}</small></span></div>
      ))}
      <details className={styles.section} open>
        <summary><span><Gauge size={14} />SYSTEM</span><ChevronDown size={14} /></summary>
        <div className={styles.systemContent}>
          <div className={styles.battery}>
            <span><Battery size={15} /> Battery</span>
            <strong className={battery != null && battery <= 20 ? styles.bad : undefined}>{format(battery, 0)}{battery != null && <small>%</small>}</strong>
          </div>
          <dl className={styles.readings}>
            <div><dt>Current draw</dt><dd>{format(rover.battery.currentDrawA)} <small>A</small></dd></div>
            <div><dt>WHS link</dt><dd className={safety.whsOnline ? styles.good : styles.bad}>{safety.whsOnline ? 'ONLINE' : 'OFFLINE'}</dd></div>
            <div><dt>Telemetry</dt><dd className={connection.stale ? styles.warn : undefined}>{connection.lastUpdate ?? '—'}</dd></div>
            <div><dt>Latency</dt><dd>{connection.latencyMs === null ? '—' : `${connection.latencyMs} ms`}</dd></div>
          </dl>
        </div>
      </details>
      <details className={styles.section} open>
        <summary><span><Activity size={14} />MOTION</span><ChevronDown size={14} /></summary>
        <dl className={styles.readings}>
          <div><dt>Ground speed</dt><dd>{format(rover.body.linearSpeedMps, 2)} <small>m/s</small></dd></div>
          <div><dt>Yaw rate</dt><dd>{format(rover.body.yawRateDegS)} <small>°/s</small></dd></div>
          <div><dt>Body pitch</dt><dd>{format(rover.body.pitchDeg)} <small>°</small></dd></div>
        </dl>
      </details>
      <details className={styles.section}>
        <summary><span>DRIVE DETAILS</span><ChevronDown size={14} /></summary>
        <div className={styles.driveRows}>
          <table aria-label="Drive telemetry by wheel">
            <colgroup><col className={styles.wheelColumn} /><col className={styles.rpmColumn} /><col className={styles.rpmColumn} /><col className={styles.tempColumn} /></colgroup>
            <thead><tr><th scope="col">Wheel</th><th scope="col">Motor<small>RPM</small></th><th scope="col">Wheel<small>RPM</small></th><th scope="col">Temp<small>°C</small></th></tr></thead>
            <tbody>
          {rover.motors.map((motor) => {
            const wheel = rover.wheels.find((joint) => joint.name === motor.wheelJointName);
            // Wheel JointState velocity is rad/s; motor velocity is already RPM.
            const wheelRpm = wheel?.velocity == null ? null : wheel.velocity * 60 / (2 * Math.PI);
            return <tr key={motor.id} className={motor.state === 'fault' ? styles.bad : undefined}>
              <th scope="row" title={motor.wheelJointName}>{motor.label}</th>
              <td>{format(motor.velocityRpm, 0)}</td>
              <td>{format(wheelRpm, 1)}</td>
              <td>{format(motor.temperatureC, 0)}</td>
            </tr>;
          })}
            </tbody>
          </table>
        </div>
      </details>
    </aside>
  );
}
