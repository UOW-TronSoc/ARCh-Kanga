import React, { useCallback, useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { getWsBase } from "../../config";
import "./Terminal.css";

const PIN_CLOSE = 4401;

export default function TerminalPage() {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);
  const wsRef = useRef(null);
  const [status, setStatus] = useState("Connecting…");
  const [cwd, setCwd] = useState("");

  const sendResize = useCallback(() => {
    const term = termRef.current;
    const ws = wsRef.current;
    if (!term || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        t: "resize",
        cols: term.cols,
        rows: term.rows,
      })
    );
  }, []);

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
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    const ws = new WebSocket(`${getWsBase()}/ws/terminal`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("Connected");
      sendResize();
    };

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          if (msg.t === "ready") {
            setCwd(msg.cwd || "");
            setStatus("Ready");
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
      if (event.code === PIN_CLOSE) {
        setStatus("PIN required — sign in, then reopen Terminal");
        term.writeln(
          "\r\n\x1b[31mPIN authentication is required for the terminal.\x1b[0m"
        );
        return;
      }
      setStatus((prev) =>
        prev.startsWith("Shell exited") || prev.includes("PIN") || prev.includes("error")
          ? prev
          : "Disconnected"
      );
    };

    const onData = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });

    const onResize = () => {
      try {
        fit.fit();
        sendResize();
      } catch {
        /* container may be hidden */
      }
    };
    window.addEventListener("resize", onResize);
    // Fit once after layout settles.
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
  }, [sendResize]);

  return (
    <div className="terminalPage">
      <div className="terminalToolbar">
        <div className="terminalToolbar-title">
          <span className="terminalToolbar-label">Host terminal</span>
          {cwd ? (
            <code className="terminalToolbar-cwd" title={cwd}>
              {cwd}
            </code>
          ) : null}
        </div>
        <span
          className={
            "terminalToolbar-status" +
            (status === "Ready" || status === "Connected"
              ? " terminalToolbar-status--ok"
              : status.includes("error") || status.includes("PIN")
                ? " terminalToolbar-status--err"
                : "")
          }
        >
          {status}
        </span>
      </div>
      <div className="terminalPane" ref={containerRef} />
    </div>
  );
}
