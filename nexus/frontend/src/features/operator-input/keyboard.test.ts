import { describe, expect, it, vi } from 'vitest';
import { handleOperatorKeyDown, shouldIgnoreOperatorShortcut } from './keyboard';

function keyEvent(overrides: Partial<KeyboardEvent> & { target?: HTMLElement }): KeyboardEvent {
  const target = overrides.target ?? document.body;
  return {
    repeat: false,
    code: '',
    key: '',
    preventDefault: vi.fn(),
    target,
    ...overrides,
  } as KeyboardEvent;
}

describe('operator keyboard shortcuts', () => {
  it('ignores repeats and editable targets', () => {
    const input = document.createElement('input');
    expect(shouldIgnoreOperatorShortcut(keyEvent({ repeat: true, target: document.body }))).toBe(true);
    expect(shouldIgnoreOperatorShortcut(keyEvent({ target: input }))).toBe(true);
    expect(shouldIgnoreOperatorShortcut(keyEvent({ target: document.body }))).toBe(false);
  });

  it('ignores shortcuts inside dialogs', () => {
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    const button = document.createElement('button');
    dialog.append(button);
    document.body.append(dialog);
    expect(shouldIgnoreOperatorShortcut(keyEvent({ target: button }))).toBe(true);
    dialog.remove();
  });

  it('toggles drive input on Enter when focused handlers are present', () => {
    const toggle = vi.fn();
    const drivestop = vi.fn();
    const event = keyEvent({ code: 'Enter', key: 'Enter', target: document.body });
    expect(handleOperatorKeyDown(event, { onAssertDrivestop: drivestop, onToggleDriveInput: toggle })).toBe(true);
    expect(toggle).toHaveBeenCalledTimes(1);
    expect(event.preventDefault).toHaveBeenCalled();
  });

  it('does not toggle drive input on Enter without focused handlers', () => {
    const drivestop = vi.fn();
    const event = keyEvent({ code: 'Enter', key: 'Enter', target: document.body });
    expect(handleOperatorKeyDown(event, { onAssertDrivestop: drivestop })).toBe(false);
    expect(drivestop).not.toHaveBeenCalled();
  });

  it('asserts drivestop on Space from any focus', () => {
    const toggle = vi.fn();
    const drivestop = vi.fn();
    const event = keyEvent({ code: 'Space', key: ' ', target: document.body });
    handleOperatorKeyDown(event, { onAssertDrivestop: drivestop, onToggleDriveInput: toggle });
    expect(drivestop).toHaveBeenCalledTimes(1);
    expect(toggle).not.toHaveBeenCalled();
  });
});