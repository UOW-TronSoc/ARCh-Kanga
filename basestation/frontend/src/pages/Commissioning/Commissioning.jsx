import React, { useEffect, useMemo, useState } from "react";
import Modal from "react-bootstrap/Modal";
import { getApiBase } from "../../config";
import "./Commissioning.css";

const EDITOR_TABS = [
  ["individual", "Individual config"],
  ["shared", "Shared config"],
  ["limits", "Soft limits"],
];

// A failed job remains active until the operator retries, skips, or cancels it.
const TERMINAL_JOB_STATES = new Set([
  "succeeded",
  "completed_with_skips",
  "cancelled",
]);
const JOB_STATE_LABELS = {
  pending: "Pending",
  awaiting_confirmation: "Awaiting confirmation",
  running: "Running",
  succeeded: "Complete",
  completed_with_skips: "Complete with skips",
  failed: "Failed",
  skipped: "Skipped",
  cancelled: "Cancelled",
};

async function commissioningRequest(
  path,
  { signal, method = "GET", body: requestBody } = {},
) {
  const response = await fetch(`${getApiBase()}/commissioning${path}`, {
    credentials: "same-origin",
    signal,
    method,
    headers: requestBody === undefined ? undefined : { "Content-Type": "application/json" },
    body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
  });

  let responseBody = {};
  try {
    responseBody = await response.json();
  } catch {
    // The status code below still gives a useful error if the body is empty.
  }

  if (!response.ok) {
    throw new Error(responseBody.detail || `Request failed (${response.status})`);
  }
  return responseBody;
}

function configPath(editorTab, subsystemId, motorId) {
  if (editorTab === "shared") {
    return "kanga_core_drive/config/motors/shared_motor_config.py";
  }
  if (editorTab === "limits") {
    return `kanga_core_description/config/motor_limits/${subsystemId}.yaml`;
  }
  return `kanga_core_drive/config/motors/wheel_${motorId}_motor_config.py`;
}

function shortMotorLabel(motor) {
  return motor?.id?.toUpperCase() || "motor";
}

function editorEndpoint(editorTab, subsystemId, motorId) {
  return editorTab === "limits"
    ? `/soft-limits/${subsystemId}`
    : `/configs/${subsystemId}/${editorTab === "shared" ? "shared" : motorId}`;
}

export default function Commissioning() {
  const [subsystems, setSubsystems] = useState([]);
  const [subsystemId, setSubsystemId] = useState("core");
  const [motorId, setMotorId] = useState("");
  const [editorTab, setEditorTab] = useState("individual");
  const [configRecords, setConfigRecords] = useState({});
  const [draftConfigs, setDraftConfigs] = useState({});

  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [catalogReload, setCatalogReload] = useState(0);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [configsError, setConfigsError] = useState("");
  const [configsReload, setConfigsReload] = useState(0);
  const [savingConfig, setSavingConfig] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [notice, setNotice] = useState("");
  const [job, setJob] = useState(null);
  const [startingJob, setStartingJob] = useState(false);
  const [updatingJob, setUpdatingJob] = useState(false);
  const [jobError, setJobError] = useState("");

  const subsystem = useMemo(
    () => subsystems.find((item) => item.id === subsystemId),
    [subsystems, subsystemId],
  );
  const motors = useMemo(() => subsystem?.motors ?? [], [subsystem]);
  const motor = motors.find((item) => item.id === motorId) ?? motors[0];
  const configKey = editorTab === "individual" ? motor?.id : editorTab;
  const configRecord = configKey ? configRecords[configKey] : null;
  const currentDraft = configKey ? draftConfigs[configKey] ?? "" : "";
  const currentEditorDirty = Boolean(
    configRecord && currentDraft !== configRecord.content,
  );
  const hasAnyDirty = useMemo(
    () => Object.entries(configRecords).some(
      ([key, record]) => (draftConfigs[key] ?? "") !== record.content,
    ),
    [configRecords, draftConfigs],
  );
  const jobId = job?.id;
  const jobActive = Boolean(job && !TERMINAL_JOB_STATES.has(job.state));
  const calibrationAwaitingConfirmation = Boolean(
    job?.operation === "calibrate" && job.state === "awaiting_confirmation",
  );
  const calibrationMotor = calibrationAwaitingConfirmation
    ? job.items[job.active_index]
    : null;
  const failureAwaitingDecision = Boolean(job?.state === "failed");
  const failedMotor = failureAwaitingDecision
    ? job.items[job.active_index]
    : null;
  const multiMotorSequence = Boolean(job?.items.length > 1);

  useEffect(() => {
    document.title = "Commissioning";
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCatalog() {
      setCatalogLoading(true);
      setCatalogError("");
      try {
        const catalog = await commissioningRequest("/catalog", {
          signal: controller.signal,
        });
        const loadedSubsystems = catalog.subsystems ?? [];
        setSubsystems(loadedSubsystems);
        setSubsystemId((currentId) =>
          loadedSubsystems.some((item) => item.id === currentId)
            ? currentId
            : loadedSubsystems[0]?.id || "",
        );
      } catch (error) {
        if (error.name !== "AbortError") {
          setCatalogError(error.message || "Could not load the motor catalog.");
        }
      } finally {
        if (!controller.signal.aborted) setCatalogLoading(false);
      }
    }

    loadCatalog();
    return () => controller.abort();
  }, [catalogReload]);

  useEffect(() => {
    if (!subsystem?.available) {
      setConfigRecords({});
      setDraftConfigs({});
      setConfigsError("");
      setSaveError("");
      setNotice("");
      setConfigsLoading(false);
      return undefined;
    }

    const controller = new AbortController();

    async function loadConfigs() {
      setConfigsLoading(true);
      setConfigsError("");
      setConfigRecords({});
      setDraftConfigs({});
      setSaveError("");
      setNotice("");

      try {
        // Each record includes active content, immutable default content, and
        // a revision token. Drafts stay separate so Reset never needs a GET.
        const requests = [
          ["shared", `/configs/${subsystem.id}/shared`],
          ["limits", `/soft-limits/${subsystem.id}`],
          ...subsystem.motors.map((item) => [
            item.id,
            `/configs/${subsystem.id}/${item.id}`,
          ]),
        ];
        const loaded = await Promise.all(
          requests.map(async ([key, path]) => [
            key,
            await commissioningRequest(path, { signal: controller.signal }),
          ]),
        );
        const records = Object.fromEntries(loaded);
        setConfigRecords(records);
        setDraftConfigs(
          Object.fromEntries(
            Object.entries(records).map(([key, record]) => [key, record.content]),
          ),
        );
      } catch (error) {
        if (error.name !== "AbortError") {
          setConfigsError(error.message || "Could not load motor configurations.");
        }
      } finally {
        if (!controller.signal.aborted) setConfigsLoading(false);
      }
    }

    loadConfigs();
    return () => controller.abort();
  }, [subsystem, configsReload]);

  useEffect(() => {
    if (motors.length && !motors.some((item) => item.id === motorId)) {
      setMotorId(motors[0].id);
    }
  }, [motors, motorId]);

  useEffect(() => {
    const warnBeforeUnload = (event) => {
      if (!hasAnyDirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [hasAnyDirty]);

  useEffect(() => {
    if (!jobId) return undefined;

    const controller = new AbortController();
    let pollTimer;

    async function pollJob() {
      try {
        const latest = await commissioningRequest(`/jobs/${jobId}`, {
          signal: controller.signal,
        });
        setJob(latest);
        setJobError("");

        if (latest.state === "succeeded") {
          const calibration = latest.operation === "calibrate";
          setNotice(
            latest.items.length === 1
              ? calibration
                ? `${latest.items[0].label} calibrated and saved successfully.`
                : `${latest.items[0].label} configuration applied and saved to ODrive.`
              : calibration
                ? `Sequential calibration completed for ${latest.items.length} motors.`
                : `Save All completed for ${latest.items.length} motors.`,
          );
          return;
        }
        if (latest.state === "completed_with_skips") {
          const skippedCount = latest.items.filter(
            (item) => item.state === "skipped",
          ).length;
          setNotice(
            `${latest.operation === "calibrate" ? "Calibration" : "Save"} sequence completed with ${skippedCount} skipped ${skippedCount === 1 ? "motor" : "motors"}.`,
          );
          return;
        }
        if (latest.state === "failed") {
          setJobError(
            `${latest.items[latest.active_index]?.label || "Motor"} failed. Choose how to continue.`,
          );
          // The job remains active while the failure dialog is open. Keep
          // polling so a retry or skip resumes progress under the same job ID.
          pollTimer = window.setTimeout(pollJob, 500);
          return;
        }
        if (latest.state === "cancelled") {
          setJobError(
            latest.operation === "calibrate"
              ? "Calibration was cancelled before the waiting motor ran."
              : "The save job was cancelled.",
          );
          return;
        }
        pollTimer = window.setTimeout(pollJob, 500);
      } catch (error) {
        if (error.name === "AbortError") return;
        setJobError(
          `${error.message || "Could not read job progress."} Retrying…`,
        );
        pollTimer = window.setTimeout(pollJob, 1000);
      }
    }

    pollTimer = window.setTimeout(pollJob, 250);
    return () => {
      controller.abort();
      window.clearTimeout(pollTimer);
    };
  }, [jobId]);

  const discardDraft = (key) => {
    const record = configRecords[key];
    if (!record) return;
    setDraftConfigs((current) => ({ ...current, [key]: record.content }));
  };

  const confirmDiscard = (key) => {
    const record = configRecords[key];
    if (!record || (draftConfigs[key] ?? "") === record.content) return true;
    if (!window.confirm("Discard the unsaved changes in this editor?")) return false;
    discardDraft(key);
    return true;
  };

  const selectSubsystem = (nextId) => {
    if (nextId === subsystemId) return;
    if (
      hasAnyDirty
      && !window.confirm("Discard all unsaved commissioning config changes?")
    ) return;
    setSubsystemId(nextId);
    setEditorTab("individual");
    setMotorId("");
  };

  const selectMotor = (nextId) => {
    if (nextId === motor?.id) return;
    if (editorTab === "individual" && !confirmDiscard(configKey)) return;
    setMotorId(nextId);
    setSaveError("");
    setNotice("");
  };

  const selectTab = (nextTab) => {
    if (nextTab === editorTab || !confirmDiscard(configKey)) return;
    setEditorTab(nextTab);
    setSaveError("");
    setNotice("");
  };

  const changeDraft = (content) => {
    if (!configKey) return;
    setDraftConfigs((current) => ({ ...current, [configKey]: content }));
    setSaveError("");
    setNotice("");
  };

  const resetEditor = () => {
    discardDraft(configKey);
    setSaveError("");
    setNotice("Reset to the last version loaded from the basestation.");
  };

  const restoreDefaults = () => {
    if (!configRecord || !configKey) return;
    setDraftConfigs((current) => ({
      ...current,
      [configKey]: configRecord.default_content,
    }));
    setSaveError("");
    setNotice("Defaults staged in the editor. Save File is still required.");
  };

  const saveEditor = async () => {
    if (!configRecord || !configKey || !currentEditorDirty) return;

    setSavingConfig(true);
    setSaveError("");
    setNotice("");
    try {
      const saved = await commissioningRequest(
        editorEndpoint(editorTab, subsystem.id, motor?.id),
        {
          method: "PUT",
          body: {
            content: currentDraft,
            revision: configRecord.revision,
          },
        },
      );
      setConfigRecords((current) => ({ ...current, [configKey]: saved }));
      setDraftConfigs((current) => ({ ...current, [configKey]: saved.content }));
      setNotice("Configuration saved and its revision refreshed.");
    } catch (error) {
      setSaveError(error.message || "Could not save this configuration.");
    } finally {
      setSavingConfig(false);
    }
  };

  const beginJob = async (operation, motorIds) => {
    if (
      !subsystem?.available
      || !motorIds.length
      || hasAnyDirty
      || savingConfig
      || startingJob
      || jobActive
    ) return;

    setStartingJob(true);
    setJobError("");
    const calibration = operation === "calibrate";
    if (calibration) {
      setNotice("Starting calibration and waiting for confirmation that the motor is free to spin…");
    } else {
      setNotice(
        motorIds.length === 1
          ? `Starting save for ${motor?.label || motorIds[0]}…`
          : "Starting sequential Save All…",
      );
    }
    try {
      const created = await commissioningRequest("/jobs", {
        method: "POST",
        body: {
          subsystem: subsystem.id,
          operation,
          motor_ids: motorIds,
        },
      });
      setJob(created);
    } catch (error) {
      setJobError(
        error.message
        || `Could not start the motor ${calibration ? "calibration" : "save"} job.`,
      );
      setNotice("");
    } finally {
      setStartingJob(false);
    }
  };

  const confirmCalibration = async () => {
    if (!calibrationAwaitingConfirmation || updatingJob) return;
    setUpdatingJob(true);
    setJobError("");
    setNotice(
      `Temporarily releasing drivestop and calibrating ${calibrationMotor.label}…`,
    );
    try {
      const updated = await commissioningRequest(`/jobs/${job.id}/confirm`, {
        method: "POST",
      });
      setJob(updated);
    } catch (error) {
      setJobError(error.message || "Could not confirm this motor calibration.");
    } finally {
      setUpdatingJob(false);
    }
  };

  const cancelCalibration = async () => {
    if (!calibrationAwaitingConfirmation || updatingJob) return;
    setUpdatingJob(true);
    setJobError("");
    try {
      const updated = await commissioningRequest(`/jobs/${job.id}/cancel`, {
        method: "POST",
      });
      setJob(updated);
    } catch (error) {
      setJobError(error.message || "Could not cancel this calibration job.");
    } finally {
      setUpdatingJob(false);
    }
  };

  const resolveFailedJob = async (action) => {
    if (!failureAwaitingDecision || updatingJob) return;
    setUpdatingJob(true);
    setJobError("");
    try {
      const updated = await commissioningRequest(`/jobs/${job.id}/${action}`, {
        method: "POST",
      });
      setJob(updated);

      if (action === "retry") {
        setNotice(
          job.operation === "calibrate"
            ? `Retry requested for ${failedMotor.label}; confirm it is free to spin.`
            : `Retrying the save for ${failedMotor.label}…`,
        );
      } else if (action === "skip") {
        setNotice(`${failedMotor.label} skipped; continuing the sequence.`);
      } else {
        setNotice("");
      }
    } catch (error) {
      setJobError(error.message || `Could not ${action} this commissioning job.`);
    } finally {
      setUpdatingJob(false);
    }
  };

  const loading = catalogLoading || configsLoading;
  const loadError = catalogError || configsError;
  const pageError = loadError || saveError;
  const controlsLocked = savingConfig || startingJob || updatingJob || jobActive;
  const motorActionsDisabled = Boolean(
    !subsystem?.available
    || loading
    || controlsLocked
    || hasAnyDirty
    || !motors.length,
  );

  return (
    <div className="commissioningPage">
      <div className="container-fluid px-3 py-2">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <h3 className="text-white mb-0">Motor Commissioning</h3>
          <span className="badge bg-secondary">Backend configuration editor</span>
        </div>

        {pageError ? (
          <div className="alert alert-danger py-2 mb-3 commissioningPreview" role="alert">
            <div className="d-flex flex-wrap justify-content-between align-items-center gap-2">
              <span>
                <strong>{saveError ? "Save failed:" : "Could not load commissioning data:"}</strong>{" "}
                {pageError}
              </span>
              {loadError ? (
                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  onClick={() => (catalogError
                    ? setCatalogReload((value) => value + 1)
                    : setConfigsReload((value) => value + 1))}
                >
                  Retry
                </button>
              ) : null}
            </div>
          </div>
        ) : notice ? (
          <p className="small text-white-50 mb-3" role="status">{notice}</p>
        ) : null}

        <section className="commissioningPanel p-3 mb-3" aria-label="Motor selection">
          <div className="row g-3 align-items-end">
            <div className="col-sm-6 col-lg-3">
              <label className="form-label" htmlFor="commissioning-subsystem">
                Subsystem
              </label>
              <select
                id="commissioning-subsystem"
                className="form-select form-select-sm"
                value={subsystemId}
                disabled={catalogLoading || controlsLocked || !subsystems.length}
                onChange={(event) => selectSubsystem(event.target.value)}
              >
                {subsystems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}{item.available ? "" : " — coming later"}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-sm-6 col-lg-3">
              <label className="form-label" htmlFor="commissioning-motor">
                Motor
              </label>
              <select
                id="commissioning-motor"
                className="form-select form-select-sm"
                value={motor?.id || ""}
                disabled={!subsystem?.available || configsLoading || controlsLocked || !motors.length}
                onChange={(event) => selectMotor(event.target.value)}
              >
                {motors.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label} · {item.namespace}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-lg-6">
              <div className="small text-white-50">
                <span
                  className={`badge me-2 ${subsystem?.available ? "text-bg-success" : "text-bg-danger"}`}
                >
                  {subsystem?.available ? "Available" : "Unavailable"}
                </span>
                {subsystem?.description || (catalogLoading ? "Loading catalog…" : "No subsystem selected")}
              </div>
            </div>
          </div>
        </section>

        {subsystem && !subsystem.available ? (
          <div className="alert alert-secondary">
            <h5 className="alert-heading">{subsystem.label} commissioning is not available yet</h5>
            <p className="mb-0">
              It will become active after the subsystem provides motor IDs, configuration files,
              namespaces, and a CAN interface through the commissioning catalog.
            </p>
          </div>
        ) : subsystem?.available ? (
          <div className="row g-3 pb-3">
            <div className="col-xl-8">
              <section className="commissioningPanel p-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-3">
                  <h5 className="text-white mb-0">
                    {editorTab === "individual"
                      ? `${motor?.label || "Motor"} configuration`
                      : editorTab === "shared"
                        ? "Shared motor configuration"
                        : "Soft-limit configuration"}
                  </h5>
                  <span
                    className={`badge ${currentEditorDirty ? "text-bg-warning" : "text-bg-secondary"}`}
                  >
                    {savingConfig
                      ? "Saving"
                      : configsLoading
                        ? "Loading"
                        : currentEditorDirty
                          ? "Unsaved"
                          : "Saved"}
                  </span>
                </div>

                <div className="nav nav-tabs commissioningTabs mb-3" role="tablist">
                  {EDITOR_TABS.map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      role="tab"
                      aria-selected={editorTab === id}
                      className={`nav-link ${editorTab === id ? "active" : ""}`}
                      disabled={controlsLocked}
                      onClick={() => selectTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div>
                  <div className="commissioningFileMeta">
                    <code>{configPath(editorTab, subsystem.id, motor?.id)}</code>
                  </div>
                  <textarea
                    className="commissioningTextEditor"
                    spellCheck="false"
                    aria-label={`${editorTab} configuration`}
                    disabled={configsLoading || controlsLocked || !configRecord}
                    value={currentDraft}
                    onChange={(event) => changeDraft(event.target.value)}
                    placeholder={configsLoading ? "Loading configuration…" : "Configuration unavailable"}
                  />
                  {editorTab === "limits" ? (
                    <div className="form-text text-white-50 mt-2">
                      Saved limits apply to runtime controllers after the core stack is relaunched.
                    </div>
                  ) : null}
                </div>

                <div className="d-flex flex-wrap justify-content-end gap-2 mt-3">
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={configsLoading || controlsLocked || !configRecord}
                    onClick={restoreDefaults}
                  >
                    Restore defaults
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={configsLoading || controlsLocked || !currentEditorDirty}
                    onClick={resetEditor}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={configsLoading || controlsLocked || !currentEditorDirty}
                    onClick={saveEditor}
                  >
                    {savingConfig ? "Saving…" : "Save file"}
                  </button>
                </div>
              </section>
            </div>

            <div className="col-xl-4">
              <section className="commissioningPanel p-3 mb-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
                  <h5 className="text-white mb-0">Commission motors</h5>
                  <span className="badge text-bg-secondary">
                    {subsystem.can_interface || "CAN unavailable"}
                  </span>
                </div>

                <dl className="commissioningMotorDetails">
                  <div><dt>Selected</dt><dd>{motor?.label}</dd></div>
                  <div><dt>Namespace</dt><dd>/{motor?.namespace}</dd></div>
                  <div><dt>Node</dt><dd>{motor?.node_id}</dd></div>
                  <div><dt>Profile</dt><dd>{subsystem.drivetrain_profile}</dd></div>
                </dl>

                {hasAnyDirty ? (
                  <div className="alert alert-warning py-2 small">
                    Save or reset editor changes before commissioning motors.
                  </div>
                ) : null}

                <div className="commissioningActionGroup">
                  <div className="small text-white-50 mb-2">Selected motor</div>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={motorActionsDisabled}
                    onClick={() => beginJob("save", [motor.id])}
                  >
                    {startingJob ? "Starting…" : `Save ${shortMotorLabel(motor)}`}
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={motorActionsDisabled}
                    onClick={() => beginJob("calibrate", [motor.id])}
                  >
                    Calibrate {shortMotorLabel(motor)}
                  </button>
                </div>

                <hr className="border-secondary" />

                <div className="commissioningActionGroup">
                  <div className="small text-white-50 mb-2">All {subsystem.label.toLowerCase()} motors</div>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={motorActionsDisabled}
                    onClick={() => beginJob("save", motors.map((item) => item.id))}
                  >
                    {startingJob ? "Starting…" : "Save all"}
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={motorActionsDisabled}
                    onClick={() => beginJob(
                      "calibrate",
                      motors.map((item) => item.id),
                    )}
                  >
                    Calibrate all sequentially
                  </button>
                </div>

                <p className="small text-white-50 mt-3 mb-0">
                  Save and calibration temporarily release drivestop for each motor, then
                  reassert it after every attempt. Calibration still requires confirmation.
                </p>
              </section>

              <section className="commissioningPanel p-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
                  <h5 className="text-white mb-0">Commissioning progress</h5>
                  {job ? (
                    <span className={`commissioningJobState state-${job.state}`}>
                      {JOB_STATE_LABELS[job.state] ?? job.state}
                    </span>
                  ) : null}
                </div>

                {jobError ? (
                  <div className="alert alert-danger py-2 small mb-2">{jobError}</div>
                ) : null}

                {job ? (
                  <ol className="commissioningProgressList">
                    {job.items.map((item, index) => (
                      <li key={item.motor_id} className={`state-${item.state}`}>
                        <span className="commissioningProgressIndex">{index + 1}</span>
                        <span>
                          <strong>{item.label}</strong>
                          <small>
                            {item.message || `/${motors.find(
                              (candidate) => candidate.id === item.motor_id,
                            )?.namespace || item.motor_id}`}
                          </small>
                        </span>
                        <span className="commissioningProgressStatus">
                          {JOB_STATE_LABELS[item.state] ?? item.state}
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="small text-white-50 mb-0">
                    Choose a save or calibration action to start a backend job.
                  </p>
                )}
              </section>
            </div>
          </div>
        ) : null}
      </div>

      <Modal
        show={calibrationAwaitingConfirmation}
        onHide={cancelCalibration}
        centered
        contentClassName="commissioningModal"
        backdropClassName="commissioningModalBackdrop"
        backdrop="static"
        keyboard={!updatingJob}
      >
        <Modal.Header closeButton={!updatingJob}>
          <Modal.Title>Is {calibrationMotor?.label} free to spin?</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          This motor will spin during calibration. Confirm it is clear of the ground and cannot
          contact people or equipment.
          <span className="commissioningSequenceHint">
            Drivestop will be released only for this motor and reasserted when the attempt finishes.
          </span>
        </Modal.Body>
        <Modal.Footer>
          <button
            type="button"
            className="commissioningButton commissioningButtonMuted"
            disabled={updatingJob}
            onClick={cancelCalibration}
          >
            Cancel
          </button>
          <button
            type="button"
            className="commissioningButton commissioningButtonAccent"
            disabled={updatingJob}
            onClick={confirmCalibration}
          >
            {updatingJob ? "Starting…" : "Confirm and calibrate"}
          </button>
        </Modal.Footer>
      </Modal>

      <Modal
        show={failureAwaitingDecision}
        onHide={() => resolveFailedJob("cancel")}
        centered
        contentClassName="commissioningModal"
        backdropClassName="commissioningModalBackdrop"
        backdrop="static"
        keyboard={!updatingJob}
      >
        <Modal.Header closeButton={!updatingJob}>
          <Modal.Title>{failedMotor?.label} failed</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p className="mb-2">
            The {job?.operation === "calibrate" ? "calibration" : "save"} attempt did not
            complete.
          </p>
          <div className="alert alert-danger py-2 small mb-0">
            {failedMotor?.message || "No failure detail was returned."}
          </div>
          {job?.operation === "calibrate" ? (
            <span className="commissioningSequenceHint">
              Retrying will ask you to confirm that this motor is free to spin again.
            </span>
          ) : null}
        </Modal.Body>
        <Modal.Footer className="flex-wrap">
          <button
            type="button"
            className="commissioningButton commissioningButtonMuted"
            disabled={updatingJob}
            onClick={() => resolveFailedJob("cancel")}
          >
            Cancel{multiMotorSequence ? " sequence" : ""}
          </button>
          {multiMotorSequence ? (
            <button
              type="button"
              className="commissioningButton commissioningButtonMuted"
              disabled={updatingJob}
              onClick={() => resolveFailedJob("skip")}
            >
              Skip motor
            </button>
          ) : null}
          <button
            type="button"
            className="commissioningButton commissioningButtonAccent"
            disabled={updatingJob}
            onClick={() => resolveFailedJob("retry")}
          >
            {updatingJob
              ? "Updating…"
              : `Retry ${job?.operation === "calibrate" ? "calibration" : "save"}`}
          </button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
