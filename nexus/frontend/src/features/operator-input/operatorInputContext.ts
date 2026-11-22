import { createContext } from 'react';
import type { OperatorInputState } from './operatorInputState';

export const OperatorInputContext = createContext<OperatorInputState>({ gamepad: null });