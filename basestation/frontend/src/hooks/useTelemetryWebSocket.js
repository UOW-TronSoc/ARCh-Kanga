import { useEffect, useState } from "react";
import { getWsBase } from "../config";

const INITIAL = {
  connected: false,
  drivestop: null,
  whs_online: false,
  closed_loop: false,
  wheels: null,
  body: null,
};

export function useTelemetryWebSocket() {
  const [telemetry, setTelemetry] = useState(INITIAL);

  useEffect(() => {
    let alive = true;
    let ws = null;
    let retryTimer = null;

    const connect = () => {
      ws = new WebSocket(`${getWsBase()}/ws/telemetry`);
      ws.onopen = () => {
        if (alive) setTelemetry((t) => ({ ...t, connected: true }));
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (alive) {
            setTelemetry({
              connected: true,
              drivestop: data.drivestop ?? null,
              whs_online: !!data.whs_online,
              closed_loop: !!data.closed_loop,
              wheels: data.wheels ?? null,
              body: data.body ?? null,
            });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (alive) {
          setTelemetry((t) => ({ ...t, connected: false }));
          retryTimer = setTimeout(connect, 1000);
        }
      };
    };

    connect();
    return () => {
      alive = false;
      clearTimeout(retryTimer);
      ws?.close();
    };
  }, []);

  return telemetry;
}
