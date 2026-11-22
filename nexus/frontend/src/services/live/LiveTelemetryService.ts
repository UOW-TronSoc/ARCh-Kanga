import type { AppDataService, AppSnapshotListener } from '../contracts/AppDataService';
import type { AppSnapshot } from '../../types';
import { createWaitingLiveSnapshot } from './liveSnapshot';

export interface TelemetrySocket {
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  close(): void;
  send?(data: string): void;
}

interface TelemetryMessage {
  schemaVersion: number;
  sequence: number;
  serverTimestamp: string;
  rosAvailable: boolean;
  whsAvailable: boolean;
  drivestop: boolean | null;
  closedLoop?: boolean | null;
  closedLoopAvailable?: boolean;
  wheels?: { name: string; velocity: number }[];
  wheelsFreshness?: 'fresh' | 'stale' | 'unavailable';
}

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 5_000;

export class LiveTelemetryService implements AppDataService {
  private snapshot: AppSnapshot = createWaitingLiveSnapshot();
  private readonly listeners = new Set<AppSnapshotListener>();
  private lastSequence: number | null = null;
  private backoff = INITIAL_BACKOFF_MS;
  private stopped = false;
  private active: TelemetrySocket | null = null;
  private controlSocket: TelemetrySocket | null = null;
  private controlRetry: number | null = null;
  private retry: number | null = null;
  private readonly url: string;
  private readonly controlUrl: string;
  private readonly socketFactory: (url: string) => TelemetrySocket;
  private readonly schedule: (callback: () => void, delayMs: number) => number;
  private readonly cancel: (handle: number) => void;

  constructor(options: {
    url?: string;
    controlUrl?: string;
    autostart?: boolean;
    socketFactory?: (url: string) => TelemetrySocket;
    schedule?: (callback: () => void, delayMs: number) => number;
    cancel?: (handle: number) => void;
  } = {}) {
    this.url = options.url ?? defaultTelemetryUrl();
    this.controlUrl = options.controlUrl ?? defaultControlUrl();
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url) as TelemetrySocket);
    this.schedule = options.schedule ?? ((callback, delayMs) => window.setTimeout(callback, delayMs));
    this.cancel = options.cancel ?? ((handle) => window.clearTimeout(handle));
    if (options.autostart !== false) this.start();
  }

  start() {
    if (this.active || this.controlSocket) return;
    this.stopped = false;
    this.connect();
    this.connectControl();
  }

  getSnapshot = () => this.snapshot;

  subscribe = (listener: AppSnapshotListener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  stop() {
    this.stopped = true;
    if (this.retry !== null) this.cancel(this.retry);
    if (this.controlRetry !== null) this.cancel(this.controlRetry);
    const socket = this.active;
    const control = this.controlSocket;
    this.active = null;
    this.controlSocket = null;
    socket?.close();
    control?.close();
  }

  assertDrivestop = () => {
    this.sendControl({ type: 'assert' });
  };

  releaseDrivestop = () => {
    this.sendControl({ type: 'release' });
  };

  takeControl = () => {
    this.sendControl({ type: 'take' });
  };
  toggleClosedLoop = () => {
    if (this.snapshot.control?.role !== 'holder') return;
    const enable = this.snapshot.safety.closedLoop !== true;
    this.sendControl({ type: 'mode', enable });
    if (!enable) this.disarmLocally();
  };

  toggleInputArm = () => {
    this.sendControl({ type: this.snapshot.drive.inputArmed ? 'disarm' : 'arm' });
  };

  disarmDriveInput = () => {
    this.sendControl({ type: 'disarm' });
    this.disarmLocally();
  };

  sendDrive = (frame: { x: number; yaw: number; scale: number }) => {
    this.sendControl({ type: 'drive', ...frame });
  };

  clearErrors = () => {
    if (this.snapshot.control?.role !== 'holder') return;
    this.sendControl({ type: 'clear_errors' });
  };

  private sendControl(message: Record<string, unknown>) {
    const socket = this.controlSocket as TelemetrySocket & { send?: (data: string) => void };
    socket?.send?.(JSON.stringify(message));
  }

  private connectControl() {
    if (this.stopped) return;
    const socket = this.socketFactory(this.controlUrl);
    this.controlSocket = socket;
    socket.onmessage = (event) => {
      if (socket !== this.controlSocket) return;
      const message = parseControl(event.data);
      if (!message) return;
      this.snapshot = {
        ...this.snapshot,
        control: {
          role: message.role,
          notice: message.notice,
          error: message.error,
        },
        drive: { ...this.snapshot.drive, inputArmed: message.armed === true },
      };
      this.emit();
    };
    socket.onclose = () => {
      if (socket !== this.controlSocket || this.stopped) return;
      this.controlSocket = null;
      this.snapshot = {
        ...this.snapshot,
        control: { role: 'observer', notice: null, error: null },
        drive: { ...this.snapshot.drive, inputArmed: false },
      };
      this.emit();
      this.controlRetry = this.schedule(() => this.connectControl(), this.backoff);
    };
  }
  setSpeedLimit = (percent: number) => {
    const speedLimitPercent = Math.max(0, Math.min(100, percent));
    this.snapshot = { ...this.snapshot, drive: { ...this.snapshot.drive, speedLimitPercent } };
    this.emit();
  };

  private disarmLocally() {
    this.snapshot = { ...this.snapshot, drive: { ...this.snapshot.drive, inputArmed: false } };
    this.emit();
  }

  private connect() {
    if (this.stopped) return;
    this.lastSequence = null;
    const socket = this.socketFactory(this.url);
    this.active = socket;
    socket.onmessage = (event) => {
      if (socket !== this.active) return;
      const message = parseMessage(event.data);
      if (!message) return;
      if (this.lastSequence !== null && message.sequence <= this.lastSequence) return;
      this.lastSequence = message.sequence;
      this.backoff = INITIAL_BACKOFF_MS;
      const wasArmed = this.snapshot.drive.inputArmed;
      const modeReady = message.drivestop === false && message.closedLoopAvailable === true && message.closedLoop === true;
      this.snapshot = {
        ...this.snapshot,
        safety: {
          ...this.snapshot.safety,
          drivestop: message.drivestop,
          whsOnline: message.whsAvailable,
          closedLoop: message.closedLoopAvailable ? (message.closedLoop ?? null) : null,
        },
        drive: {
          ...this.snapshot.drive,
          inputArmed: wasArmed && modeReady,
        },
        connection: {
          backendMode: 'live',
          phase: 'connected',
          latencyMs: null,
          lastUpdate: message.serverTimestamp,
          stale: !message.rosAvailable || !message.whsAvailable,
        },
        rover: {
          ...this.snapshot.rover,
          sequence: message.sequence,
          serverTimestamp: message.serverTimestamp,
          wheels: message.wheelsFreshness === 'fresh' || message.wheelsFreshness === 'stale'
            ? (message.wheels ?? []).map((wheel) => ({
              name: wheel.name,
              position: null,
              velocity: wheel.velocity,
              freshness: message.wheelsFreshness === 'stale' ? 'stale' as const : 'fresh' as const,
            }))
            : [],
        },
      };
      this.emit();
      if (wasArmed && !modeReady) this.sendControl({ type: 'disarm' });
    };
    socket.onclose = () => {
      if (socket !== this.active || this.stopped) return;
      this.active = null;
      const wasArmed = this.snapshot.drive.inputArmed;
      this.snapshot = {
        ...this.snapshot,
        drive: { ...this.snapshot.drive, inputArmed: false },
        connection: { ...this.snapshot.connection, phase: 'reconnecting', stale: true },
      };
      if (wasArmed) this.sendControl({ type: 'disarm' });
      this.emit();
      this.retry = this.schedule(() => this.connect(), this.backoff);
      this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF_MS);
    };
  }

  private emit() {
    this.listeners.forEach((listener) => listener(this.snapshot));
  }
}

function parseMessage(raw: string): TelemetryMessage | null {
  try {
    const parsed = JSON.parse(raw) as Partial<TelemetryMessage>;
    if (parsed.schemaVersion !== 1 || typeof parsed.sequence !== 'number') return null;
    if (typeof parsed.serverTimestamp !== 'string') return null;
    if (typeof parsed.rosAvailable !== 'boolean' || typeof parsed.whsAvailable !== 'boolean') return null;
    if (parsed.drivestop !== null && typeof parsed.drivestop !== 'boolean') return null;
    if (parsed.closedLoop !== undefined && parsed.closedLoop !== null && typeof parsed.closedLoop !== 'boolean') return null;
    return {
      schemaVersion: 1,
      sequence: parsed.sequence,
      serverTimestamp: parsed.serverTimestamp,
      rosAvailable: parsed.rosAvailable,
      whsAvailable: parsed.whsAvailable,
      drivestop: parsed.drivestop ?? null,
      closedLoop: parsed.closedLoop ?? null,
      closedLoopAvailable: parsed.closedLoopAvailable === true,
      wheels: parsed.wheels ?? [],
      wheelsFreshness: parsed.wheelsFreshness === 'fresh' || parsed.wheelsFreshness === 'stale'
        ? parsed.wheelsFreshness
        : 'unavailable',
    };
  } catch {
    return null;
  }
}

function parseControl(raw: string): { role: 'observer' | 'holder'; notice: string | null; error: string | null; armed: boolean } | null {
  try {
    const parsed = JSON.parse(raw) as { type?: string; role?: string; notice?: string | null; error?: string | null; armed?: boolean };
    if (parsed.type !== 'state' || (parsed.role !== 'observer' && parsed.role !== 'holder')) return null;
    return { role: parsed.role, notice: parsed.notice ?? null, error: parsed.error ?? null, armed: parsed.armed === true };
  } catch {
    return null;
  }
}

export function defaultTelemetryUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/telemetry`;
}

export function defaultControlUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/control`;
}
