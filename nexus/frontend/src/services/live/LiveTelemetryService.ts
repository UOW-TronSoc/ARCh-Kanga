import type { AppDataService, AppSnapshotListener } from '../contracts/AppDataService';
import type { AppSnapshot } from '../../types';
import { createWaitingLiveSnapshot } from './liveSnapshot';

export interface TelemetrySocket {
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  close(): void;
}

interface TelemetryMessage {
  schemaVersion: number;
  sequence: number;
  serverTimestamp: string;
  rosAvailable: boolean;
  whsAvailable: boolean;
  drivestop: boolean | null;
}

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 5_000;

export class LiveTelemetryService implements AppDataService {
  readonly commandsEnabled = false;
  private snapshot: AppSnapshot = createWaitingLiveSnapshot();
  private readonly listeners = new Set<AppSnapshotListener>();
  private lastSequence: number | null = null;
  private backoff = INITIAL_BACKOFF_MS;
  private stopped = false;
  private active: TelemetrySocket | null = null;
  private retry: number | null = null;
  private readonly url: string;
  private readonly socketFactory: (url: string) => TelemetrySocket;
  private readonly schedule: (callback: () => void, delayMs: number) => number;
  private readonly cancel: (handle: number) => void;

  constructor(options: {
    url?: string;
    socketFactory?: (url: string) => TelemetrySocket;
    schedule?: (callback: () => void, delayMs: number) => number;
    cancel?: (handle: number) => void;
  } = {}) {
    this.url = options.url ?? defaultTelemetryUrl();
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url) as TelemetrySocket);
    this.schedule = options.schedule ?? ((callback, delayMs) => window.setTimeout(callback, delayMs));
    this.cancel = options.cancel ?? ((handle) => window.clearTimeout(handle));
    this.connect();
  }

  getSnapshot = () => this.snapshot;

  subscribe = (listener: AppSnapshotListener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  stop() {
    this.stopped = true;
    if (this.retry !== null) this.cancel(this.retry);
    const socket = this.active;
    this.active = null;
    socket?.close();
  }

  assertDrivestop = () => undefined;
  releaseDrivestop = () => undefined;
  toggleClosedLoop = () => undefined;
  toggleInputArm = () => undefined;
  disarmDriveInput = () => undefined;
  setSpeedLimit = (percent: number) => {
    void percent;
  };

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
      this.snapshot = {
        ...this.snapshot,
        safety: {
          ...this.snapshot.safety,
          drivestop: message.drivestop,
          whsOnline: message.whsAvailable,
          closedLoop: false,
        },
        drive: { ...this.snapshot.drive, inputArmed: false },
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
          freshness: 'unavailable',
        },
      };
      this.emit();
    };
    socket.onclose = () => {
      if (socket !== this.active || this.stopped) return;
      this.active = null;
      this.snapshot = {
        ...this.snapshot,
        connection: { ...this.snapshot.connection, phase: 'reconnecting', stale: true },
      };
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
    return {
      schemaVersion: 1,
      sequence: parsed.sequence,
      serverTimestamp: parsed.serverTimestamp,
      rosAvailable: parsed.rosAvailable,
      whsAvailable: parsed.whsAvailable,
      drivestop: parsed.drivestop ?? null,
    };
  } catch {
    return null;
  }
}

export function defaultTelemetryUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/telemetry`;
}
