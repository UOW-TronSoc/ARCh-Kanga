import type { CameraDescriptor } from './types';

export const mockCameras: readonly CameraDescriptor[] = [
  { id: 'front-nav', label: 'Front navigation', health: 'standby', capabilities: [] },
  { id: 'rear-nav', label: 'Rear navigation', health: 'standby', capabilities: [] },
  { id: 'payload', label: 'Payload', health: 'standby', capabilities: [] },
];
