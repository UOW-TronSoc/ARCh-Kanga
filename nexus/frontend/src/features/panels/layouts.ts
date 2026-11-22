import type { LayoutDefinition } from './types';

export const roverLayout: LayoutDefinition = {
  id: 'rover',
  slots: [
    { id: 'main', label: 'Main view' },
    { id: 'inset1', label: 'Inset 1' },
    { id: 'inset2', label: 'Inset 2' },
  ],
  defaults: {
    main: 'rover-twin',
    inset1: 'camera:front-nav',
    inset2: 'camera:rear-nav',
  },
};

export const defaultLayouts: readonly LayoutDefinition[] = [roverLayout];
