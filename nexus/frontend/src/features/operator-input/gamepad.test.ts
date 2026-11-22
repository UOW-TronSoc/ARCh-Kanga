import { describe, expect, it, vi } from 'vitest';
import {
  BUTTON_ASSERT_DRIVESTOP,
  BUTTON_DRIVE_INPUT,
  processGamepadSafetyButtons,
  recognizeGamepadMapping,
  resolveTrackedGamepad,
  seedButtonEdges,
  selectLowestConnectedGamepad,
  toDetectedGamepad,
} from './gamepad';

function mockGamepad(index: number, buttons: boolean[], id = 'test-controller'): Gamepad {
  return {
    index,
    connected: true,
    id,
    mapping: '',
    timestamp: 0,
    axes: [],
    buttons: buttons.map((pressed) => ({ pressed, touched: pressed, value: pressed ? 1 : 0 })),
    hapticActuators: [],
    vibrationActuator: null,
  } as unknown as Gamepad;
}

describe('gamepad discovery helpers', () => {
  it('selects the connected gamepad with the lowest browser index', () => {
    const pads: (Gamepad | null)[] = [null, mockGamepad(1, []), mockGamepad(3, [])];
    expect(selectLowestConnectedGamepad(pads)?.index).toBe(1);
  });

  it('supports sparse browser indices', () => {
    const pads: (Gamepad | null)[] = [null, null, mockGamepad(2, [])];
    expect(selectLowestConnectedGamepad(pads)?.index).toBe(2);
  });

  it('retains the tracked pad while it stays connected', () => {
    const pads: (Gamepad | null)[] = [mockGamepad(0, []), mockGamepad(1, [])];
    const result = resolveTrackedGamepad(pads, 1);
    expect(result.index).toBe(1);
    expect(result.gamepad?.index).toBe(1);
  });

  it('falls back to the lowest connected pad after disconnect', () => {
    const pads: (Gamepad | null)[] = [mockGamepad(0, []), null];
    const result = resolveTrackedGamepad(pads, 1);
    expect(result.index).toBe(0);
  });

  it('recognizes Logitech Extreme 3D controllers', () => {
    expect(recognizeGamepadMapping('Logitech Logitech Extreme 3D')).toBe('logitech-extreme-3d');
    expect(recognizeGamepadMapping('046d:c215 Logitech Extreme 3D Pro')).toBe('logitech-extreme-3d');
    expect(toDetectedGamepad(mockGamepad(0, [], 'Logitech Extreme 3D')).mapping).toBe('logitech-extreme-3d');
  });
});

describe('gamepad safety buttons', () => {
  it('toggles drive input on B0 rising edge only when focused', () => {
    const toggle = vi.fn();
    const drivestop = vi.fn();
    let edges = [false, false];
    edges = processGamepadSafetyButtons(mockGamepad(0, [true, false]), edges, {
      onAssertDrivestop: drivestop,
      onToggleDriveInput: toggle,
    });
    expect(toggle).toHaveBeenCalledTimes(1);
    processGamepadSafetyButtons(mockGamepad(0, [true, false]), edges, {
      onAssertDrivestop: drivestop,
      onToggleDriveInput: toggle,
    });
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('skips drive input when focus handlers are absent but still updates edges', () => {
    const drivestop = vi.fn();
    const edges = processGamepadSafetyButtons(mockGamepad(0, [true, false]), [false, false], {
      onAssertDrivestop: drivestop,
    });
    expect(edges[BUTTON_DRIVE_INPUT]).toBe(true);
    expect(drivestop).not.toHaveBeenCalled();
  });

  it('asserts drivestop on B1 rising edge only', () => {
    const toggle = vi.fn();
    const drivestop = vi.fn();
    const pressed = mockGamepad(0, [false, true]);
    processGamepadSafetyButtons(pressed, [false, false], { onAssertDrivestop: drivestop, onToggleDriveInput: toggle });
    expect(drivestop).toHaveBeenCalledTimes(1);
    expect(toggle).not.toHaveBeenCalled();
  });

  it('does not fire actions for buttons already held at connect time', () => {
    const toggle = vi.fn();
    const drivestop = vi.fn();
    const gp = mockGamepad(0, [true, true]);
    const seeded = seedButtonEdges(gp);
    processGamepadSafetyButtons(gp, seeded, { onAssertDrivestop: drivestop, onToggleDriveInput: toggle });
    expect(toggle).not.toHaveBeenCalled();
    expect(drivestop).not.toHaveBeenCalled();
    expect(gp.buttons[BUTTON_DRIVE_INPUT].pressed).toBe(true);
    expect(gp.buttons[BUTTON_ASSERT_DRIVESTOP].pressed).toBe(true);
  });
});