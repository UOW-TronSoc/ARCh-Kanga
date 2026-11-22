import type { AppSnapshot } from '../../types';

export function createWaitingLiveSnapshot(): AppSnapshot {
  return {
    connection: {
      backendMode: 'live',
      phase: 'connecting',
      latencyMs: null,
      lastUpdate: null,
      stale: false,
    },
    safety: { drivestop: null, whsOnline: false, closedLoop: null, faults: [] },
    drive: { speedLimitPercent: 0, inputArmed: false },
    control: { role: 'observer', notice: null, error: null },
    rover: {
      sequence: 0,
      serverTimestamp: '',
      freshness: 'unavailable',
      battery: { percentage: null, currentDrawA: null },
      body: {
        positionM: { x: 0, y: 0, z: 0 },
        yawDeg: 0,
        pitchDeg: null,
        linearSpeedMps: 0,
        yawRateDegS: 0,
      },
      wheels: [],
      suspension: [],
      motors: [],
    },
  };
}
