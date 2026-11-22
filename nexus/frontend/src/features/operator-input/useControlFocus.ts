import { useContext } from 'react';
import { ControlFocusContext } from './controlFocusContext';

export function useControlFocus() {
  return useContext(ControlFocusContext);
}