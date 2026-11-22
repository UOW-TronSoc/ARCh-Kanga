import { useAppSnapshot } from '../../app/appDataContext';
import { StatusChip } from '../../components/ui/StatusChip';
import { DRIVESTOP_LABEL, drivestopPresentation } from '../../services/live/drivestopPresentation';
import type { StatusTone } from '../../types';

const TONE: Record<ReturnType<typeof drivestopPresentation>, StatusTone> = {
  waiting: 'info',
  asserted: 'danger',
  released: 'success',
  stale: 'warning',
};

export function DrivestopStatus() {
  const presentation = drivestopPresentation(useAppSnapshot());
  return (
    <span role="status" aria-label="Drivestop">
      <StatusChip tone={TONE[presentation]}>{DRIVESTOP_LABEL[presentation]}</StatusChip>
    </span>
  );
}
