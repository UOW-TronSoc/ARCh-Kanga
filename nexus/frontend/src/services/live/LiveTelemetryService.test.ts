import { afterEach, describe, expect, it, vi } from 'vitest';
import { LiveTelemetryService, type TelemetrySocket } from './LiveTelemetryService';

class FakeSocket implements TelemetrySocket {
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  constructor(readonly url: string) {}
  close() {
    this.onclose?.();
  }
  send(data: string) {
    this.sent.push(data);
  }
  server(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function message(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    sequence: 1,
    serverTimestamp: '2026-11-22T07:00:00.000Z',
    rosAvailable: true,
    whsAvailable: true,
    drivestop: true,
    ...overrides,
  };
}

describe('LiveTelemetryService', () => {
  const sockets: FakeSocket[] = [];
  let service: LiveTelemetryService | null = null;
  const telemetry = () => sockets.filter((socket) => socket.url.includes('/ws/telemetry')).at(-1)!;

  afterEach(() => {
    service?.stop();
    vi.useRealTimers();
  });

  function start() {
    vi.useFakeTimers();
    sockets.length = 0;
    service = new LiveTelemetryService({
      url: 'ws://nexus/ws/telemetry',
      socketFactory: (url) => {
        const socket = new FakeSocket(url);
        sockets.push(socket);
        return socket;
      },
    });
    return service;
  }

  it('waits for WHS and never substitutes demo telemetry', () => {
    const live = start();
    expect(live.getSnapshot().safety.drivestop).toBeNull();
    expect(live.getSnapshot().safety.whsOnline).toBe(false);
    expect(live.getSnapshot().rover.battery.percentage).toBeNull();
    telemetry().server(message({ sequence: 4, drivestop: true }));
    expect(live.getSnapshot().safety.drivestop).toBe(true);
    expect(live.getSnapshot().safety.whsOnline).toBe(true);
    expect(live.getSnapshot().rover.battery.percentage).toBeNull();
  });

  it('keeps an unchanged value current and marks publisher loss stale', () => {
    const live = start();
    telemetry().server(message({ sequence: 2, drivestop: false }));
    telemetry().server(message({ sequence: 8, drivestop: false }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    expect(live.getSnapshot().connection.stale).toBe(false);
    telemetry().server(message({ sequence: 3, drivestop: true }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    telemetry().server(message({ sequence: 9, drivestop: false, whsAvailable: false }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    expect(live.getSnapshot().safety.whsOnline).toBe(false);
    expect(live.getSnapshot().connection.stale).toBe(true);
  });

  it('accepts a restarted sequence after reconnect', () => {
    const live = start();
    telemetry().server(message({ sequence: 20, drivestop: true }));
    telemetry().close();
    expect(live.getSnapshot().connection.phase).toBe('reconnecting');
    expect(live.getSnapshot().safety.drivestop).toBe(true);
    vi.advanceTimersByTime(500);
    telemetry().server(message({ sequence: 1, drivestop: false }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    expect(live.getSnapshot().connection.phase).toBe('connected');
  });

  it('keeps arming across telemetry and sends holder commands', () => {
    const live = start();
    telemetry().server(message({ drivestop: false, closedLoop: true, closedLoopAvailable: true }));
    const control = sockets.find((socket) => socket.url.includes('/ws/control'))!;
    control.server({ type: 'state', role: 'holder', notice: null, error: null, armed: true });
    telemetry().server(message({ sequence: 2, drivestop: false, closedLoop: true, closedLoopAvailable: true }));
    expect(live.getSnapshot().drive.inputArmed).toBe(true);
    expect(live.getSnapshot().safety.closedLoop).toBe(true);
    live.setSpeedLimit(90);
    live.sendDrive({ x: 1, yaw: 0, scale: 90 });
    live.toggleInputArm();
    expect(live.getSnapshot().drive.speedLimitPercent).toBe(90);
    expect(control.sent.map((body) => JSON.parse(body).type)).toEqual(['drive', 'disarm']);
  });

  it('treats a missing mode publisher as unknown and blocks a preserved arm', () => {
    const live = start();
    telemetry().server(message({ drivestop: false, closedLoop: true, closedLoopAvailable: true }));
    const control = sockets.find((socket) => socket.url.includes('/ws/control'))!;
    control.server({ type: 'state', role: 'holder', notice: null, error: null, armed: true });
    telemetry().server(message({ sequence: 2, drivestop: false, closedLoop: null, closedLoopAvailable: false }));
    expect(live.getSnapshot().safety.closedLoop).toBeNull();
    expect(live.getSnapshot().drive.inputArmed).toBe(false);
    expect(control.sent.map((body) => JSON.parse(body).type)).toEqual(['disarm']);
  });

  it('keeps wheel velocities stale until a new sample arrives', () => {
    const live = start();
    telemetry().server(message({
      drivestop: true,
      wheelsFreshness: 'unavailable',
    }));
    expect(live.getSnapshot().rover.wheels).toEqual([]);
    telemetry().server(message({
      sequence: 2,
      wheels: [{ name: 'wheel_fl_joint', velocity: 1.5 }],
      wheelsFreshness: 'fresh',
    }));
    expect(live.getSnapshot().rover.wheels[0]).toMatchObject({ velocity: 1.5, freshness: 'fresh' });
    telemetry().server(message({
      sequence: 3,
      drivestop: true,
      whsAvailable: true,
      wheels: [{ name: 'wheel_fl_joint', velocity: 1.5 }],
      wheelsFreshness: 'stale',
    }));
    expect(live.getSnapshot().rover.wheels[0].freshness).toBe('stale');
    expect(live.getSnapshot().safety.whsOnline).toBe(true);
  });
});