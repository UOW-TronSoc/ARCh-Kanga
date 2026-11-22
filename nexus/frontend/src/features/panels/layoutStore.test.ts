import { LayoutStore, layoutStorageKey, slotSizesStorageKey } from './layoutStore';
import type { LayoutDefinition } from './types';

const contentIds = ['twin', 'front', 'rear', 'payload'];

const rover: LayoutDefinition = {
  id: 'rover',
  slots: [{ id: 'main', label: 'Main' }, { id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
  defaults: { main: 'twin', a: 'front', b: 'rear' },
};

const cameras: LayoutDefinition = {
  id: 'cameras',
  slots: [{ id: 'one', label: 'One' }, { id: 'two', label: 'Two' }],
  defaults: { one: 'front', two: 'rear' },
};

const createStore = (storage: Storage | null = window.sessionStorage) => new LayoutStore([rover, cameras], contentIds, storage);

describe('LayoutStore', () => {
  beforeEach(() => window.sessionStorage.clear());

  it('starts from the default layouts', () => {
    expect(createStore().getLayout('rover')).toEqual(rover.defaults);
  });

  it('swaps slots when content is already placed elsewhere in the layout', () => {
    const store = createStore();
    store.assign('rover', 'main', 'front');
    expect(store.getLayout('rover')).toEqual({ main: 'front', a: 'twin', b: 'rear' });
  });

  it('replaces the slot when content is not already in the layout', () => {
    const store = createStore();
    store.assign('rover', 'b', 'payload');
    expect(store.getLayout('rover')).toEqual({ main: 'twin', a: 'front', b: 'payload' });
  });

  it('ignores unknown layouts, slots and content', () => {
    const store = createStore();
    const before = store.getLayout('rover');
    store.assign('rover', 'main', 'missing');
    store.assign('rover', 'nope', 'front');
    store.assign('nope', 'main', 'front');
    expect(store.getLayout('rover')).toBe(before);
  });

  it('notifies subscribers only when the layout changes', () => {
    const store = createStore();
    const listener = vi.fn();
    store.subscribe(listener);
    store.assign('rover', 'main', 'twin');
    expect(listener).not.toHaveBeenCalled();
    store.assign('rover', 'main', 'rear');
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('lets separate layouts hold the same content independently', () => {
    const store = createStore();
    store.assign('rover', 'main', 'front');
    store.assign('cameras', 'two', 'front');
    expect(store.getLayout('rover').main).toBe('front');
    expect(store.getLayout('cameras')).toEqual({ one: 'rear', two: 'front' });
  });

  it('round-trips layouts through session storage', () => {
    createStore().assign('rover', 'main', 'rear');
    expect(createStore().getLayout('rover')).toEqual({ main: 'rear', a: 'front', b: 'twin' });
  });

  it.each([
    ['corrupt JSON', '{not json'],
    ['missing slots', JSON.stringify({ main: 'twin' })],
    ['unknown content', JSON.stringify({ main: 'twin', a: 'front', b: 'ghost' })],
    ['duplicate content', JSON.stringify({ main: 'twin', a: 'twin', b: 'rear' })],
  ])('falls back to defaults for %s', (_, stored) => {
    window.sessionStorage.setItem(layoutStorageKey('rover'), stored);
    expect(createStore().getLayout('rover')).toEqual(rover.defaults);
  });

  it('keeps slot widths with the slot when content swaps', () => {
    const store = createStore();
    store.setSlotWidth('rover', 'a', 320);
    store.assign('rover', 'main', 'front');
    expect(store.getSlotSizes('rover')).toEqual({ a: 320 });
  });

  it('round-trips slot widths through session storage and drops invalid entries', () => {
    createStore().setSlotWidth('rover', 'b', 280);
    expect(createStore().getSlotSizes('rover')).toEqual({ b: 280 });

    window.sessionStorage.setItem(slotSizesStorageKey('rover'), JSON.stringify({ a: -4, b: 'wide', ghost: 200, main: 500 }));
    expect(createStore().getSlotSizes('rover')).toEqual({ main: 500 });
  });

  it('ignores invalid slot widths', () => {
    const store = createStore();
    store.setSlotWidth('rover', 'missing', 300);
    store.setSlotWidth('rover', 'a', Number.NaN);
    store.setSlotWidth('nope', 'a', 300);
    expect(store.getSlotSizes('rover')).toEqual({});
  });

  it('works without storage', () => {
    const store = createStore(null);
    store.assign('rover', 'main', 'front');
    expect(store.getLayout('rover').main).toBe('front');
  });
});
