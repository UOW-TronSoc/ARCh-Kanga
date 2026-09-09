import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  pointerWithin,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import TerminalLayout from "./TerminalLayout";
import {
  DEFAULT_MAX_SESSIONS,
  addTab,
  closeTab,
  createInitialState,
  dropTab,
  findGroup,
  focusTab,
  groupOfTab,
  moveTab,
  parseStoredWorkspace,
  setSplitSizes,
  splitFocused,
  updateTabSession,
} from "./terminalLayout";
import "./Terminal.css";

const STORAGE_KEY = "kanga-terminal-tabs";
const LEGACY_SESSION_KEY = "kanga-terminal-session";

function loadWorkspace() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = parseStoredWorkspace(JSON.parse(raw));
      if (parsed) return parsed;
    }
  } catch {
    /* ignore corrupt storage */
  }
  const legacy = sessionStorage.getItem(LEGACY_SESSION_KEY);
  if (legacy) {
    sessionStorage.removeItem(LEGACY_SESSION_KEY);
    const parsed = parseStoredWorkspace({
      version: 1,
      activeId: "legacy",
      tabs: [{ id: "legacy", label: "Terminal 1", sessionId: legacy }],
    });
    if (parsed) return parsed;
  }
  return createInitialState();
}

function statusClass(status) {
  if (status === "Ready" || status === "Connected" || status === "Reconnected") {
    return "terminalToolbar-status--ok";
  }
  if (status.includes("error") || status.includes("PIN") || status.includes("limit")) {
    return "terminalToolbar-status--err";
  }
  return "";
}

function collisionDetection(args) {
  const pointerHits = pointerWithin(args);
  const edge = pointerHits.find((hit) => String(hit.id).startsWith("edge:"));
  if (edge) return [edge];
  const sortable = closestCenter(args);
  if (sortable.length) return sortable;
  const center = pointerHits.find((hit) => String(hit.id).startsWith("center:"));
  return center ? [center] : pointerHits;
}

function dropTargetFromOver(workspace, over) {
  if (!over) return null;
  const id = String(over.id);
  if (id.startsWith("edge:")) {
    const parts = id.split(":");
    return { groupId: parts[1], edge: parts[2] };
  }
  if (id.startsWith("center:")) {
    return { groupId: id.slice("center:".length), edge: "center", index: null };
  }
  const group = groupOfTab(workspace.layout, id);
  if (!group) return null;
  return { groupId: group.id, edge: "center", index: group.tabIds.indexOf(id) };
}

export default function TerminalPage() {
  const initialRef = useRef(null);
  if (initialRef.current === null) {
    initialRef.current = loadWorkspace();
  }
  const [workspace, setWorkspace] = useState(initialRef.current);
  const [maxSessions, setMaxSessions] = useState(DEFAULT_MAX_SESSIONS);
  const [statuses, setStatuses] = useState({});
  const [pendingClose, setPendingClose] = useState(null);
  const [draggingTabId, setDraggingTabId] = useState("");
  const closersRef = useRef({});

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(workspace));
    sessionStorage.removeItem(LEGACY_SESSION_KEY);
  }, [workspace]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const registerCloser = useCallback((id, closer) => {
    if (closer) closersRef.current[id] = closer;
    else delete closersRef.current[id];
  }, []);

  const handleReady = useCallback((id, info) => {
    if (info.maxSessions) setMaxSessions(info.maxSessions);
    setWorkspace((current) => updateTabSession(current, id, info.sessionId));
    if (info.cwd) {
      setStatuses((current) => ({
        ...current,
        [id]: { ...(current[id] || {}), cwd: info.cwd },
      }));
    }
  }, []);

  const handleStatus = useCallback((id, status) => {
    setStatuses((current) => ({
      ...current,
      [id]: { ...(current[id] || {}), status },
    }));
  }, []);

  const handleAdd = useCallback(() => {
    setWorkspace((current) => addTab(current, maxSessions));
  }, [maxSessions]);

  const handleFocus = useCallback((groupId, tabId) => {
    setWorkspace((current) => focusTab(current, groupId, tabId));
  }, []);

  const handleSplit = useCallback((groupId, edge) => {
    setWorkspace((current) => {
      const group = findGroup(current.layout, groupId);
      if (!group) return current;
      const focused = focusTab(current, groupId, group.activeTabId);
      return splitFocused(focused, edge, maxSessions);
    });
  }, [maxSessions]);

  const confirmClose = useCallback(() => {
    if (!pendingClose) return;
    const closer = closersRef.current[pendingClose.id];
    if (closer) closer();
    setWorkspace((current) => closeTab(current, pendingClose.id));
    setStatuses((current) => {
      const next = { ...current };
      delete next[pendingClose.id];
      return next;
    });
    setPendingClose(null);
  }, [pendingClose]);

  const onDragEnd = useCallback((event) => {
    setDraggingTabId("");
    const tabId = String(event.active.id);
    setWorkspace((current) => {
      const target = dropTargetFromOver(current, event.over);
      if (!target) return current;
      if (target.edge && target.edge !== "center") {
        return dropTab(current, tabId, target);
      }
      return moveTab(current, tabId, target.groupId, target.index);
    });
  }, []);

  const focusedStatus = workspace.focusedTabId
    ? statuses[workspace.focusedTabId] || {}
    : {};
  const statusText = workspace.focusedTabId
    ? focusedStatus.status || "Connecting…"
    : "No terminal open";
  const atLimit = Object.keys(workspace.tabs).length >= maxSessions;
  const draggedTab = draggingTabId ? workspace.tabs[draggingTabId] : null;

  return (
    <div className="terminalPage">
      <div className="terminalToolbar">
        <div className="terminalToolbar-title">
          <span className="terminalToolbar-label">Host terminals</span>
          <button
            type="button"
            className="terminalTab-add"
            onClick={handleAdd}
            disabled={atLimit || !workspace.layout}
            title={atLimit ? `Terminal limit reached (${maxSessions})` : "New terminal"}
          >
            +
          </button>
        </div>
        <div className="terminalToolbar-meta">
          {focusedStatus.cwd ? (
            <code className="terminalToolbar-cwd" title={focusedStatus.cwd}>
              {focusedStatus.cwd}
            </code>
          ) : null}
          <span className={"terminalToolbar-status " + statusClass(statusText)}>
            {statusText}
          </span>
        </div>
      </div>

      {workspace.layout ? (
        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetection}
          onDragStart={(event) => setDraggingTabId(String(event.active.id))}
          onDragCancel={() => setDraggingTabId("")}
          onDragEnd={onDragEnd}
        >
          <div className="terminalWorkspace">
            <TerminalLayout
              node={workspace.layout}
              tabs={workspace.tabs}
              statuses={statuses}
              focusedGroupId={workspace.focusedGroupId}
              dragging={Boolean(draggingTabId)}
              onFocus={handleFocus}
              onClose={setPendingClose}
              onSplit={handleSplit}
              onSizes={(splitId, sizes) =>
                setWorkspace((current) => setSplitSizes(current, splitId, sizes))
              }
              onReady={handleReady}
              onStatus={handleStatus}
              onRegisterCloser={registerCloser}
            />
          </div>
          <DragOverlay>
            {draggedTab ? (
              <div className="terminalTab terminalTab--active terminalTab--overlay">
                <span className="terminalTab-label">{draggedTab.label}</span>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      ) : (
        <div className="terminalEmpty">
          <p>No terminal open.</p>
          <button type="button" className="terminalEmpty-action" onClick={handleAdd}>
            New terminal
          </button>
        </div>
      )}

      {pendingClose ? (
        <div className="terminalConfirm" role="dialog" aria-modal="true">
          <div className="terminalConfirm-card">
            <h2>Close {pendingClose.label}?</h2>
            <p>This stops its shell and any command still running.</p>
            <div className="terminalConfirm-actions">
              <button type="button" onClick={() => setPendingClose(null)}>
                Cancel
              </button>
              <button type="button" className="terminalConfirm-danger" onClick={confirmClose}>
                Close terminal
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
