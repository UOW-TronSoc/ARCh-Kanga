import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { AppProviders } from '../../app/providers';
import { MockAppDataService } from '../../services/mock/MockAppDataService';
import { buildOperableSnapshot } from '../../test/snapshotBuilders';
import { ControlFocusProvider } from './ControlFocusProvider';
import { OperatorInputCoordinator } from './OperatorInputCoordinator';
import { BUTTON_ASSERT_DRIVESTOP, BUTTON_DRIVE_INPUT } from './gamepad';

function mockGamepad(index: number, buttons: boolean[]): Gamepad {
  return {
    index,
    connected: true,
    id: 'USB Gamepad',
    mapping: '',
    timestamp: Date.now(),
    axes: [],
    buttons: buttons.map((pressed) => ({ pressed, touched: pressed, value: pressed ? 1 : 0 })),
    hapticActuators: [],
    vibrationActuator: null,
  } as unknown as Gamepad;
}

function renderCoordinator(service = new MockAppDataService(buildOperableSnapshot()), route = '/rover') {
  return render(
    <AppProviders service={service}>
      <MemoryRouter initialEntries={[route]}>
        <ControlFocusProvider>
          <OperatorInputCoordinator>
            <p>child</p>
          </OperatorInputCoordinator>
        </ControlFocusProvider>
      </MemoryRouter>
    </AppProviders>,
  );
}

class MockGamepadEvent extends Event {
  readonly gamepad: Gamepad;

  constructor(type: string, init: { gamepad: Gamepad }) {
    super(type);
    this.gamepad = init.gamepad;
  }
}

describe('OperatorInputCoordinator', () => {
  beforeEach(() => {
    vi.stubGlobal('GamepadEvent', MockGamepadEvent);
    vi.stubGlobal('navigator', {
      getGamepads: () => [],
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('mounts without a connected gamepad', () => {
    renderCoordinator();
    expect(screen.getByText('child')).toBeInTheDocument();
  });

  it('routes gamepad B0/B1 shortcuts through the guarded service on drivetrain focus', () => {
    const service = new MockAppDataService(buildOperableSnapshot());
    const toggleSpy = vi.spyOn(service, 'toggleInputArm');
    const drivestopSpy = vi.spyOn(service, 'assertDrivestop');
    const pads: (Gamepad | null)[] = [mockGamepad(0, [false, false])];
    vi.stubGlobal('navigator', { getGamepads: () => pads });

    renderCoordinator(service);

    act(() => {
      pads[0] = mockGamepad(0, [true, false]);
      window.dispatchEvent(new Event('focus'));
    });
    expect(toggleSpy).toHaveBeenCalled();
    toggleSpy.mockClear();

    act(() => {
      pads[0] = mockGamepad(0, [false, true]);
      window.dispatchEvent(new Event('focus'));
    });
    expect(drivestopSpy).toHaveBeenCalled();
    expect(pads[0]?.buttons[BUTTON_DRIVE_INPUT].pressed).toBe(false);
    expect(pads[0]?.buttons[BUTTON_ASSERT_DRIVESTOP].pressed).toBe(true);
  });

  it('suppresses B0 while focus is inactive but still asserts drivestop on B1', () => {
    const service = new MockAppDataService(buildOperableSnapshot());
    const toggleSpy = vi.spyOn(service, 'toggleInputArm');
    const drivestopSpy = vi.spyOn(service, 'assertDrivestop');
    const pads: (Gamepad | null)[] = [mockGamepad(0, [false, false])];
    vi.stubGlobal('navigator', { getGamepads: () => pads });

    renderCoordinator(service, '/launch');

    act(() => {
      pads[0] = mockGamepad(0, [true, false]);
      window.dispatchEvent(new Event('focus'));
    });
    expect(toggleSpy).not.toHaveBeenCalled();

    act(() => {
      pads[0] = mockGamepad(0, [false, true]);
      window.dispatchEvent(new Event('focus'));
    });
    expect(drivestopSpy).toHaveBeenCalled();
  });

  it('does not manufacture edges when a secondary gamepad connects', () => {
    const service = new MockAppDataService(buildOperableSnapshot());
    const toggleSpy = vi.spyOn(service, 'toggleInputArm');
    const pads: (Gamepad | null)[] = [mockGamepad(0, [false, false]), null];
    vi.stubGlobal('navigator', { getGamepads: () => pads });

    renderCoordinator(service);

    act(() => {
      window.dispatchEvent(new Event('focus'));
    });

    act(() => {
      pads[1] = mockGamepad(1, [true, false]);
      window.dispatchEvent(new MockGamepadEvent('gamepadconnected', { gamepad: pads[1]! }));
    });

    expect(toggleSpy).not.toHaveBeenCalled();
  });

  it('allows Enter on drivetrain focus and Space globally from inactive focus', () => {
    const service = new MockAppDataService(buildOperableSnapshot());
    const toggleSpy = vi.spyOn(service, 'toggleInputArm');
    const drivestopSpy = vi.spyOn(service, 'assertDrivestop');

    renderCoordinator(service, '/launch');

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Enter', key: 'Enter', bubbles: true }));
    });
    expect(toggleSpy).not.toHaveBeenCalled();

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', key: ' ', bubbles: true }));
    });
    expect(drivestopSpy).toHaveBeenCalled();
  });
});