import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { useAppDataService, useAppSnapshot } from '../../app/appDataContext';
import type { DetectedGamepad } from '../../types';
import { focusedActionsForTarget } from './controlProfiles';
import {
  GAMEPAD_POLL_MS,
  processGamepadSafetyButtons,
  readConnectedGamepads,
  resolveTrackedGamepad,
  seedButtonEdges,
  toDetectedGamepad,
} from './gamepad';
import { ZERO, combineAxes, gamepadAxes, keyboardAxes } from './driveInput';
import { handleOperatorKeyDown } from './keyboard';
import { OperatorInputProvider } from './OperatorInputProvider';
import type { OperatorInputState } from './operatorInputState';
import { useControlFocus } from './useControlFocus';

export function OperatorInputCoordinator({ children }: PropsWithChildren) {
  const service = useAppDataService();
  const snapshot = useAppSnapshot();
  const focus = useControlFocus();
  const keysRef = useRef(new Set<string>());
  const armed = snapshot.drive.inputArmed && snapshot.control?.role === 'holder';
  const [gamepad, setGamepad] = useState<DetectedGamepad | null>(null);
  const trackedIndexRef = useRef<number | null>(null);
  const buttonEdgesRef = useRef<boolean[]>([]);
  const lastProcessedIndexRef = useRef<number | null>(null);

  const onAssertDrivestop = useCallback(() => {
    service.assertDrivestop();
  }, [service]);

  const focusedActions = useMemo(
    () => focusedActionsForTarget(focus, service),
    [focus, service],
  );

  const dropTrackedGamepad = useCallback(() => {
    trackedIndexRef.current = null;
    keysRef.current.clear();
    buttonEdgesRef.current = [];
    lastProcessedIndexRef.current = null;
    setGamepad(null);
    service.disarmDriveInput();
  }, [service]);

  const syncGamepad = useCallback(() => {
    const gamepads = readConnectedGamepads();
    const { gamepad: resolved, index, lost } = resolveTrackedGamepad(gamepads, trackedIndexRef.current);
    if (lost) {
      dropTrackedGamepad();
      return;
    }
    trackedIndexRef.current = index;

    if (!resolved) {
      buttonEdgesRef.current = [];
      lastProcessedIndexRef.current = null;
      setGamepad(null);
      return;
    }

    const nextDetected = toDetectedGamepad(resolved);
    setGamepad((prev) => {
      if (prev?.index === nextDetected.index && prev.name === nextDetected.name && prev.mapping === nextDetected.mapping) {
        return prev;
      }
      return nextDetected;
    });

    if (lastProcessedIndexRef.current !== resolved.index) {
      buttonEdgesRef.current = seedButtonEdges(resolved);
      lastProcessedIndexRef.current = resolved.index;
    }

    buttonEdgesRef.current = processGamepadSafetyButtons(resolved, buttonEdgesRef.current, {
      onAssertDrivestop,
      onToggleDriveInput: focusedActions?.onToggleDriveInput,
    });
  }, [dropTrackedGamepad, focusedActions, onAssertDrivestop]);

  useEffect(() => {
    const handleConnect = (event: GamepadEvent) => {
      if (trackedIndexRef.current === null) {
        trackedIndexRef.current = event.gamepad.index;
        buttonEdgesRef.current = seedButtonEdges(event.gamepad);
        lastProcessedIndexRef.current = event.gamepad.index;
      }
      syncGamepad();
    };

    const handleDisconnect = (event: GamepadEvent) => {
      if (event.gamepad.index !== trackedIndexRef.current) return;
      dropTrackedGamepad();
    };

    window.addEventListener('gamepadconnected', handleConnect);
    window.addEventListener('gamepaddisconnected', handleDisconnect);
    window.addEventListener('focus', syncGamepad);

    syncGamepad();
    const interval = window.setInterval(syncGamepad, GAMEPAD_POLL_MS);

    return () => {
      window.removeEventListener('gamepadconnected', handleConnect);
      window.removeEventListener('gamepaddisconnected', handleDisconnect);
      window.removeEventListener('focus', syncGamepad);
      window.clearInterval(interval);
    };
  }, [dropTrackedGamepad, syncGamepad]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      handleOperatorKeyDown(event, {
        onAssertDrivestop,
        onToggleDriveInput: focusedActions?.onToggleDriveInput,
      });
    };
    const trackMotionKey = (event: KeyboardEvent, down: boolean) => {
      const key = event.key.toLowerCase();
      if (!['w', 'a', 's', 'd'].includes(key)) return;
      if (!down) {
        keysRef.current.delete(key);
        return;
      }
      const target = event.target;
      if (target instanceof HTMLElement) {
        const tag = target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable) return;
      }
      event.preventDefault();
      keysRef.current.add(key);
    };
    const onMotionDown = (event: KeyboardEvent) => trackMotionKey(event, true);
    const onMotionUp = (event: KeyboardEvent) => trackMotionKey(event, false);
    const keys = keysRef.current;
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keydown', onMotionDown);
    window.addEventListener('keyup', onMotionUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keydown', onMotionDown);
      window.removeEventListener('keyup', onMotionUp);
      keys.clear();
    };
  }, [focusedActions, onAssertDrivestop]);

  useEffect(() => {
    if (!armed) keysRef.current.clear();
  }, [armed]);

  useEffect(() => {
    if (!armed) return undefined;
    const timer = window.setInterval(() => {
      const pads = readConnectedGamepads();
      const current = trackedIndexRef.current === null ? null : pads[trackedIndexRef.current];
      const axes = combineAxes(keyboardAxes(keysRef.current), current ? gamepadAxes(current) : ZERO);
      service.sendDrive({ ...axes, scale: snapshot.drive.speedLimitPercent });
    }, 50);
    return () => window.clearInterval(timer);
  }, [armed, service, snapshot.drive.speedLimitPercent]);

  useEffect(() => {
    const release = () => {
      keysRef.current.clear();
      if (snapshot.drive.inputArmed) service.disarmDriveInput();
    };
    const onVisibility = () => {
      if (document.hidden) release();
    };
    window.addEventListener('blur', release);
    document.addEventListener('visibilitychange', onVisibility);
    if (focus.kind !== 'drivetrain' && snapshot.drive.inputArmed) release();
    return () => {
      window.removeEventListener('blur', release);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [focus.kind, service, snapshot.drive.inputArmed]);

  const value = useMemo<OperatorInputState>(() => ({ gamepad }), [gamepad]);

  return <OperatorInputProvider value={value}>{children}</OperatorInputProvider>;
}