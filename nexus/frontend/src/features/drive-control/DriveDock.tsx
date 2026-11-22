import { Gamepad2, Keyboard, LockKeyhole, ShieldAlert, Unplug } from 'lucide-react';
import { useAppDataService } from '../../app/appDataContext';
import { useDriveControls, useSafetyControls } from '../../hooks';
import { DrivestopStatus } from '../safety/DrivestopStatus';
import { useOperatorInput } from '../operator-input/useOperatorInput';
import { mappingDisplayLabel } from '../operator-input/gamepad';
import styles from './DriveDock.module.css';

export function DriveControlPanel() {
  const drive = useDriveControls();
  const safety = useSafetyControls();
  const commandsEnabled = useAppDataService().commandsEnabled;
  const { gamepad } = useOperatorInput();
  const criticalFault = safety.faults.some((fault) => fault.severity === 'critical');
  const inputBlocked = !commandsEnabled || safety.drivestop !== false || !safety.whsOnline || criticalFault;

  return (
    <section className={styles.card} aria-label="Drive command controls">
      <header>
        <div><ShieldAlert size={16} /><span><b>Drive</b><small>Operator control</small></span></div>
        <DrivestopStatus />
      </header>

      <div className={styles.actions}>
        <button className={drive.inputArmed ? styles.enabled : styles.muted} disabled={inputBlocked} onClick={drive.toggleInputArm}>
          {inputBlocked && <LockKeyhole size={14} />}Drive input: {drive.inputArmed ? 'Enabled' : 'Disabled'}
        </button>

        <div className={styles.speed}>
          <label htmlFor="speed-limit"><span>Speed max</span><b>{drive.speedLimitPercent}%</b></label>
          <input id="speed-limit" aria-label="Speed limit" type="range" min="0" max="100" value={drive.speedLimitPercent} disabled={!commandsEnabled} onChange={(event) => drive.setSpeedLimit(Number(event.target.value))} />
        </div>

        {commandsEnabled && (
          <button className={safety.drivestop ? styles.dangerButton : styles.safe} onClick={safety.drivestop ? safety.releaseDrivestop : safety.assertDrivestop} aria-label={safety.drivestop ? 'Release drivestop in mock mode' : 'Assert drivestop'}>
            Drivestop: {safety.drivestop ? 'Enabled' : 'Disabled'}
          </button>
        )}

        <button className={safety.closedLoop ? styles.enabled : styles.idle} disabled={!commandsEnabled || safety.drivestop !== false || !safety.whsOnline} onClick={safety.toggleClosedLoop} aria-label="Toggle closed-loop drive">
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

      <p>{commandsEnabled ? 'Enter / B0 enables drive input · Space / B1 asserts drivestop' : 'Keyboard and gamepad shortcuts are disabled.'}</p>
    </section>
  );
}