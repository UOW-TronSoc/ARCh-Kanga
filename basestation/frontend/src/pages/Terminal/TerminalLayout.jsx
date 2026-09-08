import React from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import TerminalPane from "./TerminalPane";

function tabDotClass(status) {
  if (!status) return "";
  if (status === "Ready" || status === "Connected" || status === "Reconnected") {
    return "terminalTab-dot--ok";
  }
  if (status.includes("error") || status.includes("PIN") || status.includes("exited")) {
    return "terminalTab-dot--err";
  }
  return "terminalTab-dot--busy";
}

function TerminalTab({
  tab,
  groupId,
  selected,
  status,
  onSelect,
  onClose,
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: tab.id,
    data: { tabId: tab.id, groupId },
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={
        "terminalTab" +
        (selected ? " terminalTab--active" : "") +
        (isDragging ? " terminalTab--dragging" : "")
      }
      role="tab"
      aria-selected={selected}
    >
      <button
        type="button"
        className="terminalTab-select"
        onClick={() => onSelect(groupId, tab.id)}
        {...attributes}
        {...listeners}
      >
        <span className={"terminalTab-dot " + tabDotClass(status)} />
        <span className="terminalTab-label">{tab.label}</span>
      </button>
      <button
        type="button"
        className="terminalTab-close"
        aria-label={`Close ${tab.label}`}
        onClick={() => onClose(tab)}
      >
        ×
      </button>
    </div>
  );
}

function DropEdge({ groupId, edge, hot }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `edge:${groupId}:${edge}`,
    data: { groupId, edge },
  });
  return (
    <div
      ref={setNodeRef}
      className={
        `terminalDrop terminalDrop--${edge}` +
        ((hot && isOver) || hot === edge ? " is-hot" : "")
      }
    />
  );
}

function TerminalGroup({
  group,
  tabs,
  statuses,
  focused,
  dragging,
  hotEdge,
  onFocus,
  onClose,
  onSplit,
  onReady,
  onStatus,
  onRegisterCloser,
}) {
  const center = useDroppable({
    id: `center:${group.id}`,
    data: { groupId: group.id, edge: "center" },
  });

  return (
    <section
      className={"terminalGroup" + (focused ? " terminalGroup--focused" : "")}
      onPointerDown={() => onFocus(group.id, group.activeTabId)}
    >
      <div className="terminalTabs" role="tablist" aria-label="Terminal group">
        <SortableContext items={group.tabIds} strategy={horizontalListSortingStrategy}>
          {group.tabIds.map((tabId) => (
            <TerminalTab
              key={tabId}
              tab={tabs[tabId]}
              groupId={group.id}
              selected={tabId === group.activeTabId}
              status={statuses[tabId]?.status || ""}
              onSelect={onFocus}
              onClose={onClose}
            />
          ))}
        </SortableContext>
        <button
          type="button"
          className="terminalSplitButton"
          title="Split right"
          aria-label="Split right"
          onClick={() => onSplit(group.id, "right")}
        >
          ⟺
        </button>
        <button
          type="button"
          className="terminalSplitButton"
          title="Split down"
          aria-label="Split down"
          onClick={() => onSplit(group.id, "bottom")}
        >
          ⇕
        </button>
      </div>
      <div
        ref={center.setNodeRef}
        className={"terminalGroup-body" + (center.isOver ? " is-drop-target" : "")}
      >
        {dragging ? (
          <>
            <DropEdge groupId={group.id} edge="left" hot={hotEdge} />
            <DropEdge groupId={group.id} edge="right" hot={hotEdge} />
            <DropEdge groupId={group.id} edge="top" hot={hotEdge} />
            <DropEdge groupId={group.id} edge="bottom" hot={hotEdge} />
          </>
        ) : null}
        {group.tabIds.map((tabId) => (
          <TerminalPane
            key={tabId}
            clientId={tabId}
            initialSessionId={tabs[tabId]?.sessionId || ""}
            visible={tabId === group.activeTabId}
            onReady={onReady}
            onStatus={onStatus}
            onRegisterCloser={onRegisterCloser}
          />
        ))}
      </div>
    </section>
  );
}

export default function TerminalLayout({
  node,
  tabs,
  statuses,
  focusedGroupId,
  dragging,
  hotEdge,
  onFocus,
  onClose,
  onSplit,
  onSizes,
  onReady,
  onStatus,
  onRegisterCloser,
}) {
  if (!node) return null;
  if (node.type === "group") {
    return (
      <TerminalGroup
        group={node}
        tabs={tabs}
        statuses={statuses}
        focused={node.id === focusedGroupId}
        dragging={dragging}
        hotEdge={hotEdge}
        onFocus={onFocus}
        onClose={onClose}
        onSplit={onSplit}
        onReady={onReady}
        onStatus={onStatus}
        onRegisterCloser={onRegisterCloser}
      />
    );
  }

  return (
    <Allotment
      vertical={node.direction === "vertical"}
      defaultSizes={node.sizes}
      onChange={(sizes) => onSizes(node.id, sizes)}
    >
      {node.children.map((child) => (
        <Allotment.Pane key={child.id} minSize={160}>
          <TerminalLayout
            node={child}
            tabs={tabs}
            statuses={statuses}
            focusedGroupId={focusedGroupId}
            dragging={dragging}
            hotEdge={hotEdge}
            onFocus={onFocus}
            onClose={onClose}
            onSplit={onSplit}
            onSizes={onSizes}
            onReady={onReady}
            onStatus={onStatus}
            onRegisterCloser={onRegisterCloser}
          />
        </Allotment.Pane>
      ))}
    </Allotment>
  );
}
