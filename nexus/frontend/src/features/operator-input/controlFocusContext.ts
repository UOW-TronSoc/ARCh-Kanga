import { createContext } from 'react';
import type { ControlTarget } from '../../types';

export const inactiveControlTarget: ControlTarget = { kind: 'inactive' };

export const ControlFocusContext = createContext<ControlTarget>(inactiveControlTarget);