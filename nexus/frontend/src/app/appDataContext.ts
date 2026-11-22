import { createContext, useContext, useSyncExternalStore } from 'react';
import type { AppDataService } from '../services/contracts/AppDataService';

export const AppDataContext = createContext<AppDataService | null>(null);

export function useAppDataService() {
  const service = useContext(AppDataContext);
  if (!service) throw new Error('useAppDataService must be used within AppProviders');
  return service;
}

export function useAppSnapshot() {
  const service = useAppDataService();
  return useSyncExternalStore(service.subscribe, service.getSnapshot, service.getSnapshot);
}
