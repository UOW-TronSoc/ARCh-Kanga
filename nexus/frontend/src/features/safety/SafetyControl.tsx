import { OctagonAlert, ShieldCheck } from 'lucide-react';
import { useAppDataService } from '../../app/appDataContext';
import { useSafetyState } from '../../hooks';
import { Button } from '../../components/ui/Button';
import styles from './SafetyControl.module.css';

export function SafetyControl() {
  const safety = useSafetyState();
  const service = useAppDataService();

  if (safety.drivestop) {
    return (
      <Button variant="danger" className={styles.control} onClick={service.releaseDrivestop} aria-label="Release drivestop in mock mode">
        <OctagonAlert size={18} /> DRIVESTOP ACTIVE
      </Button>
    );
  }

  return (
    <Button variant="danger" className={styles.control} onClick={service.assertDrivestop} aria-label="Assert drivestop">
      <ShieldCheck size={18} /> STOP
    </Button>
  );
}
