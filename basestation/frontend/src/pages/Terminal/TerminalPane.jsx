import React, { useCallback, useEffect, useRef } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { getWsBase } from "../../config";

const PIN_CLOSE = 4401;

export default function TerminalPane({
  clientId,
  initialSessionId,
  visible,
  onReady,
  onStatus,
  onRegisterCloser,
}) {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);
  const wsRef = useRef(null);
  const visibleRef = useRef(visible);
  const closeRequestedRef = useRef(false);
  const statusRef = useRef("Connecting…");

  useEffect(() => {
    visibleRef.current = visible;
  }, [visible]);

  const fitAndResize = useCallback(() => {
    const term = termRef.current;
    const fit = fitRef.current;
    const ws = wsRef.current;
    if (!visibleRef.current || !term || !fit) return;
    try {
      fit.fit();
    } catch {
      return;
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          t: "resize",
          cols: term.cols,
          rows: term.rows,
        })
      );
    }
  }, []);

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
      fitAndResize();
    };

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          if (msg.t === "ready") {
            onReady(clientId, {
              sessionId: msg.session_id || "",
              cwd: msg.cwd || "",
              maxSessions: Number(msg.max_sessions) || 0,
              reattached: Boolean(msg.reattached),
            });
            setStatus(msg.reattached ? "Reconnected" : "Ready");
            fitAndResize();
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
      if (closeRequestedRef.current) return;
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

    const observer = new ResizeObserver(() => fitAndResize());
    observer.observe(el);
    const fitTimer = window.setTimeout(fitAndResize, 50);

    return () => {
      window.clearTimeout(fitTimer);
      observer.disconnect();
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
    // initialSessionId is captured at mount so a group move can reconnect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  useEffect(() => {
    if (!visible) return undefined;
    const timer = window.setTimeout(() => {
      fitAndResize();
      termRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [visible, fitAndResize]);

  return (
    <div
      className={"terminalPane" + (visible ? "" : " terminalPane--hidden")}
      ref={containerRef}
      aria-hidden={!visible}
    />
  );
}
