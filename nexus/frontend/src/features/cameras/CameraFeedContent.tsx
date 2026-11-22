import { PanelActions } from '../panels/PanelActions';
import type { PanelContentProps } from '../panels/types';
import type { CameraDescriptor, CameraHealth } from './types';
import styles from './CameraFeedContent.module.css';

const signalLabels: Record<CameraHealth, string> = {
  live: 'LIVE',
  standby: 'SIGNAL STANDBY',
  unavailable: 'FEED UNAVAILABLE',
};

export function CameraFeedContent({ camera }: PanelContentProps & { camera: CameraDescriptor }) {
  return (
    <div className={styles.feed}>
      <span className={styles.grid} />
      <span className={styles.track} />
      <span className={styles.signal}>{signalLabels[camera.health]}</span>
      <PanelActions>
        <span className={`${styles.health} ${styles[camera.health]}`}><i />{camera.health}</span>
      </PanelActions>
    </div>
  );
}
