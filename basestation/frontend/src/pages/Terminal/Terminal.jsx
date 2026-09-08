import React, { useCallback, useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { getWsBase } from "../../config";
import "./Terminal.css";

const PIN_CLOSE = 4401;
const LEGACY_SESSION_KEY = "kanga-terminal-session";
const TABS_STORAGE_KEY = "kanga-terminal-tabs";
const TABS_STORAGE_VERSION = 1;
const DEFAULT_MAX_SESSIONS = 4;

function newClientId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nextLabel(tabs) {
  const used = tabs.reduce((max, tab) => {
    const match = /^Terminal (\d+)$/.exec(tab.label || "");
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return `Terminal ${used + 1}`;
}

function makeTab(partial = {}) {
  return {
    id: partial.id || newClientId(),
    label: partial.label || "Terminal 1",
    sessionId: partial.sessionId || "",
  };
}

function loadTabsState() {
  try {
    const raw = sessionStorage.getItem(TABS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (
        parsed &&
        parsed.version === TABS_STORAGE_VERSION &&
        Array.isArray(parsed.tabs)
      ) {
        const tabs = parsed.tabs
          .filter((tab) => tab && typeof tab.id === "string")
          .map((tab) =>
            makeTab({
              id: tab.id,
              label: tab.label,
              sessionId: typeof tab.sessionId === "string" ? tab.sessionId : "",
            })
          );
        const activeId = tabs.some((tab) => tab.id === parsed.activeId)
          ? parsed.activeId
          : tabs[0]?.id || "";
        return { tabs, activeId };
      }
    }
  } catch {
    /* ignore corrupt storage */
  }

  const legacy = sessionStorage.getItem(LEGACY_SESSION_KEY);
  if (legacy) {
    sessionStorage.removeItem(LEGACY_SESSION_KEY);
    const tab = makeTab({ label: "Terminal 1", sessionId: legacy });
    return { tabs: [tab], activeId: tab.id };
  }

  const tab = makeTab({ label: "Terminal 1" });
  return { tabs: [tab], activeId: tab.id };
}

function persistTabsState(tabs, activeId) {
  sessionStorage.setItem(
    TABS_STORAGE_KEY,
    JSON.stringify({
      version: TABS_STORAGE_VERSION,
      activeId,
      tabs,
    })
  );
  sessionStorage.removeItem(LEGACY_SESSION_KEY);
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

function TerminalPane({
  clientId,
  initialSessionId,
  active,
  onReady,
  onStatus,
  onRegisterCloser,
}) {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);
  const wsRef = useRef(null);
  const closeRequestedRef = useRef(false);
  const statusRef = useRef("Connecting…");

  const sendResize = useCallback(() => {
    const term = termRef.current;
    const ws = wsRef.current;
    if (!active || !term || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        t: "resize",
        cols: term.cols,
        rows: term.rows,
      })
    );
  }, [active]);

  const requestClose = useCallback(() => {
    closeRequestedRef.current = true;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ t: "close" }));
    }
  }, []);

  useEffect(() => {
    onRegisterCloser(clientId, requestClose);
    return () => onRegisterCloser(clientId, null);
  }, [clientId, onRegisterCloser, requestClose]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;

    const term = new XTerm({
      cursorBlink: true,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
      fontSize: 14,
      theme: {
        background: "#1e1e1e",
        foreground: "#f1f1f1",
        cursor: "#F8CE4D",
        selectionBackground: "rgba(248, 206, 77, 0.35)",
      },
      allowProposedApi: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(el);
    if (active) {
      fit.fit();
    }
    termRef.current = term;
    fitRef.current = fit;

    const sessionQuery = initialSessionId
      ? `?session=${encodeURIComponent(initialSessionId)}`
      : "";
    const ws = new WebSocket(`${getWsBase()}/ws/terminal${sessionQuery}`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    const setStatus = (status) => {
      statusRef.current = status;
      onStatus(clientId, status);
    };

    ws.onopen = () => {
      if (closeRequestedRef.current) {
        ws.send(JSON.stringify({ t: "close" }));
        return;
      }
      setStatus("Connected");
      sendResize();
    };

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          if (msg.t === "ready") {
            onReady(clientId, {
              sessionId: msg.session_id || "",
              cwd: msg.cwd || "",
              maxSessions: Number(msg.max_sessions) || DEFAULT_MAX_SESSIONS,
              reattached: Boolean(msg.reattached),
            });
            setStatus(msg.reattached ? "Reconnected" : "Ready");
            sendResize();
            return;
          }
          if (msg.t === "error") {
            setStatus(msg.message || "Terminal error");
            term.writeln(`\r\n\x1b[31m${msg.message || "Terminal error"}\x1b[0m`);
            return;
          }
          if (msg.t === "exit") {
            const code = msg.code == null ? "?" : String(msg.code);
            onReady(clientId, { sessionId: "", exited: true });
            setStatus(`Shell exited (${code})`);
            term.writeln(`\r\n\x1b[33m[shell exited: ${code}]\x1b[0m`);
          }
        } catch {
          term.write(event.data);
        }
        return;
      }
      term.write(new Uint8Array(event.data));
    };

    ws.onerror = () => {
      setStatus("Connection error");
    };

    ws.onclose = (event) => {
      wsRef.current = null;
      if (closeRequestedRef.current) {
        return;
      }
      if (event.code === PIN_CLOSE) {
        setStatus("PIN required — sign in, then reopen Terminal");
        term.writeln(
          "\r\n\x1b[31mPIN authentication is required for the terminal.\x1b[0m"
        );
        return;
      }
      const prev = statusRef.current;
      if (
        !prev.startsWith("Shell exited") &&
        !prev.includes("PIN") &&
        !prev.includes("error")
      ) {
        setStatus("Disconnected");
      }
    };

    const onData = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });

    const onResize = () => {
      if (!active) return;
      try {
        fit.fit();
        sendResize();
      } catch {
        /* container may be hidden */
      }
    };
    window.addEventListener("resize", onResize);
    const fitTimer = window.setTimeout(onResize, 50);

    return () => {
      window.clearTimeout(fitTimer);
      window.removeEventListener("resize", onResize);
      onData.dispose();
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          /* already closed */
        }
        wsRef.current = null;
      }
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
    // initialSessionId is the reconnect key captured at mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  useEffect(() => {
    if (!active) return undefined;
    const term = termRef.current;
    const fit = fitRef.current;
    if (!term || !fit) return undefined;
    const timer = window.setTimeout(() => {
      try {
        fit.fit();
        sendResize();
        term.focus();
      } catch {
        /* container may still be hidden */
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [active, sendResize]);

  return (
    <div
      className={"terminalPane" + (active ? "" : " terminalPane--hidden")}
      ref={containerRef}
      aria-hidden={!active}
    />
  );
}

export default function TerminalPage() {
  const initialRef = useRef(null);
  if (initialRef.current === null) {
    initialRef.current = loadTabsState();
  }
  const [tabs, setTabs] = useState(initialRef.current.tabs);
  const [activeId, setActiveId] = useState(initialRef.current.activeId);
  const [maxSessions, setMaxSessions] = useState(DEFAULT_MAX_SESSIONS);
  const [statuses, setStatuses] = useState({});
  const [pendingClose, setPendingClose] = useState(null);
  const closersRef = useRef({});

  useEffect(() => {
    persistTabsState(tabs, activeId);
  }, [tabs, activeId]);

  const registerCloser = useCallback((id, closer) => {
    if (closer) {
      closersRef.current[id] = closer;
    } else {
      delete closersRef.current[id];
    }
  }, []);

  const handleReady = useCallback((id, info) => {
    if (info.maxSessions) {
      setMaxSessions(info.maxSessions);
    }
    setTabs((current) =>
      current.map((tab) =>
        tab.id === id ? { ...tab, sessionId: info.sessionId || "" } : tab
      )
    );
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

  const addTab = useCallback(() => {
    setTabs((current) => {
      if (current.length >= maxSessions) return current;
      const tab = makeTab({ label: nextLabel(current) });
      setActiveId(tab.id);
      return [...current, tab];
    });
  }, [maxSessions]);

  const activateAdjacent = useCallback((current, closedId) => {
    const index = current.findIndex((tab) => tab.id === closedId);
    const remaining = current.filter((tab) => tab.id !== closedId);
    const next = remaining[index] || remaining[index - 1] || null;
    setActiveId(next ? next.id : "");
    return remaining;
  }, []);

  const confirmClose = useCallback(() => {
    if (!pendingClose) return;
    const closer = closersRef.current[pendingClose.id];
    if (closer) closer();
    setTabs((current) => activateAdjacent(current, pendingClose.id));
    setStatuses((current) => {
      const next = { ...current };
      delete next[pendingClose.id];
      return next;
    });
    setPendingClose(null);
  }, [activateAdjacent, pendingClose]);

  const activeTab = tabs.find((tab) => tab.id === activeId) || null;
  const activeStatus = activeTab ? statuses[activeTab.id] || {} : {};
  const statusText = activeTab
    ? activeStatus.status || "Connecting…"
    : "No terminal open";
  const atLimit = tabs.length >= maxSessions;

  return (
    <div className="terminalPage">
      <div className="terminalToolbar">
        <div className="terminalTabs" role="tablist" aria-label="Terminal sessions">
          {tabs.map((tab) => {
            const tabStatus = statuses[tab.id]?.status || "";
            const selected = tab.id === activeId;
            return (
              <div
                key={tab.id}
                className={"terminalTab" + (selected ? " terminalTab--active" : "")}
                role="tab"
                aria-selected={selected}
              >
                <button
                  type="button"
                  className="terminalTab-select"
                  onClick={() => setActiveId(tab.id)}
                >
                  <span className={"terminalTab-dot " + tabDotClass(tabStatus)} />
                  <span className="terminalTab-label">{tab.label}</span>
                </button>
                <button
                  type="button"
                  className="terminalTab-close"
                  aria-label={`Close ${tab.label}`}
                  onClick={() => setPendingClose(tab)}
                >
                  ×
                </button>
              </div>
            );
          })}
          <button
            type="button"
            className="terminalTab-add"
            onClick={addTab}
            disabled={atLimit}
            title={
              atLimit
                ? `Terminal limit reached (${maxSessions})`
                : "New terminal"
            }
          >
            +
          </button>
        </div>
        <div className="terminalToolbar-meta">
          {activeStatus.cwd ? (
            <code className="terminalToolbar-cwd" title={activeStatus.cwd}>
              {activeStatus.cwd}
            </code>
          ) : null}
          <span className={"terminalToolbar-status " + statusClass(statusText)}>
            {statusText}
          </span>
        </div>
      </div>

      {tabs.length === 0 ? (
        <div className="terminalEmpty">
          <p>No terminal open.</p>
          <button type="button" className="terminalEmpty-action" onClick={addTab}>
            New terminal
          </button>
        </div>
      ) : (
        <div className="terminalStack">
          {tabs.map((tab) => (
            <TerminalPane
              key={tab.id}
              clientId={tab.id}
              initialSessionId={tab.sessionId}
              active={tab.id === activeId}
              onReady={handleReady}
              onStatus={handleStatus}
              onRegisterCloser={registerCloser}
            />
          ))}
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
