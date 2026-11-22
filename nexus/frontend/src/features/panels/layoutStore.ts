import type { LayoutDefinition, LayoutState, PanelContentId } from './types';

type LayoutListener = () => void;

export type SlotSizes = Readonly<Record<string, number>>;

const NO_SIZES: SlotSizes = Object.freeze({});

export const layoutStorageKey = (layoutId: string) => `nexus.panel-layout.${layoutId}`;
export const slotSizesStorageKey = (layoutId: string) => `nexus.panel-sizes.${layoutId}`;

function defaultStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export class LayoutStore {
  private readonly definitions = new Map<string, LayoutDefinition>();
  private readonly states = new Map<string, LayoutState>();
  private readonly sizes = new Map<string, SlotSizes>();
  private readonly listeners = new Set<LayoutListener>();
  private readonly validContent: ReadonlySet<PanelContentId>;

  constructor(
    definitions: readonly LayoutDefinition[],
    contentIds: Iterable<PanelContentId>,
    private readonly storage: Storage | null = defaultStorage(),
  ) {
    this.validContent = new Set(contentIds);
    for (const definition of definitions) {
      this.definitions.set(definition.id, definition);
      this.states.set(definition.id, this.restore(definition));
      this.sizes.set(definition.id, this.restoreSizes(definition));
    }
  }

  subscribe = (listener: LayoutListener) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  getLayout = (layoutId: string): LayoutState => {
    const state = this.states.get(layoutId);
    if (!state) throw new Error(`Unknown panel layout: ${layoutId}`);
    return state;
  };

  assign = (layoutId: string, slotId: string, contentId: PanelContentId) => {
    const current = this.states.get(layoutId);
    if (!current || !(slotId in current) || !this.validContent.has(contentId)) return;
    if (current[slotId] === contentId) return;

    const next: Record<string, PanelContentId> = { ...current };
    const holder = Object.keys(current).find((slot) => current[slot] === contentId);
    if (holder) next[holder] = current[slotId];
    next[slotId] = contentId;

    this.states.set(layoutId, next);
    this.persist(layoutStorageKey(layoutId), next);
    this.emit();
  };

  getSlotSizes = (layoutId: string): SlotSizes => this.sizes.get(layoutId) ?? NO_SIZES;

  setSlotWidth = (layoutId: string, slotId: string, width: number) => {
    const definition = this.definitions.get(layoutId);
    if (!definition?.slots.some((slot) => slot.id === slotId) || !Number.isFinite(width) || width <= 0) return;
    const current = this.getSlotSizes(layoutId);
    if (current[slotId] === width) return;

    const next = { ...current, [slotId]: width };
    this.sizes.set(layoutId, next);
    this.persist(slotSizesStorageKey(layoutId), next);
    this.emit();
  };

  private emit() {
    this.listeners.forEach((listener) => listener());
  }

  private restoreSizes(definition: LayoutDefinition): SlotSizes {
    try {
      const raw = this.storage?.getItem(slotSizesStorageKey(definition.id));
      const parsed: unknown = raw ? JSON.parse(raw) : null;
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return NO_SIZES;
      const slotIds = new Set(definition.slots.map((slot) => slot.id));
      return Object.fromEntries(Object.entries(parsed).filter(([slotId, width]) => (
        slotIds.has(slotId) && typeof width === 'number' && Number.isFinite(width) && width > 0
      )));
    } catch {
      return NO_SIZES;
    }
  }

  private restore(definition: LayoutDefinition): LayoutState {
    try {
      const raw = this.storage?.getItem(layoutStorageKey(definition.id));
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (this.isValid(definition, parsed)) return parsed;
      }
    } catch {
      // Unreadable or corrupt storage falls through to the defaults.
    }
    return definition.defaults;
  }

  private isValid(definition: LayoutDefinition, value: unknown): value is LayoutState {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    const record = value as Record<string, unknown>;
    if (Object.keys(record).length !== definition.slots.length) return false;
    const ids = definition.slots.map((slot) => record[slot.id]);
    return ids.every((id) => typeof id === 'string' && this.validContent.has(id)) && new Set(ids).size === ids.length;
  }

  private persist(key: string, value: unknown) {
    try {
      this.storage?.setItem(key, JSON.stringify(value));
    } catch {
      // Blocked or full storage keeps the layout in memory for this tab only.
    }
  }
}
