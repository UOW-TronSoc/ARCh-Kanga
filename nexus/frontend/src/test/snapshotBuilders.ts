import { initialAppSnapshot } from '../fixtures';
import type { AppSnapshot, Fault } from '../types';

function cloneBase(): AppSnapshot {
  return structuredClone(initialAppSnapshot);
}

export function buildOperableSnapshot(): AppSnapshot {
  return {
    ...cloneBase(),
    safety: { ...cloneBase().safety, drivestop: false },
  };
}

export function buildDrivestopSnapshot(): AppSnapshot {
  return cloneBase();
}

export function buildDisconnectedSnapshot(): AppSnapshot {
  const base = cloneBase();
  return {
    ...base,
    connection: { backendMode: 'mock', phase: 'disconnected', latencyMs: null, lastUpdate: '42s ago', stale: true },
    safety: { ...base.safety, whsOnline: false, closedLoop: false },
    rover: { ...base.rover, freshness: 'unavailable' },
  };
}

export function buildCriticalSnapshot(): AppSnapshot {
  const base = buildOperableSnapshot();
  const fault: Fault = {
    id: 'motor-fr-encoder',
    title: 'Front-right encoder fault',
    detail: 'Position estimate is unavailable. Drive input has been inhibited.',
    severity: 'critical',
  };
  return {
    ...base,
    safety: { ...base.safety, faults: [fault] },
    rover: {
      ...base.rover,
      motors: base.rover.motors.map((motor) => (motor.id === 'fr' ? { ...motor, state: 'fault' as const } : motor)),
    },
  };
}

export function buildStaleSnapshot(): AppSnapshot {
  const base = buildOperableSnapshot();
  return {
    ...base,
    connection: { ...base.connection, latencyMs: 620, lastUpdate: '8s ago', stale: true },
    rover: {
      ...base.rover,
      freshness: 'stale',
      wheels: base.rover.wheels.map((wheel) => ({ ...wheel, freshness: 'stale' as const })),
    },
  };
}