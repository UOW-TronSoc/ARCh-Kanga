import { useEffect, useState } from 'react';
import { Gamepad2, Keyboard, LockKeyhole, ShieldAlert, Unplug } from 'lucide-react';
import { useAppDataService, useAppSnapshot } from '../../app/appDataContext';
import { useDriveControls, useSafetyControls } from '../../hooks';
import { useOperatorInput } from '../operator-input/useOperatorInput';
import { mappingDisplayLabel } from '../operator-input/gamepad';
import { canReleaseDrivestop, drivestopPresentation } from './drivestopPresentation';
import styles from './DriveDock.module.css';

export function DriveControlPanel() {
  const drive = useDriveControls();
  const safety = useSafetyControls();
  const service = useAppDataService();
  const control = useAppSnapshot().control;
  const { gamepad } = useOperatorInput();
  const [confirmingRelease, setConfirmingRelease] = useState(false);
  const [confirmingTake, setConfirmingTake] = useState(false);
  const criticalFault = safety.faults.some((fault) => fault.severity === 'critical');
  const inputBlocked = safety.drivestop || !safety.whsOnline || criticalFault;
  const holder = !control || control.role === 'holder';
  const stopState = drivestopPresentation(safety.drivestop, safety.whsOnline);
  const releaseAllowed = canReleaseDrivestop(stopState, holder);
  const feedbackReady = safety.whsOnline && safety.drivestop === false && safety.closedLoop !== null;
  const modeAllowed = holder && safety.whsOnline && safety.closedLoop !== null;
  useEffect(() => {
    if (control && control.role !== 'holder') setConfirmingRelease(false);
    if (control?.role !== 'observer') setConfirmingTake(false);
  }, [control]);

  return (
    <section className={`${styles.card} ${control?.role === 'holder' ? styles.holding : ''}`} aria-label="Drive command controls">
      <header>
        <div><ShieldAlert size={16} /><span><b>Drive</b><small>Operator control</small></span></div>
        <span className={styles.link}><i className={safety.whsOnline ? styles.online : styles.danger} />WHS {safety.whsOnline ? 'online' : 'offline'}</span>
      </header>

      <div className={styles.actions}>
        <button className={drive.inputArmed ? styles.enabled : styles.muted} disabled={!drive.inputArmed && (!holder || inputBlocked || !feedbackReady)} onClick={drive.toggleInputArm}>
          {inputBlocked && <LockKeyhole size={14} />}Drive input: {drive.inputArmed ? 'Enabled' : 'Disabled'}
        </button>

        <div className={styles.speed}>
          <label htmlFor="speed-limit"><span>Speed max</span><b>{drive.speedLimitPercent}%</b></label>
          <input id="speed-limit" aria-label="Speed limit" type="range" min="0" max="100" value={drive.speedLimitPercent} onChange={(event) => drive.setSpeedLimit(Number(event.target.value))} />
        </div>

        <button className={stopState === 'Asserted' ? styles.dangerButton : styles.safe} disabled={stopState === 'Asserted' && !releaseAllowed} onClick={() => {
          if (!releaseAllowed) {
            safety.assertDrivestop();
            return;
          }
          if (control) {
            setConfirmingRelease(true);
            return;
          }
          safety.releaseDrivestop();
        }} aria-label={releaseAllowed ? 'Release drivestop' : 'Assert stop'}>
          Drivestop: {stopState}
        </button>
        {control?.role === 'observer' && <button type="button" onClick={() => setConfirmingTake(true)}>Take control</button>}
        {control?.notice && <p>{control.notice}</p>}
        {control?.error && <p role="alert">{control.error}</p>}
        {confirmingTake && (
          <div className={`${styles.confirm} ${styles.confirmTake}`} role="dialog" aria-label="Take control?">
            <p>Take control?</p>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.cancel} onClick={() => setConfirmingTake(false)}>Cancel</button>
              <button type="button" className={styles.take} onClick={() => { setConfirmingTake(false); service.takeControl(); }}>Take control</button>
            </div>
          </div>
        )}
        {confirmingRelease && (
          <div className={styles.confirm} role="dialog" aria-label="Release drivestop?">
            <p>Release drivestop?</p>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.cancel} onClick={() => setConfirmingRelease(false)}>Cancel</button>
              <button type="button" className={styles.release} onClick={() => { setConfirmingRelease(false); safety.releaseDrivestop(); }}>Release</button>
            </div>
          </div>
        )}

        {control && <button type="button" disabled={!holder} onClick={() => service.clearErrors()}>Clear errors</button>}
        <button className={safety.closedLoop ? styles.enabled : styles.idle} disabled={!modeAllowed || Boolean(safety.drivestop)} onClick={safety.toggleClosedLoop} aria-label="Toggle closed-loop drive">
          ODrive state: {safety.closedLoop === true ? 'Closed loop' : safety.closedLoop === false ? 'Idle' : '—'}
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

    </section>
  );
}