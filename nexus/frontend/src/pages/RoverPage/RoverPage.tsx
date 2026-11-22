import { PanelLayoutView } from '../../features/panels/PanelLayoutView';
import { roverLayout } from '../../features/panels/layouts';
import { TelemetryRail } from '../../features/telemetry/TelemetryRail';
import styles from './RoverPage.module.css';

const MAIN_SLOT = 'main';

export function RoverPage() {
  return (
    <div className={styles.page}>
      <div className={styles.workspace}>
        <PanelLayoutView
          layout={roverLayout}
          className={styles.views}
          mainSlotId={MAIN_SLOT}
          sizeFor={(slot) => (slot.id === MAIN_SLOT ? 'main' : 'inset')}
          slotClassName={(slot) => (slot.id === MAIN_SLOT ? styles.mainView : styles.insetView)}
        />
        <div className={styles.title}><span>ROVER / CORE</span><h1>Kanga</h1></div>
        <div className={styles.telemetry}><TelemetryRail /></div>
      </div>
    </div>
  );
}
