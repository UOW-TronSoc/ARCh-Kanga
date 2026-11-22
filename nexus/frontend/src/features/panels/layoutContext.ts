import { createContext, useCallback, useContext, useSyncExternalStore } from 'react';
import { panelContentIds } from './contentRegistry';
import { defaultLayouts } from './layouts';
import { LayoutStore } from './layoutStore';

export const LayoutStoreContext = createContext<LayoutStore | null>(null);

export const createDefaultLayoutStore = () => new LayoutStore(defaultLayouts, panelContentIds);

export function useLayoutStore() {
  const store = useContext(LayoutStoreContext);
  if (!store) throw new Error('useLayoutStore must be used within AppProviders');
  return store;
}

export function useLayout(layoutId: string) {
  const store = useLayoutStore();
  const getSnapshot = useCallback(() => store.getLayout(layoutId), [store, layoutId]);
  return useSyncExternalStore(store.subscribe, getSnapshot, getSnapshot);
}

export function useSlotSizes(layoutId: string) {
  const store = useLayoutStore();
  const getSnapshot = useCallback(() => store.getSlotSizes(layoutId), [store, layoutId]);
  return useSyncExternalStore(store.subscribe, getSnapshot, getSnapshot);
}
