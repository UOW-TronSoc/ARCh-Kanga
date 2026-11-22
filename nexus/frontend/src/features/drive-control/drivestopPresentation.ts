export type DrivestopPresentation = 'Unknown' | 'Asserted' | 'Released' | 'Stale';

export function drivestopPresentation(drivestop: boolean | null, whsOnline: boolean): DrivestopPresentation {
  if (drivestop === null) return 'Unknown';
  if (!whsOnline) return 'Stale';
  return drivestop ? 'Asserted' : 'Released';
}

export function canReleaseDrivestop(presentation: DrivestopPresentation, holder: boolean): boolean {
  return presentation === 'Asserted' && holder;
}
