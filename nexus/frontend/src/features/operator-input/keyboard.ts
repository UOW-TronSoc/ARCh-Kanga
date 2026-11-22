export function shouldIgnoreOperatorShortcut(event: KeyboardEvent): boolean {
  if (event.repeat) return true;
  const target = event.target;
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.closest('[role="dialog"]')) return true;
  return false;
}

export interface OperatorKeyboardHandlers {
  onAssertDrivestop: () => void;
  onToggleDriveInput?: () => void;
}

export function handleOperatorKeyDown(event: KeyboardEvent, handlers: OperatorKeyboardHandlers): boolean {
  if (shouldIgnoreOperatorShortcut(event)) return false;

  if (event.code === 'Space' || event.key === ' ') {
    event.preventDefault();
    handlers.onAssertDrivestop();
    return true;
  }

  if (handlers.onToggleDriveInput && (event.code === 'Enter' || event.key === 'Enter')) {
    event.preventDefault();
    handlers.onToggleDriveInput();
    return true;
  }

  return false;
}