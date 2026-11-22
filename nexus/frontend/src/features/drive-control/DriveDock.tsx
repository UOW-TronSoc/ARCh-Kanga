import { Gamepad2, Keyboard, LockKeyhole, ShieldAlert, Unplug } from 'lucide-react';
import { useDriveControls, useSafetyControls } from '../../hooks';
import { useOperatorInput } from '../operator-input/useOperatorInput';
import { mappingDisplayLabel } from '../operator-input/gamepad';
import styles from './DriveDock.module.css';

export function DriveControlPanel() {
  const drive = useDriveControls();
  const safety = useSafetyControls();
  const { gamepad } = useOperatorInput();
  const criticalFault = safety.faults.some((fault) => fault.severity === 'critical');
  const inputBlocked = safety.drivestop || !safety.whsOnline || criticalFault;

  return (
    <section className={styles.card} aria-label="Drive command controls">
      <header>
        <div><ShieldAlert size={16} /><span><b>Drive</b><small>Operator control</small></span></div>
        <span className={styles.link}><i className={safety.whsOnline ? styles.online : styles.danger} />WHS {safety.whsOnline ? 'online' : 'offline'}</span>
      </header>

      <div className={styles.actions}>
        <button className={drive.inputArmed ? styles.enabled : styles.muted} disabled={inputBlocked} onClick={drive.toggleInputArm}>
          {inputBlocked && <LockKeyhole size={14} />}Drive input: {drive.inputArmed ? 'Enabled' : 'Disabled'}
        </button>

        <div className={styles.speed}>
          <label htmlFor="speed-limit"><span>Speed max</span><b>{drive.speedLimitPercent}%</b></label>
          <input id="speed-limit" aria-label="Speed limit" type="range" min="0" max="100" value={drive.speedLimitPercent} onChange={(event) => drive.setSpeedLimit(Number(event.target.value))} />
        </div>

        <button className={safety.drivestop ? styles.dangerButton : styles.safe} onClick={safety.drivestop ? safety.releaseDrivestop : safety.assertDrivestop} aria-label={safety.drivestop ? 'Release drivestop in mock mode' : 'Assert drivestop'}>
          Drivestop: {safety.drivestop ? 'Enabled' : 'Disabled'}
        </button>

        <button className={safety.closedLoop ? styles.enabled : styles.idle} disabled={safety.drivestop || !safety.whsOnline} onClick={safety.toggleClosedLoop} aria-label="Toggle closed-loop drive">
          ODrive state: {safety.closedLoop ? 'Closed loop' : 'Idle'}
        </button>
      </div>

      <div className={styles.device} aria-live="polite">
        <span>Detected gamepad</span>
        <div>
          {gamepad ? <Gamepad2 size={15} /> : <Unplug size={15} />}
          {gamepad ? (
            <span className={styles.deviceDetail}>
              <b>{gamepad.name}</b>
              <small>{mappingDisplayLabel(gamepad.mapping)}</small>
            </span>
          ) : (
            <span className={styles.deviceDetail}>
              <b>No gamepad detected</b>
              <small className={styles.keyboardHint}><Keyboard size={12} /> Keyboard available</small>
            </span>
          )}
        </div>
      </div>

      <p>Enter / B0 enables drive input · Space / B1 asserts drivestop</p>
    </section>
  );
}