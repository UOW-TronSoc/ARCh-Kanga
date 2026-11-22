import type { AppSnapshot } from '../../types';

export type AppSnapshotListener = (snapshot: AppSnapshot) => void;

export interface AppDataService {
  getSnapshot(): AppSnapshot;
  subscribe(listener: AppSnapshotListener): () => void;
  assertDrivestop(): void;
  releaseDrivestop(): void;
  takeControl(): void;
  toggleClosedLoop(): void;
  toggleInputArm(): void;
  disarmDriveInput(): void;
  setSpeedLimit(percent: number): void;
  sendDrive(frame: { x: number; yaw: number; scale: number }): void;
  clearErrors(): void;
}