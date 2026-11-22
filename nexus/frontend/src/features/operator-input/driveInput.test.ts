import { describe, expect, it } from 'vitest';
import { applyAxisDeadzone, combineAxes, keyboardAxes } from './driveInput';

describe('drive input', () => {
  it('maps W/S to forward and reverse and A/D to yaw', () => {
    expect(keyboardAxes(new Set(['w']))).toEqual({ x: 1, yaw: 0 });
    expect(keyboardAxes(new Set(['s', 'a']))).toEqual({ x: -1, yaw: 1 });
    expect(keyboardAxes(new Set(['d']))).toEqual({ x: 0, yaw: -1 });
  });

  it('drops axes inside the dead zone and keeps full throw', () => {
    expect(applyAxisDeadzone(0.2)).toBe(0);
    expect(applyAxisDeadzone(1)).toBe(1);
    expect(combineAxes({ x: 1, yaw: 0 }, { x: 1, yaw: -1 })).toEqual({ x: 1, yaw: -1 });
  });
});
