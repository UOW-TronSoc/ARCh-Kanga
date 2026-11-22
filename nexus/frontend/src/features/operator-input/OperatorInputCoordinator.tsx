import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { useAppDataService } from '../../app/appDataContext';
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
import { handleOperatorKeyDown } from './keyboard';
import { OperatorInputProvider } from './OperatorInputProvider';
import type { OperatorInputState } from './operatorInputState';
import { useControlFocus } from './useControlFocus';

export function OperatorInputCoordinator({ children }: PropsWithChildren) {
  const service = useAppDataService();
  const focus = useControlFocus();
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

  const syncGamepad = useCallback(() => {
    const gamepads = readConnectedGamepads();
    const { gamepad: resolved, index } = resolveTrackedGamepad(gamepads, trackedIndexRef.current);
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
  }, [focusedActions, onAssertDrivestop]);

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
      trackedIndexRef.current = null;
      buttonEdgesRef.current = [];
      lastProcessedIndexRef.current = null;
      syncGamepad();
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
  }, [syncGamepad]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      handleOperatorKeyDown(event, {
        onAssertDrivestop,
        onToggleDriveInput: focusedActions?.onToggleDriveInput,
      });
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [focusedActions, onAssertDrivestop]);

  const value = useMemo<OperatorInputState>(() => ({ gamepad }), [gamepad]);

  return <OperatorInputProvider value={value}>{children}</OperatorInputProvider>;
}