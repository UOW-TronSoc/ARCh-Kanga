import { afterEach, describe, expect, it, vi } from 'vitest';
import { drivestopPresentation } from './drivestopPresentation';
import { LiveTelemetryService, type TelemetrySocket } from './LiveTelemetryService';

class FakeSocket implements TelemetrySocket {
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  close() {
    this.closed = true;
    this.onclose?.();
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

  afterEach(() => {
    service?.stop();
    vi.useRealTimers();
  });

  function start() {
    vi.useFakeTimers();
    sockets.length = 0;
    service = new LiveTelemetryService({
      url: 'ws://nexus/ws/telemetry',
      socketFactory: () => {
        const socket = new FakeSocket();
        sockets.push(socket);
        return socket;
      },
    });
    return service;
  }

  it('waits for WHS and never substitutes demo telemetry', () => {
    const live = start();
    expect(drivestopPresentation(live.getSnapshot())).toBe('waiting');
    expect(live.getSnapshot().rover.battery.percentage).toBeNull();
    expect(live.getSnapshot().rover.freshness).toBe('unavailable');
    sockets[0]?.server(message({ sequence: 4, drivestop: true }));
    expect(drivestopPresentation(live.getSnapshot())).toBe('asserted');
    expect(live.getSnapshot().rover.battery.percentage).toBeNull();
  });

  it('keeps an unchanged value current and marks publisher loss stale', () => {
    const live = start();
    sockets[0]?.server(message({ sequence: 2, drivestop: false }));
    sockets[0]?.server(message({ sequence: 8, drivestop: false }));
    expect(drivestopPresentation(live.getSnapshot())).toBe('released');
    sockets[0]?.server(message({ sequence: 3, drivestop: true }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    sockets[0]?.server(message({ sequence: 9, drivestop: false, whsAvailable: false }));
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    expect(drivestopPresentation(live.getSnapshot())).toBe('stale');
  });

  it('accepts a restarted sequence after reconnect', () => {
    const live = start();
    sockets[0]?.server(message({ sequence: 20, drivestop: true }));
    sockets[0]?.close();
    expect(drivestopPresentation(live.getSnapshot())).toBe('stale');
    vi.advanceTimersByTime(500);
    sockets[1]?.server(message({ sequence: 1, drivestop: false }));
    expect(drivestopPresentation(live.getSnapshot())).toBe('released');
  });

  it('does not send drivestop or motion commands', () => {
    const live = start();
    sockets[0]?.server(message({ drivestop: false }));
    live.assertDrivestop();
    live.releaseDrivestop();
    live.toggleClosedLoop();
    live.toggleInputArm();
    live.setSpeedLimit(90);
    expect(live.getSnapshot().safety.drivestop).toBe(false);
    expect(live.getSnapshot().drive.inputArmed).toBe(false);
  });
});