/** Same-origin API + WebSocket bases (single port 8000). */

const getOrigin = () => {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://127.0.0.1:8000";
};

export const getBackendBase = () => getOrigin();

export const getApiBase = () => `${getOrigin()}/api`;

export const getWsBase = () => {
  if (typeof window !== "undefined" && window.location) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "ws://127.0.0.1:8000";
};
