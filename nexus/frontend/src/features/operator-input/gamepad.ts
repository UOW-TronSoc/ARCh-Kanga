import type { DetectedGamepad, RecognizedGamepadMapping } from '../../types';

export const BUTTON_DRIVE_INPUT = 0;
export const BUTTON_ASSERT_DRIVESTOP = 1;

const GAMEPAD_POLL_MS = 200;

export function recognizeGamepadMapping(id: string): RecognizedGamepadMapping {
  const lower = id.toLowerCase();
  if (lower.includes('046d') && lower.includes('c215')) return 'logitech-extreme-3d';
  if (lower.includes('logitech') && lower.includes('extreme') && lower.includes('3d')) {
    return 'logitech-extreme-3d';
  }
  return 'generic-gamepad';
}

export function mappingDisplayLabel(mapping: RecognizedGamepadMapping): string {
  return mapping === 'logitech-extreme-3d' ? 'Logitech Extreme 3D' : 'Generic gamepad';
}

export function selectLowestConnectedGamepad(gamepads: (Gamepad | null)[]): Gamepad | null {
  let selected: Gamepad | null = null;
  for (let index = 0; index < gamepads.length; index += 1) {
    const gamepad = gamepads[index];
    if (gamepad?.connected) {
      selected = gamepad;
      break;
    }
  }
  return selected;
}

export function resolveTrackedGamepad(
  gamepads: (Gamepad | null)[],
  trackedIndex: number | null,
): { gamepad: Gamepad | null; index: number | null } {
  if (trackedIndex !== null) {
    const current = gamepads[trackedIndex];
    if (current?.connected) return { gamepad: current, index: trackedIndex };
  }
  const fallback = selectLowestConnectedGamepad(gamepads);
  return { gamepad: fallback, index: fallback?.index ?? null };
}

export function toDetectedGamepad(gamepad: Gamepad): DetectedGamepad {
  return {
    index: gamepad.index,
    name: gamepad.id || 'Unknown controller',
    mapping: recognizeGamepadMapping(gamepad.id),
  };
}

export function readConnectedGamepads(): (Gamepad | null)[] {
  return navigator.getGamepads ? [...navigator.getGamepads()] : [];
}

export function seedButtonEdges(gamepad: Gamepad): boolean[] {
  return gamepad.buttons.map((button) => Boolean(button?.pressed));
}

export interface GamepadSafetyHandlers {
  onAssertDrivestop: () => void;
  onToggleDriveInput?: () => void;
}

export function processGamepadSafetyButtons(
  gamepad: Gamepad,
  previousPressed: boolean[],
  handlers: GamepadSafetyHandlers,
): boolean[] {
  const nextPressed = gamepad.buttons.map((button) => Boolean(button?.pressed));
  const driveInputDown = nextPressed[BUTTON_DRIVE_INPUT];
  const drivestopDown = nextPressed[BUTTON_ASSERT_DRIVESTOP];
  const prevDriveInput = previousPressed[BUTTON_DRIVE_INPUT];
  const prevDrivestop = previousPressed[BUTTON_ASSERT_DRIVESTOP];

  if (handlers.onToggleDriveInput && driveInputDown && !prevDriveInput) handlers.onToggleDriveInput();
  if (drivestopDown && !prevDrivestop) handlers.onAssertDrivestop();

  return nextPressed;
}

export { GAMEPAD_POLL_MS };