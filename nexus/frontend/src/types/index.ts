export type BackendMode = 'mock' | 'live';
export type ConnectionPhase = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
export type Freshness = 'fresh' | 'stale' | 'unavailable';
export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export type RecognizedGamepadMapping = 'logitech-extreme-3d' | 'generic-gamepad';

export interface JointState {
  name: string;
  position: number | null;
  /** Joint angular velocity in radians per second. */
  velocity: number | null;
  freshness: Freshness;
}

export interface MotorSummary {
  id: string;
  label: string;
  wheelJointName: string;
  temperatureC: number | null;
  busVoltageV: number | null;
  velocityRpm: number | null;
  state: 'nominal' | 'warning' | 'fault' | 'unavailable';
}

export interface RoverSnapshot {
  sequence: number;
  serverTimestamp: string;
  freshness: Freshness;
  battery: { percentage: number | null; currentDrawA: number | null };
  body: {
    positionM: { x: number; y: number; z: number };
    yawDeg: number;
    pitchDeg: number | null;
    linearSpeedMps: number;
    yawRateDegS: number;
  };
  wheels: JointState[];
  suspension: JointState[];
  motors: MotorSummary[];
}

export interface Fault {
  id: string;
  title: string;
  detail: string;
  severity: 'warning' | 'critical';
}

export interface SafetyState {
  drivestop: boolean | null;
  whsOnline: boolean;
  closedLoop: boolean;
  faults: Fault[];
}

export interface ConnectionState {
  backendMode: BackendMode;
  phase: ConnectionPhase;
  latencyMs: number | null;
  lastUpdate: string | null;
  stale: boolean;
}

export interface DriveControlState {
  speedLimitPercent: number;
  inputArmed: boolean;
}

export interface AppSnapshot {
  rover: RoverSnapshot;
  safety: SafetyState;
  connection: ConnectionState;
  drive: DriveControlState;
}

export type { ControlTarget } from './controlFocus';

export interface DetectedGamepad {
  index: number;
  name: string;
  mapping: RecognizedGamepadMapping;
}