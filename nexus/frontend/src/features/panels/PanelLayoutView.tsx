import { getPanelContent, panelContents } from './contentRegistry';
import { useLayout, useLayoutStore, useSlotSizes } from './layoutContext';
import { ViewPanel } from './ViewPanel';
import type { LayoutDefinition, LayoutSlot, PanelSize } from './types';

interface PanelLayoutViewProps {
  layout: LayoutDefinition;
  className?: string;
  mainSlotId?: string;
  sizeFor: (slot: LayoutSlot) => PanelSize;
  slotClassName: (slot: LayoutSlot) => string;
}

export function PanelLayoutView({ layout, className, mainSlotId, sizeFor, slotClassName }: PanelLayoutViewProps) {
  const state = useLayout(layout.id);
  const slotSizes = useSlotSizes(layout.id);
  const store = useLayoutStore();
  const options = panelContents.map((content) => ({
    id: content.id,
    label: content.label,
    location: layout.slots.find((slot) => state[slot.id] === content.id)?.label,
  }));

  return (
    <div className={className}>
      {layout.slots.map((slot) => {
        const content = getPanelContent(state[slot.id]);
        const size = sizeFor(slot);
        const width = slotSizes[slot.id];
        const promote = mainSlotId && slot.id !== mainSlotId && content
          ? () => store.assign(layout.id, mainSlotId, content.id)
          : undefined;
        return (
          <ViewPanel
            key={content?.id ?? `empty:${slot.id}`}
            content={content}
            size={size}
            active={size !== 'inset'}
            slotLabel={slot.label}
            options={options}
            onSelect={(contentId) => store.assign(layout.id, slot.id, contentId)}
            onPromote={promote}
            onResize={(nextWidth) => store.setSlotWidth(layout.id, slot.id, nextWidth)}
            className={slotClassName(slot)}
            style={width === undefined ? undefined : { width }}
          />
        );
      })}
    </div>
  );
}
