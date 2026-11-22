import type { PanelCapability } from '../panels/types';

export type CameraHealth = 'live' | 'standby' | 'unavailable';

export interface CameraDescriptor {
  id: string;
  label: string;
  health: CameraHealth;
  capabilities: readonly PanelCapability[];
}
