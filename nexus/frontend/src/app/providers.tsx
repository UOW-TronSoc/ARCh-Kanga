import { useMemo, type PropsWithChildren } from 'react';
import { createDefaultAppDataService } from '../services/createAppDataService';
import type { AppDataService } from '../services/contracts/AppDataService';
import { createDefaultLayoutStore, LayoutStoreContext } from '../features/panels/layoutContext';
import type { LayoutStore } from '../features/panels/layoutStore';
import { AppDataContext } from './appDataContext';

export function AppProviders({ children, service, layoutStore }: PropsWithChildren<{ service?: AppDataService; layoutStore?: LayoutStore }>) {
  const appDataService = useMemo(() => service ?? createDefaultAppDataService(), [service]);
  const layouts = useMemo(() => layoutStore ?? createDefaultLayoutStore(), [layoutStore]);
  return (
    <AppDataContext.Provider value={appDataService}>
      <LayoutStoreContext.Provider value={layouts}>{children}</LayoutStoreContext.Provider>
    </AppDataContext.Provider>
  );
}
