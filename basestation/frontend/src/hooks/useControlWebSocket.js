import { useCallback, useEffect, useRef, useState } from "react";
import { getWsBase } from "../config";

export const CONTROL_TAKEN = 4000;

/**
 * Drive control WebSocket — newest tab wins (server close code 4000).
 * Reconnects on drop unless bumped; drive must start disabled after connect.
 */
export function useControlWebSocket({ enabled, getCommand, onConnect }) {
  const wsRef = useRef(null);
  const enabledRef = useRef(enabled);
  const getCommandRef = useRef(getCommand);
  const [linkState, setLinkState] = useState("connecting");
  const [bumped, setBumped] = useState(false);

  enabledRef.current = enabled;
  getCommandRef.current = getCommand;

  const sendStop = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ t: "drive", x: 0, yaw: 0, scale: 0 }));
    }
  }, []);

  const connect = useCallback(() => {
    setBumped(false);
    setLinkState("connecting");
    const ws = new WebSocket(`${getWsBase()}/ws/control`);
    wsRef.current = ws;

    ws.onopen = () => {
      setLinkState("connected");
      onConnect?.();
      sendStop();
    };

    ws.onclose = (ev) => {
      wsRef.current = null;
      if (ev.code === CONTROL_TAKEN) {
        setLinkState("bumped");
        setBumped(true);
        return;
      }
      setLinkState("reconnecting");
      setTimeout(connect, 1000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onConnect, sendStop]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  useEffect(() => {
    const dropAllInput = () => sendStop();
    window.addEventListener("blur", dropAllInput);
    const onVis = () => {
      if (document.hidden) dropAllInput();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.removeEventListener("blur", dropAllInput);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [sendStop]);

  useEffect(() => {
    const tick = () => {
      const ws = wsRef.current;
      if (!enabledRef.current || !ws || ws.readyState !== WebSocket.OPEN) return;
      const cmd = document.hidden
        ? { x: 0, yaw: 0, scale: 0 }
        : getCommandRef.current();
      ws.send(JSON.stringify({ t: "drive", ...cmd }));
    };
    const id = setInterval(tick, 50);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!enabled) sendStop();
  }, [enabled, sendStop]);

  return { linkState, bumped, retakeControl: connect, sendStop };
}
