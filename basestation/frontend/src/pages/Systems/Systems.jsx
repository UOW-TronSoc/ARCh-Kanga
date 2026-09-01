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

function formatTimestamp(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
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
                {" "}<code>ros2 launch kanga_launch_agent launch_agent.launch.py</code>.
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
                  <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
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
                    </div>
                  </div>

                  <dl className="systemsMeta">
                    <div>
                      <dt>Ownership</dt>
                      <dd>{system.owned ? "Owned by launch agent" : "Not owned by launch agent"}</dd>
                    </div>
                    <div>
                      <dt>Profile</dt>
                      <dd>{system.available ? "Launch executable available" : "Launch executable unavailable"}</dd>
                    </div>
                    <div>
                      <dt>Started</dt>
                      <dd>{formatTimestamp(system.started_at)}</dd>
                    </div>
                    <div>
                      <dt>Last change</dt>
                      <dd>{formatTimestamp(system.transitioned_at)}</dd>
                    </div>
                    {system.exit_code != null ? (
                      <div>
                        <dt>Exit code</dt>
                        <dd>{system.exit_code}</dd>
                      </div>
                    ) : null}
                  </dl>

                  {transitional ? (
                    <p className="systemsProgress" role="status">
                      {system.state === "STARTING"
                        ? "Startup in progress. Process state will become Running after the startup window, independent of sensor health."
                        : "Shutdown in progress. The agent is signalling the owned process group."}
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
