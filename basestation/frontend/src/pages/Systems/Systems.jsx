import React, { useCallback, useEffect, useRef, useState } from "react";
import Modal from "react-bootstrap/Modal";
import { getApiBase } from "../../config";
import "./Systems.css";

const POLL_MS = 1000;
const TRANSITIONAL_STATES = new Set(["STARTING", "STOPPING"]);
const CONFIRMED_ACTIONS = new Set(["stop", "restart"]);

const STATE_LABELS = {
  STOPPED: "Stopped",
  UNMANAGED: "Unmanaged",
  STARTING: "Starting",
  RUNNING: "Running",
  STOPPING: "Stopping",
  FAILED: "Failed",
};

const ACTION_LABELS = {
  start: "Start",
  stop: "Stop",
  restart: "Restart",
};

const LAUNCH_AGENT_COMMAND = "ros2 launch kanga_launch_agent launch_agent.launch.py";

function selectCommandField(event) {
  event.target.select();
}

function httpDetail(body, status) {
  if (typeof body?.detail === "string" && body.detail) {
    return body.detail;
  }
  if (Array.isArray(body?.detail)) {
    const joined = body.detail
      .map((item) => item?.msg || item?.detail || item)
      .filter(Boolean)
      .join("; ");
    if (joined) return joined;
  }
  return `Request failed (${status})`;
}

async function systemsRequest(path, { method = "GET", signal } = {}) {
  const response = await fetch(`${getApiBase()}/systems${path}`, {
    credentials: "same-origin",
    signal,
    method,
  });
  let body = {};
  try {
    body = await response.json();
  } catch {
    // Status below still describes the failure if the body is empty.
  }
  if (!response.ok) {
    const error = new Error(httpDetail(body, response.status));
    error.status = response.status;
    throw error;
  }
  return body;
}

function formatDuration(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${String(secs).padStart(2, "0")}s`;
  }
  return `${secs}s`;
}

function formatElapsed(system) {
  if (!system.started_at) return "—";
  const start = new Date(system.started_at);
  if (Number.isNaN(start.getTime())) return "—";
  const live = TRANSITIONAL_STATES.has(system.state) || system.state === "RUNNING";
  let end = Date.now();
  if (!live) {
    if (system.state !== "FAILED" || !system.transitioned_at) return "—";
    const stopped = new Date(system.transitioned_at);
    if (Number.isNaN(stopped.getTime())) return "—";
    end = stopped.getTime();
  }
  return formatDuration(end - start.getTime());
}

function processStateClass(state) {
  switch (state) {
    case "RUNNING":
      return "systemsState--running";
    case "FAILED":
      return "systemsState--failed";
    case "UNMANAGED":
      return "systemsState--unmanaged";
    case "STARTING":
    case "STOPPING":
      return "systemsState--transition";
    default:
      return "systemsState--stopped";
  }
}

function actionButtonClass(action) {
  if (action === "start") return "systemsButton systemsButton--start";
  if (action === "stop") return "systemsButton systemsButton--stop";
  return "systemsButton systemsButton--restart";
}

function confirmCopy(system, action) {
  if (action === "stop") {
    return `Stop ${system.label}? The onboard agent will shut down the owned launch process group.`;
  }
  return `Restart ${system.label}? The onboard agent will stop the owned process, then start the same fixed profile.`;
}

export default function Systems() {
  const [systems, setSystems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState("");
  const [connectionStatus, setConnectionStatus] = useState(0);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [confirm, setConfirm] = useState(null);
  const busyRef = useRef(false);

  const applyStatus = useCallback((status) => {
    if (!status?.id) return;
    setSystems((current) => {
      const exists = current.some((item) => item.id === status.id);
      if (!exists) return [...current, status];
      return current.map((item) => (item.id === status.id ? status : item));
    });
  }, []);

  const refresh = useCallback(async (signal) => {
    const body = await systemsRequest("", { signal });
    setSystems(Array.isArray(body.systems) ? body.systems : []);
    setConnectionError("");
    setConnectionStatus(0);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const poll = async () => {
      if (busyRef.current) return;
      try {
        await refresh(controller.signal);
      } catch (error) {
        if (cancelled || error.name === "AbortError") return;
        setConnectionError(error.message);
        setConnectionStatus(error.status || 0);
        if (error.status === 503) {
          setSystems([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [refresh]);

  const runAction = async (system, action) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusyKey(`${system.id}:${action}`);
    setActionError("");
    setNotice("");
    try {
      const status = await systemsRequest(`/${encodeURIComponent(system.id)}/${action}`, {
        method: "POST",
      });
      applyStatus(status);
      setNotice(`${system.label}: ${ACTION_LABELS[action] || action} requested.`);
    } catch (error) {
      setActionError(error.message);
    } finally {
      busyRef.current = false;
      setBusyKey("");
      setConfirm(null);
    }
  };

  const requestAction = (system, action) => {
    if (CONFIRMED_ACTIONS.has(action)) {
      setConfirm({ system, action });
      return;
    }
    runAction(system, action);
  };

  return (
    <div className="systemsPage">
      <div className="container-fluid px-3 py-2">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <div>
            <h3 className="text-white mb-1">System Startup</h3>
            <p className="small text-white-50 mb-0">
              Start, stop, and restart reviewed rover launches. The onboard agent
              owns the command; this page only sends a system id and action.
            </p>
          </div>
        </div>

        {connectionError ? (
          <div className="alert alert-danger py-2 mb-3" role="alert">
            <strong>
              {connectionStatus === 503 ? "Launch agent unavailable." : "Could not load systems."}
            </strong>{" "}
            {connectionError}
            {connectionStatus === 503 ? (
              <>
                {" "}Start it in the ROS container with
                {" "}
                <input
                  className="systemsCommand"
                  type="text"
                  readOnly
                  spellCheck="false"
                  value={LAUNCH_AGENT_COMMAND}
                  size={LAUNCH_AGENT_COMMAND.length}
                  aria-label="Launch agent command"
                  onFocus={selectCommandField}
                  onDoubleClick={selectCommandField}
                />
                .
              </>
            ) : null}
          </div>
        ) : null}

        {actionError ? (
          <div className="alert alert-warning py-2 mb-3" role="alert">
            {actionError}
          </div>
        ) : notice ? (
          <p className="small text-white-50 mb-3" role="status">{notice}</p>
        ) : null}

        {loading ? (
          <p className="text-white-50">Loading managed systems…</p>
        ) : null}

        {!loading && !connectionError && systems.length === 0 ? (
          <div className="alert alert-secondary">
            The launch agent returned no profiles.
          </div>
        ) : null}

        <div className="row g-3 pb-3">
          {systems.map((system) => {
            const transitional = TRANSITIONAL_STATES.has(system.state);
            const unmanaged = system.state === "UNMANAGED";
            const actions = unmanaged ? [] : (system.allowed_actions || []);
            return (
              <div className="col-12 col-lg-6 col-xxl-4" key={system.id}>
                <section className="systemsPanel p-3 h-100" aria-label={system.label}>
                  <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-2">
                    <div>
                      <h5 className="text-white mb-1">{system.label}</h5>
                      <div className="small text-white-50">{system.id}</div>
                    </div>
                    <div className="d-flex flex-wrap gap-2">
                      <span className={`systemsState ${processStateClass(system.state)}`}>
                        {STATE_LABELS[system.state] || system.state}
                      </span>
                      <span className="systemsState systemsState--health">
                        Health: {system.health || "NOT_CHECKED"}
                      </span>
                      <span className="systemsState systemsState--health">
                        {formatElapsed(system)}
                      </span>
                    </div>
                  </div>

                  {system.exit_code != null ? (
                    <p className="systemsError mb-2">Exit code {system.exit_code}</p>
                  ) : null}

                  {transitional ? (
                    <p className="systemsProgress" role="status">
                      {system.state === "STARTING"
                        ? "Startup in progress."
                        : "Shutdown in progress."}
                    </p>
                  ) : null}

                  {unmanaged ? (
                    <div className="alert alert-warning py-2 mb-3">
                      This stack is already running outside the launch agent,
                      for example a manual <code>ros2 launch</code> or local
                      simulation. The agent will not start, stop, or restart it.
                      Stop the external process yourself before this page can
                      take ownership.
                    </div>
                  ) : null}

                  {system.last_error ? (
                    <p className="systemsError">{system.last_error}</p>
                  ) : null}

                  {actions.length ? (
                    <div className="systemsActions">
                      {actions.map((action) => {
                        const disabled = Boolean(busyKey)
                          || (!system.available && action === "start")
                          || (transitional && action !== "stop");
                        return (
                          <button
                            key={action}
                            type="button"
                            className={actionButtonClass(action)}
                            disabled={disabled}
                            onClick={() => requestAction(system, action)}
                          >
                            {busyKey === `${system.id}:${action}`
                              ? `${ACTION_LABELS[action]}…`
                              : ACTION_LABELS[action] || action}
                          </button>
                        );
                      })}
                    </div>
                  ) : !unmanaged && !transitional ? (
                    <p className="small text-white-50 mb-0">No actions available.</p>
                  ) : null}
                </section>
              </div>
            );
          })}
        </div>
      </div>

      <Modal
        show={Boolean(confirm)}
        onHide={() => !busyKey && setConfirm(null)}
        centered
        contentClassName="systemsModal"
        backdropClassName="systemsModalBackdrop"
      >
        <Modal.Header closeButton className="systemsModalHeader">
          <Modal.Title>
            {confirm ? `${ACTION_LABELS[confirm.action]} ${confirm.system.label}?` : ""}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {confirm ? confirmCopy(confirm.system, confirm.action) : null}
        </Modal.Body>
        <Modal.Footer>
          <button
            type="button"
            className="systemsButton systemsButton--restart"
            disabled={Boolean(busyKey)}
            onClick={() => setConfirm(null)}
          >
            Cancel
          </button>
          <button
            type="button"
            className={confirm ? actionButtonClass(confirm.action) : "systemsButton"}
            disabled={Boolean(busyKey)}
            onClick={() => confirm && runAction(confirm.system, confirm.action)}
          >
            {confirm ? ACTION_LABELS[confirm.action] : "Confirm"}
          </button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
