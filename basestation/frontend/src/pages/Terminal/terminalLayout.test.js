import assert from "node:assert/strict";
import test from "node:test";

import {
  addTab,
  closeTab,
  createInitialState,
  dropTab,
  moveTab,
  parseStoredWorkspace,
  setSplitSizes,
  splitFocused,
  splitTab,
} from "./terminalLayout.js";

function groupIds(layout, acc = []) {
  if (!layout) return acc;
  if (layout.type === "group") acc.push(layout.id);
  if (layout.type === "split") layout.children.forEach((child) => groupIds(child, acc));
  return acc;
}

test("migrates flat v1 tabs into one group without dropping session ids", () => {
  const parsed = parseStoredWorkspace({
    version: 1,
    activeId: "b",
    tabs: [
      { id: "a", label: "Terminal 1", sessionId: "sess-a" },
      { id: "b", label: "Terminal 2", sessionId: "sess-b" },
    ],
  });
  assert.equal(parsed.version, 2);
  assert.equal(parsed.layout.type, "group");
  assert.deepEqual(parsed.layout.tabIds, ["a", "b"]);
  assert.equal(parsed.focusedTabId, "b");
  assert.equal(parsed.tabs.a.sessionId, "sess-a");
});

test("reorders tabs within a group and moves them between groups", () => {
  let state = addTab(createInitialState(), 6);
  const [first, second] = Object.keys(state.tabs);
  const groupId = state.layout.id;
  state = moveTab(state, first, groupId, 1);
  assert.deepEqual(state.layout.tabIds, [second, first]);

  state = splitFocused(state, "right", 6);
  const right = state.layout.children[1];
  const left = state.layout.children[0];
  const moved = right.tabIds[0];
  state = moveTab(state, moved, left.id, 0);
  assert.equal(state.layout.type, "group");
  assert.equal(state.layout.tabIds[0], moved);
});

test("splits a tab to each edge in the requested order", () => {
  const cases = [
    ["left", "horizontal", 0],
    ["right", "horizontal", 1],
    ["top", "vertical", 0],
    ["bottom", "vertical", 1],
  ];
  for (const [edge, direction, index] of cases) {
    let state = addTab(createInitialState(), 6);
    const tabId = state.focusedTabId;
    const groupId = state.focusedGroupId;
    state = splitTab(state, tabId, groupId, edge);
    assert.equal(state.layout.direction, direction);
    assert.equal(state.layout.children[index].tabIds[0], tabId);
    assert.equal(state.layout.children[1 - index].tabIds.length, 1);
  }
});

test("persists split sizes and collapses an emptied group", () => {
  let state = splitFocused(addTab(createInitialState(), 6), "right", 6);
  const splitId = state.layout.id;
  state = setSplitSizes(state, splitId, [120, 280]);
  assert.deepEqual(state.layout.sizes, [120, 280]);

  const restored = parseStoredWorkspace(JSON.parse(JSON.stringify(state)));
  assert.deepEqual(restored.layout.sizes, [120, 280]);

  const doomed = state.focusedTabId;
  state = closeTab(state, doomed);
  assert.equal(state.layout.type, "group");
  assert.equal(groupIds(state.layout).length, 1);
});

test("recovers from malformed stored state and refuses a self-split of one tab", () => {
  assert.equal(parseStoredWorkspace({ version: 2, tabs: { no: "bad" } }), null);
  assert.equal(parseStoredWorkspace(null), null);

  const state = createInitialState();
  const tabId = state.focusedTabId;
  assert.equal(splitTab(state, tabId, state.focusedGroupId, "left"), state);
});

test("drop on a group edge creates a split and center drop joins the group", () => {
  let state = splitFocused(createInitialState(), "right", 6);
  const left = state.layout.children[0];
  const right = state.layout.children[1];
  const tabId = left.tabIds[0];
  state = dropTab(state, tabId, { groupId: right.id, edge: "bottom" });
  assert.equal(state.layout.type, "split");
  assert.equal(state.layout.direction, "vertical");

  const nested = state.layout;
  const moved = nested.children[1].tabIds[0];
  state = dropTab(state, moved, { groupId: nested.children[0].id, edge: "center", index: 1 });
  assert.equal(state.layout.type, "group");
  assert.equal(state.layout.tabIds.at(-1), moved);
});
