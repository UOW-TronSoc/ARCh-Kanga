export const LAYOUT_VERSION = 2;
export const DEFAULT_MAX_SESSIONS = 6;

export function newClientId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function nextLabel(tabs) {
  const used = Object.values(tabs).reduce((max, tab) => {
    const match = /^Terminal (\d+)$/.exec(tab.label || "");
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return `Terminal ${used + 1}`;
}

export function makeTab(partial = {}) {
  return {
    id: partial.id || newClientId(),
    label: partial.label || "Terminal 1",
    sessionId: partial.sessionId || "",
  };
}

function makeGroup(tabIds, activeTabId) {
  const ids = tabIds.filter(Boolean);
  return {
    type: "group",
    id: newClientId(),
    tabIds: ids,
    activeTabId: ids.includes(activeTabId) ? activeTabId : ids[0] || "",
  };
}

function makeSplit(direction, children, sizes) {
  return {
    type: "split",
    id: newClientId(),
    direction,
    sizes: sizes || children.map(() => 1),
    children,
  };
}

export function createInitialState() {
  const tab = makeTab({ label: "Terminal 1" });
  const group = makeGroup([tab.id], tab.id);
  return {
    version: LAYOUT_VERSION,
    tabs: { [tab.id]: tab },
    layout: group,
    focusedGroupId: group.id,
    focusedTabId: tab.id,
  };
}

function isGroup(node) {
  return Boolean(node && node.type === "group" && typeof node.id === "string");
}

function isSplit(node) {
  return Boolean(node && node.type === "split" && Array.isArray(node.children));
}

export function walkLayout(node, visit) {
  if (!node) return;
  visit(node);
  if (isSplit(node)) node.children.forEach((child) => walkLayout(child, visit));
}

export function findGroup(layout, groupId) {
  let found = null;
  walkLayout(layout, (node) => {
    if (isGroup(node) && node.id === groupId) found = node;
  });
  return found;
}

export function firstGroup(layout) {
  let found = null;
  walkLayout(layout, (node) => {
    if (!found && isGroup(node)) found = node;
  });
  return found;
}

export function groupOfTab(layout, tabId) {
  let found = null;
  walkLayout(layout, (node) => {
    if (isGroup(node) && node.tabIds.includes(tabId)) found = node;
  });
  return found;
}

function mapLayout(node, fn) {
  if (!node) return node;
  const replaced = fn(node);
  if (replaced !== node || !isSplit(replaced)) return replaced;
  let changed = false;
  const children = replaced.children.map((child) => {
    const mapped = mapLayout(child, fn);
    if (mapped !== child) changed = true;
    return mapped;
  });
  return changed ? { ...replaced, children } : replaced;
}

function fitSizes(sizes, count) {
  const next = Array.isArray(sizes) ? sizes.slice(0, count) : [];
  while (next.length < count) next.push(1);
  return next.map((size) => (Number.isFinite(size) && size > 0 ? size : 1));
}

export function normalizeLayout(node) {
  if (!node) return null;
  if (isGroup(node)) {
    const tabIds = node.tabIds.filter((id) => typeof id === "string" && id);
    if (tabIds.length === 0) return null;
    return {
      ...node,
      tabIds,
      activeTabId: tabIds.includes(node.activeTabId) ? node.activeTabId : tabIds[0],
    };
  }
  if (!isSplit(node)) return null;
  const children = node.children.map(normalizeLayout).filter(Boolean);
  if (children.length === 0) return null;
  if (children.length === 1) return children[0];
  return { ...node, children, sizes: fitSizes(node.sizes, children.length) };
}

function updateGroup(layout, groupId, updater) {
  return mapLayout(layout, (node) => {
    if (!isGroup(node) || node.id !== groupId) return node;
    return updater(node);
  });
}

function replaceGroup(layout, groupId, replacement) {
  return mapLayout(layout, (node) => {
    if (!isGroup(node) || node.id !== groupId) return node;
    return replacement;
  });
}

function removeTabFromLayout(layout, tabId) {
  return mapLayout(layout, (node) => {
    if (!isGroup(node) || !node.tabIds.includes(tabId)) return node;
    const tabIds = node.tabIds.filter((id) => id !== tabId);
    return {
      ...node,
      tabIds,
      activeTabId: node.activeTabId === tabId ? tabIds[0] || "" : node.activeTabId,
    };
  });
}

function splitAround(target, created, edge) {
  const horizontal = edge === "left" || edge === "right";
  const direction = horizontal ? "horizontal" : "vertical";
  const children = edge === "left" || edge === "top" ? [created, target] : [target, created];
  return makeSplit(direction, children, [1, 1]);
}

function focusState(state, groupId, tabId) {
  return {
    ...state,
    focusedGroupId: groupId || "",
    focusedTabId: tabId || "",
  };
}

export function focusTab(state, groupId, tabId) {
  const group = findGroup(state.layout, groupId);
  if (!group || !group.tabIds.includes(tabId)) return state;
  const layout = updateGroup(state.layout, groupId, (current) => ({
    ...current,
    activeTabId: tabId,
  }));
  return focusState({ ...state, layout }, groupId, tabId);
}

export function addTab(state, maxSessions = DEFAULT_MAX_SESSIONS) {
  if (Object.keys(state.tabs).length >= maxSessions) return state;
  const tab = makeTab({ label: nextLabel(state.tabs) });
  const tabs = { ...state.tabs, [tab.id]: tab };
  if (!state.layout) {
    const group = makeGroup([tab.id], tab.id);
    return focusState({ ...state, tabs, layout: group }, group.id, tab.id);
  }
  const group = findGroup(state.layout, state.focusedGroupId) || firstGroup(state.layout);
  if (!group) {
    const created = makeGroup([tab.id], tab.id);
    return focusState({ ...state, tabs, layout: created }, created.id, tab.id);
  }
  const layout = updateGroup(state.layout, group.id, (current) => ({
    ...current,
    tabIds: [...current.tabIds, tab.id],
    activeTabId: tab.id,
  }));
  return focusState({ ...state, tabs, layout }, group.id, tab.id);
}

export function closeTab(state, tabId) {
  if (!state.tabs[tabId]) return state;
  const source = groupOfTab(state.layout, tabId);
  const tabs = { ...state.tabs };
  delete tabs[tabId];
  let layout = normalizeLayout(removeTabFromLayout(state.layout, tabId));
  if (!layout) {
    return { ...state, tabs, layout: null, focusedGroupId: "", focusedTabId: "" };
  }
  let nextGroup = source ? findGroup(layout, source.id) : null;
  if (!nextGroup) nextGroup = firstGroup(layout);
  const focusedTabId = nextGroup
    ? nextGroup.activeTabId || nextGroup.tabIds[0]
    : "";
  return focusState(
    { ...state, tabs, layout },
    nextGroup ? nextGroup.id : "",
    focusedTabId
  );
}

export function moveTab(state, tabId, targetGroupId, index = null) {
  const source = groupOfTab(state.layout, tabId);
  const target = findGroup(state.layout, targetGroupId);
  if (!source || !target || !state.tabs[tabId]) return state;
  const from = source.tabIds.indexOf(tabId);
  const to = index == null ? target.tabIds.length : index;
  if (source.id === target.id) {
    if (to === from) {
      return focusState(
        {
          ...state,
          layout: updateGroup(state.layout, source.id, (group) => ({
            ...group,
            activeTabId: tabId,
          })),
        },
        source.id,
        tabId
      );
    }
    const tabIds = source.tabIds.slice();
    const [moved] = tabIds.splice(from, 1);
    tabIds.splice(Math.max(0, Math.min(to, tabIds.length)), 0, moved);
    const layout = updateGroup(state.layout, source.id, (group) => ({
      ...group,
      tabIds,
      activeTabId: tabId,
    }));
    return focusState({ ...state, layout }, source.id, tabId);
  }
  let layout = removeTabFromLayout(state.layout, tabId);
  layout = updateGroup(layout, targetGroupId, (group) => {
    const tabIds = group.tabIds.filter((id) => id !== tabId);
    const at = Math.max(0, Math.min(to, tabIds.length));
    tabIds.splice(at, 0, tabId);
    return { ...group, tabIds, activeTabId: tabId };
  });
  layout = normalizeLayout(layout);
  return focusState({ ...state, layout }, targetGroupId, tabId);
}

export function splitTab(state, tabId, targetGroupId, edge) {
  const source = groupOfTab(state.layout, tabId);
  const target = findGroup(state.layout, targetGroupId);
  if (!source || !target || !state.tabs[tabId]) return state;
  if (!["left", "right", "top", "bottom"].includes(edge)) return state;
  if (source.id === target.id && source.tabIds.length < 2) return state;

  let layout = removeTabFromLayout(state.layout, tabId);
  const created = makeGroup([tabId], tabId);
  layout = replaceGroup(layout, targetGroupId, (function wrap() {
    const remaining = findGroup(layout, targetGroupId);
    return splitAround(remaining, created, edge);
  })());
  layout = normalizeLayout(layout);
  return focusState({ ...state, layout }, created.id, tabId);
}

export function splitFocused(state, edge, maxSessions = DEFAULT_MAX_SESSIONS) {
  const group = findGroup(state.layout, state.focusedGroupId) || firstGroup(state.layout);
  if (!group || !["left", "right", "top", "bottom"].includes(edge)) return state;
  const activeId = group.tabIds.includes(state.focusedTabId)
    ? state.focusedTabId
    : group.activeTabId;
  if (group.tabIds.length > 1 && activeId) {
    return splitTab(state, activeId, group.id, edge);
  }
  if (Object.keys(state.tabs).length >= maxSessions) return state;
  const tab = makeTab({ label: nextLabel(state.tabs) });
  const created = makeGroup([tab.id], tab.id);
  const layout = normalizeLayout(
    replaceGroup(state.layout, group.id, splitAround(group, created, edge))
  );
  return focusState(
    { ...state, tabs: { ...state.tabs, [tab.id]: tab }, layout },
    created.id,
    tab.id
  );
}

export function dropTab(state, tabId, target) {
  if (!target || !tabId) return state;
  if (target.edge && target.edge !== "center") {
    return splitTab(state, tabId, target.groupId, target.edge);
  }
  return moveTab(state, tabId, target.groupId, target.index);
}

export function setSplitSizes(state, splitId, sizes) {
  if (!Array.isArray(sizes) || sizes.length === 0) return state;
  const layout = mapLayout(state.layout, (node) => {
    if (!isSplit(node) || node.id !== splitId) return node;
    return { ...node, sizes: fitSizes(sizes, node.children.length) };
  });
  return { ...state, layout };
}

export function updateTabSession(state, tabId, sessionId) {
  const tab = state.tabs[tabId];
  if (!tab) return state;
  return {
    ...state,
    tabs: { ...state.tabs, [tabId]: { ...tab, sessionId: sessionId || "" } },
  };
}

function sanitizeTab(tab) {
  if (!tab || typeof tab.id !== "string") return null;
  return makeTab({
    id: tab.id,
    label: typeof tab.label === "string" && tab.label ? tab.label : "Terminal",
    sessionId: typeof tab.sessionId === "string" ? tab.sessionId : "",
  });
}

function sanitizeNode(node, tabs) {
  if (!node || typeof node !== "object") return null;
  if (node.type === "group") {
    const tabIds = Array.isArray(node.tabIds)
      ? node.tabIds.filter((id) => tabs[id])
      : [];
    if (tabIds.length === 0) return null;
    return {
      type: "group",
      id: typeof node.id === "string" ? node.id : newClientId(),
      tabIds,
      activeTabId: tabIds.includes(node.activeTabId) ? node.activeTabId : tabIds[0],
    };
  }
  if (node.type === "split") {
    const direction = node.direction === "vertical" ? "vertical" : "horizontal";
    const children = Array.isArray(node.children)
      ? node.children.map((child) => sanitizeNode(child, tabs)).filter(Boolean)
      : [];
    if (children.length === 0) return null;
    if (children.length === 1) return children[0];
    return {
      type: "split",
      id: typeof node.id === "string" ? node.id : newClientId(),
      direction,
      sizes: fitSizes(node.sizes, children.length),
      children,
    };
  }
  return null;
}

function stateFromTabs(tabList, activeId) {
  const tabs = {};
  tabList.forEach((tab) => {
    tabs[tab.id] = tab;
  });
  const ids = tabList.map((tab) => tab.id);
  const group = makeGroup(ids, ids.includes(activeId) ? activeId : ids[0]);
  return {
    version: LAYOUT_VERSION,
    tabs,
    layout: group,
    focusedGroupId: group.id,
    focusedTabId: group.activeTabId,
  };
}

export function parseStoredWorkspace(raw) {
  if (!raw || typeof raw !== "object") return null;
  if (raw.version === 1 && Array.isArray(raw.tabs)) {
    const tabList = raw.tabs.map(sanitizeTab).filter(Boolean);
    if (tabList.length === 0) return null;
    return stateFromTabs(tabList, raw.activeId);
  }
  if (raw.version !== LAYOUT_VERSION || !raw.tabs || typeof raw.tabs !== "object") {
    return null;
  }
  const tabs = {};
  Object.values(raw.tabs).forEach((tab) => {
    const clean = sanitizeTab(tab);
    if (clean) tabs[clean.id] = clean;
  });
  const used = new Set();
  walkLayout(raw.layout, (node) => {
    if (isGroup(node) && Array.isArray(node.tabIds)) {
      node.tabIds.forEach((id) => used.add(id));
    }
  });
  Object.keys(tabs).forEach((id) => {
    if (!used.has(id)) delete tabs[id];
  });
  if (Object.keys(tabs).length === 0) return null;
  let layout = sanitizeNode(raw.layout, tabs);
  if (!layout) {
    return stateFromTabs(Object.values(tabs), raw.focusedTabId);
  }
  const focusedGroup = findGroup(layout, raw.focusedGroupId) || firstGroup(layout);
  const focusedTabId = focusedGroup && focusedGroup.tabIds.includes(raw.focusedTabId)
    ? raw.focusedTabId
    : focusedGroup?.activeTabId || "";
  if (focusedGroup && focusedTabId) {
    layout = updateGroup(layout, focusedGroup.id, (group) => ({
      ...group,
      activeTabId: focusedTabId,
    }));
  }
  return {
    version: LAYOUT_VERSION,
    tabs,
    layout,
    focusedGroupId: focusedGroup ? focusedGroup.id : "",
    focusedTabId,
  };
}

export function visibleTabIds(layout) {
  const ids = [];
  walkLayout(layout, (node) => {
    if (isGroup(node) && node.activeTabId) ids.push(node.activeTabId);
  });
  return ids;
}
