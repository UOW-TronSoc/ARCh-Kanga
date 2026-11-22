import type { AppSnapshot } from '../types';

const wheels = ['Front left', 'Rear left', 'Rear right', 'Front right'].map((label, index) => ({
  name: label,
  position: [1.28, 1.21, 1.19, 1.3][index],
  velocity: [24.8, 24.2, 24.3, 24.9][index],
  freshness: 'fresh' as const,
}));

const motors = ['FL', 'RL', 'RR', 'FR'].map((label, index) => ({
  id: label.toLowerCase(),
  label,
  wheelJointName: wheels[index].name,
  temperatureC: [38, 41, 39, 40][index],
  busVoltageV: 47.8,
  velocityRpm: [238, 232, 234, 241][index],
  state: 'nominal' as const,
}));

/** Safe mock startup: drivestop asserted, ODrive idle, drive input disabled. */
export const initialAppSnapshot: AppSnapshot = {
  connection: {
    backendMode: 'mock', phase: 'connected', latencyMs: 18, lastUpdate: 'just now', stale: false,
  },
  safety: { drivestop: true, whsOnline: true, closedLoop: false, faults: [] },
  drive: { speedLimitPercent: 42, inputArmed: false },
  rover: {
    sequence: 1842,
    serverTimestamp: '2026-11-17T10:24:51+11:00',
    freshness: 'fresh',
    battery: { percentage: 78, currentDrawA: 12.4 },
    body: {
      positionM: { x: 12.4, y: -3.8, z: 0.16 }, yawDeg: 68.2, pitchDeg: 4.6, linearSpeedMps: 0.74, yawRateDegS: -2.1,
    },
    wheels,
    suspension: wheels.map((wheel, index) => ({ ...wheel, position: [0.03, -0.01, 0.02, 0.01][index], velocity: 0 })),
    motors,
  },
};