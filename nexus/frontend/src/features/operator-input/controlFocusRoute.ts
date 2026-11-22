import type { ControlTarget } from '../../types';
import { inactiveControlTarget } from './controlFocusContext';

export function controlTargetForRoverRoute(onRover: boolean): ControlTarget {
  return onRover ? { kind: 'drivetrain' } : inactiveControlTarget;
}