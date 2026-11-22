import type { AppSnapshot } from '../../types';

export type DrivestopPresentation = 'waiting' | 'asserted' | 'released' | 'stale';

export const DRIVESTOP_LABEL: Record<DrivestopPresentation, string> = {
  waiting: 'Waiting for WHS',
  asserted: 'Asserted',
  released: 'Released',
  stale: 'Stale / disconnected',
};

export function drivestopPresentation(snapshot: AppSnapshot): DrivestopPresentation {
  if (snapshot.safety.drivestop === null) return 'waiting';
  const sourceLost = snapshot.connection.phase !== 'connected'
    || snapshot.connection.stale
    || !snapshot.safety.whsOnline;
  if (sourceLost) return 'stale';
  return snapshot.safety.drivestop ? 'asserted' : 'released';
}
