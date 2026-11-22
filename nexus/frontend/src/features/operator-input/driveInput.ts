export interface DriveAxes {
  x: number;
  yaw: number;
}

const ZERO: DriveAxes = { x: 0, yaw: 0 };

export function applyAxisDeadzone(value: number, deadzone = 0.3): number {
  if (!Number.isFinite(value)) return 0;
  const magnitude = Math.min(1, Math.abs(value));
  if (magnitude < deadzone) return 0;
  return Math.sign(value) * (magnitude - deadzone) / (1 - deadzone);
}

export function keyboardAxes(keys: ReadonlySet<string>): DriveAxes {
  let x = 0;
  let yaw = 0;
  if (keys.has('w')) x += 1;
  if (keys.has('s')) x -= 1;
  if (keys.has('a')) yaw += 1;
  if (keys.has('d')) yaw -= 1;
  return { x: Math.max(-1, Math.min(1, x)), yaw: Math.max(-1, Math.min(1, yaw)) };
}

export function gamepadAxes(gamepad: Gamepad): DriveAxes {
  const id = gamepad.id.toLowerCase();
  const logitech = id.includes('extreme') && id.includes('3d') || (id.includes('046d') && id.includes('c215'));
  const throttle = logitech ? Math.min(1, Math.max(0, (1 - (gamepad.axes[3] ?? -1)) / 2)) : 1;
  const yawAxis = logitech ? (gamepad.axes[2] ?? 0) : -(gamepad.axes[2] ?? gamepad.axes[3] ?? 0);
  let x = applyAxisDeadzone(-(gamepad.axes[1] ?? 0)) * throttle;
  let yaw = applyAxisDeadzone(yawAxis) * throttle;
  const pressed = (index: number) => Boolean(gamepad.buttons[index]?.pressed);
  if (pressed(12) !== pressed(13)) x = pressed(12) ? 1 : -1;
  if (pressed(14) !== pressed(15)) yaw = pressed(14) ? 1 : -1;
  return { x, yaw };
}

export function combineAxes(keyboard: DriveAxes, gamepad: DriveAxes): DriveAxes {
  return {
    x: Math.max(-1, Math.min(1, keyboard.x + gamepad.x)),
    yaw: Math.max(-1, Math.min(1, keyboard.yaw + gamepad.yaw)),
  };
}

export { ZERO };
