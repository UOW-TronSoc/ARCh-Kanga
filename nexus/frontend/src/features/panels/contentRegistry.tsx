import { Camera, Orbit } from 'lucide-react';
import { CameraFeedContent } from '../cameras/CameraFeedContent';
import { mockCameras } from '../cameras/mockCameras';
import { RoverTwinContent } from '../rover-view/RoverTwinContent';
import type { PanelContentDefinition, PanelContentId } from './types';

export const ROVER_TWIN_ID = 'rover-twin';
export const cameraContentId = (cameraId: string): PanelContentId => `camera:${cameraId}`;

export const panelContents: readonly PanelContentDefinition[] = [
  {
    id: ROVER_TWIN_ID,
    label: 'Rover model',
    kind: 'twin',
    icon: Orbit,
    capabilities: [],
    render: (props) => <RoverTwinContent {...props} />,
  },
  ...mockCameras.map((camera): PanelContentDefinition => ({
    id: cameraContentId(camera.id),
    label: camera.label,
    kind: 'camera',
    icon: Camera,
    capabilities: camera.capabilities,
    render: (props) => <CameraFeedContent camera={camera} {...props} />,
  })),
];

const contentById = new Map(panelContents.map((content) => [content.id, content]));

export const panelContentIds = panelContents.map((content) => content.id);
export const getPanelContent = (id: PanelContentId | undefined) => (id ? contentById.get(id) : undefined);
