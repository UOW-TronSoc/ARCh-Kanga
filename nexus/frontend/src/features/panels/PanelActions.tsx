import { useContext, type PropsWithChildren } from 'react';
import { createPortal } from 'react-dom';
import { PanelActionsContext } from './panelActionsContext';

export function PanelActions({ children }: PropsWithChildren) {
  const target = useContext(PanelActionsContext);
  return target ? createPortal(children, target) : null;
}
