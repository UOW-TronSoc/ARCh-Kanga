import { describe, expect, it } from 'vitest';
import { initialAppSnapshot } from '../../fixtures';
import {
  buildCriticalSnapshot,
  buildDisconnectedSnapshot,
  buildOperableSnapshot,
} from '../../test/snapshotBuilders';
import { MockAppDataService } from './MockAppDataService';

function operableService() {
  return new MockAppDataService(buildOperableSnapshot());
}

describe('MockAppDataService drive state machine', () => {
  it('starts with drivestop asserted, ODrive idle, and drive input disabled', () => {
    const snapshot = new MockAppDataService().getSnapshot();
    expect(snapshot.safety.drivestop).toBe(true);
    expect(snapshot.safety.closedLoop).toBe(false);
    expect(snapshot.drive.inputArmed).toBe(false);
    expect(snapshot).toEqual(initialAppSnapshot);
  });

  it('releases drivestop without arming input or closing the loop', () => {
    const service = new MockAppDataService();
    service.releaseDrivestop();
    const snapshot = service.getSnapshot();
    expect(snapshot.safety.drivestop).toBe(false);
    expect(snapshot.drive.inputArmed).toBe(false);
    expect(snapshot.safety.closedLoop).toBe(false);
  });

  it('asserting drivestop disables input and returns ODrive to idle', () => {
    const service = operableService();
    service.toggleInputArm();
    service.assertDrivestop();
    const snapshot = service.getSnapshot();
    expect(snapshot.safety.drivestop).toBe(true);
    expect(snapshot.drive.inputArmed).toBe(false);
    expect(snapshot.safety.closedLoop).toBe(false);
  });

  it('disarms drive input without changing closed loop', () => {
    const service = operableService();
    service.toggleInputArm();
    service.disarmDriveInput();
    const snapshot = service.getSnapshot();
    expect(snapshot.drive.inputArmed).toBe(false);
    expect(snapshot.safety.closedLoop).toBe(true);
  });

  it('enables closed loop then input when arming from idle', () => {
    const service = operableService();
    service.toggleInputArm();
    const snapshot = service.getSnapshot();
    expect(snapshot.safety.closedLoop).toBe(true);
    expect(snapshot.drive.inputArmed).toBe(true);
  });

  it('disabling input leaves ODrive in closed loop', () => {
    const service = operableService();
    service.toggleInputArm();
    service.toggleInputArm();
    const snapshot = service.getSnapshot();
    expect(snapshot.drive.inputArmed).toBe(false);
    expect(snapshot.safety.closedLoop).toBe(true);
  });

  it('returning ODrive to idle disables input', () => {
    const service = operableService();
    service.toggleInputArm();
    service.toggleClosedLoop();
    const snapshot = service.getSnapshot();
    expect(snapshot.safety.closedLoop).toBe(false);
    expect(snapshot.drive.inputArmed).toBe(false);
  });

  it('blocks enabling input while drivestop is active', () => {
    const service = new MockAppDataService();
    service.toggleInputArm();
    expect(service.getSnapshot().drive.inputArmed).toBe(false);
  });

  it('blocks enabling input while WHS is offline', () => {
    const service = new MockAppDataService(buildDisconnectedSnapshot());
    service.toggleInputArm();
    expect(service.getSnapshot().drive.inputArmed).toBe(false);
  });

  it('blocks enabling input when critical faults are present', () => {
    const service = new MockAppDataService(buildCriticalSnapshot());
    service.toggleInputArm();
    expect(service.getSnapshot().drive.inputArmed).toBe(false);
  });

  it('cannot enable closed loop while drivestop is active', () => {
    const service = new MockAppDataService();
    service.toggleClosedLoop();
    expect(service.getSnapshot().safety.closedLoop).toBe(false);
  });
});