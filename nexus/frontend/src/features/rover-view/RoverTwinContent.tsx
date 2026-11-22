import { lazy, Suspense, useState, type ComponentType } from 'react';
import { RotateCcw, TriangleAlert } from 'lucide-react';
import { useRoverSnapshot } from '../../hooks';
import { PanelActions } from '../panels/PanelActions';
import type { PanelContentProps } from '../panels/types';
import styles from './RoverTwinContent.module.css';

interface ModelSceneProps { sceneKey: number; resetToken: number; interactive: boolean; onError: () => void }
const RoverModelScene: ComponentType<ModelSceneProps> = import.meta.env.MODE === 'test'
  ? () => <div data-testid="mock-rover-renderer" />
  : lazy(() => import('./RoverModelScene').then((module) => ({ default: module.RoverModelScene })));

export function RoverTwinContent({ size, active }: PanelContentProps) {
  const { freshness } = useRoverSnapshot();
  const [sceneKey, setSceneKey] = useState(0);
  const [resetToken, setResetToken] = useState(0);
  const [modelFailed, setModelFailed] = useState(false);
  const retry = () => { setModelFailed(false); setSceneKey((key) => key + 1); };

  return (
    <div className={styles.twin}>
      {!modelFailed && (
        <Suspense fallback={<div className={styles.rendererLoading}>Starting 3D renderer…</div>}>
          <RoverModelScene sceneKey={sceneKey} resetToken={resetToken} interactive={active} onError={() => setModelFailed(true)} />
        </Suspense>
      )}
      {modelFailed && <button className={styles.modelError} type="button" onClick={retry}><TriangleAlert size={16} /><span>Rover model unavailable<small>Retry renderer</small></span></button>}
      <PanelActions>
        <span className={`${styles.freshness} ${styles[freshness]}`}><i />{freshness}</span>
        {size !== 'inset' && <button type="button" aria-label="Reset camera" title="Reset camera" onClick={() => setResetToken((token) => token + 1)}><RotateCcw size={15} /></button>}
      </PanelActions>
    </div>
  );
}
