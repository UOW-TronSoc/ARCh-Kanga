import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export type PanelContentId = string;
export type PanelSize = 'main' | 'inset' | 'grid';
export type PanelContentKind = 'twin' | 'camera';
export type PanelCapability = 'pan' | 'tilt' | 'zoom' | 'focus';

export interface PanelContentProps {
  size: PanelSize;
  active: boolean;
}

export interface PanelContentDefinition {
  id: PanelContentId;
  label: string;
  kind: PanelContentKind;
  icon: LucideIcon;
  capabilities: readonly PanelCapability[];
  render: (props: PanelContentProps) => ReactNode;
}

export type LayoutState = Readonly<Record<string, PanelContentId>>;

export interface LayoutSlot {
  id: string;
  label: string;
}

export interface LayoutDefinition {
  id: string;
  slots: readonly LayoutSlot[];
  defaults: LayoutState;
}
