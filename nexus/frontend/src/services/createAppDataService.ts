import type { AppDataService } from './contracts/AppDataService';
import { LiveTelemetryService } from './live/LiveTelemetryService';
import { MockAppDataService } from './mock/MockAppDataService';

/** Demo is the default. The container build selects live explicitly. */
export function createDefaultAppDataService(): AppDataService {
  if (import.meta.env.VITE_NEXUS_DATA_SOURCE === 'live') return new LiveTelemetryService();
  return new MockAppDataService();
}
