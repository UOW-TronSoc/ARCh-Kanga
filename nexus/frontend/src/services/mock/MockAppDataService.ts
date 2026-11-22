import { initialAppSnapshot } from '../../fixtures';
import type { AppDataService, AppSnapshotListener } from '../contracts/AppDataService';
import type { AppSnapshot } from '../../types';

export class MockAppDataService implements AppDataService {
  readonly commandsEnabled = true;
  private snapshot: AppSnapshot;
  private readonly listeners = new Set<AppSnapshotListener>();

  constructor(initialSnapshot: AppSnapshot = initialAppSnapshot) {
    this.snapshot = structuredClone(initialSnapshot);
  }

  getSnapshot = () => this.snapshot;

  subscribe = (listener: AppSnapshotListener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  assertDrivestop = () => {
    this.update({
      safety: { ...this.snapshot.safety, drivestop: true, closedLoop: false },
      drive: { ...this.snapshot.drive, inputArmed: false },
    });
  };

  releaseDrivestop = () => {
    this.update({ safety: { ...this.snapshot.safety, drivestop: false } });
  };

  toggleClosedLoop = () => {
    if (!this.snapshot.safety.whsOnline || this.snapshot.safety.drivestop) return;
    if (this.snapshot.safety.closedLoop) {
      this.update({
        safety: { ...this.snapshot.safety, closedLoop: false },
        drive: { ...this.snapshot.drive, inputArmed: false },
      });
      return;
    }
    this.update({ safety: { ...this.snapshot.safety, closedLoop: true } });
  };

  toggleInputArm = () => {
    if (this.snapshot.drive.inputArmed) {
      this.update({ drive: { ...this.snapshot.drive, inputArmed: false } });
      return;
    }
    if (this.inputEnableBlocked()) return;
    if (!this.snapshot.safety.closedLoop) {
      this.update({
        safety: { ...this.snapshot.safety, closedLoop: true },
        drive: { ...this.snapshot.drive, inputArmed: true },
      });
      return;
    }
    this.update({ drive: { ...this.snapshot.drive, inputArmed: true } });
  };

  disarmDriveInput = () => {
    if (!this.snapshot.drive.inputArmed) return;
    this.update({ drive: { ...this.snapshot.drive, inputArmed: false } });
  };

  setSpeedLimit = (speedLimitPercent: number) => {
    this.update({ drive: { ...this.snapshot.drive, speedLimitPercent } });
  };

  private inputEnableBlocked(): boolean {
    return (
      this.snapshot.safety.drivestop
      || !this.snapshot.safety.whsOnline
      || this.snapshot.safety.faults.some((fault) => fault.severity === 'critical')
    );
  }

  private update(patch: Partial<AppSnapshot>) {
    this.snapshot = { ...this.snapshot, ...patch };
    this.emit();
  }

  private emit() {
    this.listeners.forEach((listener) => listener(this.snapshot));
  }
}