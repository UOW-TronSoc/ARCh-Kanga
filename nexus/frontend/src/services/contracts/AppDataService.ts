import type { AppSnapshot } from '../../types';

export type AppSnapshotListener = (snapshot: AppSnapshot) => void;

export interface AppDataService {
  readonly commandsEnabled: boolean;
  getSnapshot(): AppSnapshot;
  subscribe(listener: AppSnapshotListener): () => void;
  assertDrivestop(): void;
  releaseDrivestop(): void;
  toggleClosedLoop(): void;
  toggleInputArm(): void;
  disarmDriveInput(): void;
  setSpeedLimit(percent: number): void;
}