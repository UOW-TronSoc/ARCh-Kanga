import type { AppDataService } from '../../services/contracts/AppDataService';
import type { ControlTarget } from '../../types';

export interface FocusedOperatorActions {
  onToggleDriveInput: () => void;
}

export function focusedActionsForTarget(
  target: ControlTarget,
  service: AppDataService,
): FocusedOperatorActions | null {
  if (target.kind === 'drivetrain') {
    return { onToggleDriveInput: () => service.toggleInputArm() };
  }
  return null;
}