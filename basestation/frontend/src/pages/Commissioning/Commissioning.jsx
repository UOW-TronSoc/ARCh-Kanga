import React, { useEffect, useMemo, useRef, useState } from "react";
import Modal from "react-bootstrap/Modal";
import "./Commissioning.css";

const CORE_MOTORS = [
  { id: "fl", label: "Front left", shortLabel: "FL", nodeId: 1, serial: "394D353B3231" },
  { id: "bl", label: "Back left", shortLabel: "BL", nodeId: 2, serial: "396934453331" },
  { id: "br", label: "Back right", shortLabel: "BR", nodeId: 3, serial: "394E353B3231" },
  { id: "fr", label: "Front right", shortLabel: "FR", nodeId: 4, serial: "3964344C3331" },
];

const SUBSYSTEMS = [
  {
    id: "core",
    label: "Core",
    available: true,
    description: "Four wheel ODrive S1 controllers on can_core",
  },
  {
    id: "arm",
    label: "Arm",
    available: false,
    description: "Motor contracts and configs have not been migrated yet",
  },
  {
    id: "payload",
    label: "Payload",
    available: false,
    description: "Payload commissioning hardware has not been defined yet",
  },
];

const SHARED_DEFAULT = `# Shared ODrive Fibre settings for Kanga drive wheels.
# Soft velocity and acceleration limits are injected after this file.

odrv.config.dc_bus_overvoltage_trip_level = 36
odrv.config.dc_bus_undervoltage_trip_level = 21
odrv.config.dc_max_positive_current = math.inf
odrv.config.dc_max_negative_current = -math.inf
odrv.config.brake_resistor0.enable = True
odrv.axis0.config.motor.motor_type = MotorType.PMSM_CURRENT_CONTROL
odrv.axis0.config.motor.pole_pairs = 20
odrv.axis0.config.motor.torque_constant = 0.0827
odrv.axis0.config.motor.current_soft_max = 50
odrv.axis0.config.motor.current_hard_max = 70
odrv.axis0.config.motor.calibration_current = 10
odrv.axis0.config.motor.resistance_calib_max_voltage = 2
odrv.axis0.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
odrv.axis0.controller.config.input_mode = InputMode.VEL_RAMP
odrv.can.config.protocol = Protocol.SIMPLE
odrv.can.config.baud_rate = 250000
odrv.axis0.config.can.heartbeat_msg_rate_ms = 20
odrv.axis0.config.can.encoder_msg_rate_ms = 10
odrv.axis0.config.enable_watchdog = False
odrv.axis0.config.watchdog_timeout = 1
`;

const SOFT_LIMITS_DEFAULT = `# Editable operating limits for the core wheel motors.
# These values must remain positive and cannot exceed the hard limits in the
# selected drivetrain profile (22 turns/s and 80 turns/s² for drivetrain_2025).

motor_velocity_limit_tps: 22.0
motor_acceleration_limit_tps_s: 80.0
`;

const motorConfig = (motor) => `# ODrive S1 — wheel_${motor.id} (${motor.label.toLowerCase()})
# Merged after shared_motor_config.py by commission_wheels.

SERIAL_NUMBER = "${motor.serial}"

odrv.config.brake_resistor0.resistance = ${motor.id === "bl" || motor.id === "fr" ? "2.4" : "2.2"}
odrv.axis0.config.can.node_id = ${motor.nodeId}
`;

const DEFAULT_CONFIGS = Object.freeze({
  shared: SHARED_DEFAULT,
  limits: SOFT_LIMITS_DEFAULT,
  ...Object.fromEntries(CORE_MOTORS.map((motor) => [motor.id, motorConfig(motor)])),
});

const STATUS_LABELS = {
  pending: "Pending",
  awaiting_confirmation: "Needs confirmation",
  running: "Running",
  succeeded: "Complete",
  failed: "Failed",
  cancelled: "Cancelled",
};

function freshConfigs() {
  return { ...DEFAULT_CONFIGS };
}

function updateJobItem(job, motorId, state) {
  return {
    ...job,
    items: job.items.map((item) => (item.id === motorId ? { ...item, state } : item)),
  };
}

export default function Commissioning() {
  const [subsystemId, setSubsystemId] = useState("core");
  const [motorId, setMotorId] = useState("fl");
  const [editorTab, setEditorTab] = useState("individual");
  const [savedConfigs, setSavedConfigs] = useState(freshConfigs);
  const [draftConfigs, setDraftConfigs] = useState(freshConfigs);
  const [notice, setNotice] = useState("Mock data loaded. No files or motors will be changed.");
  const [job, setJob] = useState(null);

  const timerIds = useRef([]);
  const jobToken = useRef(0);

  const subsystem = SUBSYSTEMS.find((item) => item.id === subsystemId);
  const motor = CORE_MOTORS.find((item) => item.id === motorId) ?? CORE_MOTORS[0];
  const configKey = editorTab === "individual" ? motorId : editorTab;
  const currentEditorDirty = draftConfigs[configKey] !== savedConfigs[configKey];
  const hasAnyDirty = useMemo(
    () => Object.keys(draftConfigs).some((key) => draftConfigs[key] !== savedConfigs[key]),
    [draftConfigs, savedConfigs],
  );

  const jobBusy = job?.state === "running" || job?.state === "awaiting_confirmation";
  const currentJobMotor = job?.items[job.activeIndex] ?? null;

  useEffect(() => {
    document.title = "Commissioning";
  }, []);

  useEffect(
    () => () => {
      timerIds.current.forEach((timerId) => window.clearTimeout(timerId));
    },
    [],
  );

  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (!hasAnyDirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasAnyDirty]);

  const schedule = (callback, delay) => {
    const timerId = window.setTimeout(callback, delay);
    timerIds.current.push(timerId);
  };

  const discardCurrentDraft = () => {
    setDraftConfigs((current) => ({ ...current, [configKey]: savedConfigs[configKey] }));
  };

  const confirmDiscard = () => {
    if (!currentEditorDirty) return true;
    if (!window.confirm("Discard the unsaved changes in this editor?")) return false;
    discardCurrentDraft();
    return true;
  };

  const selectSubsystem = (nextId) => {
    if (nextId === subsystemId || !confirmDiscard()) return;
    setSubsystemId(nextId);
    setNotice(
      nextId === "core"
        ? "Core mock configuration loaded."
        : `${SUBSYSTEMS.find((item) => item.id === nextId)?.label} is shown as a future placeholder.`,
    );
  };

  const selectMotor = (nextId) => {
    if (nextId === motorId || (editorTab === "individual" && !confirmDiscard())) return;
    setMotorId(nextId);
    setNotice(`${CORE_MOTORS.find((item) => item.id === nextId)?.label} selected.`);
  };

  const selectTab = (nextTab) => {
    if (nextTab === editorTab || !confirmDiscard()) return;
    setEditorTab(nextTab);
  };

  const saveEditor = () => {
    setSavedConfigs((current) => ({ ...current, [configKey]: draftConfigs[configKey] }));
    const label =
      editorTab === "individual"
        ? motor.shortLabel
        : editorTab === "shared"
          ? "shared"
          : "soft-limit";
    setNotice(`Mock ${label} config saved locally.`);
  };

  const resetEditor = () => {
    setDraftConfigs((current) => ({ ...current, [configKey]: savedConfigs[configKey] }));
    setNotice("Editor reset to its last mock-saved value.");
  };

  const restoreDefaults = () => {
    setDraftConfigs((current) => ({ ...current, [configKey]: DEFAULT_CONFIGS[configKey] }));
    setNotice("Defaults staged in the editor. Use Save File to keep them.");
  };

  const beginSave = (motorIds) => {
    const token = ++jobToken.current;
    const items = motorIds.map((id, index) => ({
      id,
      label: CORE_MOTORS.find((item) => item.id === id)?.label ?? id,
      state: index === 0 ? "running" : "pending",
    }));
    setJob({ operation: "save", state: "running", activeIndex: 0, items });
    setNotice(`Simulating ${motorIds.length === 1 ? "one motor save" : "Save All"}…`);

    motorIds.forEach((id, index) => {
      schedule(() => {
        if (jobToken.current !== token) return;
        setJob((current) => {
          if (!current) return current;
          let next = updateJobItem(current, id, "succeeded");
          const nextIndex = index + 1;
          if (nextIndex < motorIds.length) {
            next = updateJobItem(next, motorIds[nextIndex], "running");
            return { ...next, activeIndex: nextIndex, state: "running" };
          }
          return { ...next, state: "succeeded" };
        });
        if (index === motorIds.length - 1) {
          setNotice("Mock save complete. No ODrive was contacted.");
        }
      }, (index + 1) * 650);
    });
  };

  const beginCalibration = (motorIds) => {
    ++jobToken.current;
    const items = motorIds.map((id, index) => ({
      id,
      label: CORE_MOTORS.find((item) => item.id === id)?.label ?? id,
      state: index === 0 ? "awaiting_confirmation" : "pending",
    }));
    setJob({ operation: "calibrate", state: "awaiting_confirmation", activeIndex: 0, items });
    setNotice("Calibration mock waiting for off-ground confirmation.");
  };

  const confirmCalibration = () => {
    if (!currentJobMotor) return;
    const token = jobToken.current;
    const activeIndex = job.activeIndex;
    const activeId = currentJobMotor.id;
    setJob((current) => ({ ...updateJobItem(current, activeId, "running"), state: "running" }));
    setNotice(`Simulating calibration and save for ${currentJobMotor.label}…`);

    schedule(() => {
      if (jobToken.current !== token) return;
      setJob((current) => {
        if (!current) return current;
        let next = updateJobItem(current, activeId, "succeeded");
        const nextIndex = activeIndex + 1;
        if (nextIndex < current.items.length) {
          const nextId = current.items[nextIndex].id;
          next = updateJobItem(next, nextId, "awaiting_confirmation");
          return { ...next, activeIndex: nextIndex, state: "awaiting_confirmation" };
        }
        return { ...next, state: "succeeded" };
      });
      setNotice(
        activeIndex + 1 < job.items.length
          ? "Motor complete. Confirm the next motor when it is safely off the ground."
          : "Mock calibration sequence complete. No ODrive was contacted.",
      );
    }, 950);
  };

  const cancelCalibration = () => {
    ++jobToken.current;
    setJob((current) => {
      if (!current) return current;
      return {
        ...current,
        state: "cancelled",
        items: current.items.map((item) =>
          item.state === "pending" || item.state === "awaiting_confirmation"
            ? { ...item, state: "cancelled" }
            : item,
        ),
      };
    });
    setNotice("Mock calibration sequence cancelled.");
  };

  const actionsDisabled = !subsystem?.available || jobBusy || hasAnyDirty;

  return (
    <div className="commissioningPage">
      <div className="container-fluid px-3 py-2">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <h3 className="text-white mb-0">Motor Commissioning</h3>
          <span className="badge bg-secondary">UI mockup</span>
        </div>

        <div className="alert alert-info py-2 mb-3 commissioningPreview" role="status">
          <strong>Preview mode:</strong> no backend or rover connection. {notice}
        </div>

        <section
          className="commissioningPanel p-3 mb-3"
          aria-label="Motor selection"
        >
          <div className="row g-3 align-items-end">
            <div className="col-sm-6 col-lg-3">
              <label className="form-label" htmlFor="commissioning-subsystem">
                Subsystem
              </label>
              <select
                id="commissioning-subsystem"
                className="form-select form-select-sm"
                value={subsystemId}
                onChange={(event) => selectSubsystem(event.target.value)}
              >
                {SUBSYSTEMS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                    {item.available ? "" : " — coming later"}
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
                value={motorId}
                disabled={!subsystem?.available}
                onChange={(event) => selectMotor(event.target.value)}
              >
                {CORE_MOTORS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label} · wheel_{item.id}
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
                {subsystem?.description}
              </div>
            </div>
          </div>
        </section>

        {!subsystem?.available ? (
          <div className="alert alert-secondary">
            <h5 className="alert-heading">{subsystem?.label} commissioning is not available yet</h5>
            <p className="mb-0">
              This selector is included to preview the final navigation. It will become active when
              the subsystem provides motor IDs, configs, namespaces, and a CAN interface.
            </p>
          </div>
        ) : (
          <div className="row g-3 pb-3">
            <div className="col-xl-8">
              <section className="commissioningPanel p-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-3">
                  <h5 className="text-white mb-0">
                    {editorTab === "individual"
                      ? `${motor.label} configuration`
                      : editorTab === "shared"
                        ? "Shared motor configuration"
                        : "Soft-limit configuration"}
                  </h5>
                  <span className={`badge ${currentEditorDirty ? "text-bg-warning" : "text-bg-secondary"}`}>
                    {currentEditorDirty ? "Unsaved" : "Saved"}
                  </span>
                </div>

                <div className="nav nav-tabs commissioningTabs mb-3" role="tablist">
                  {[
                    ["individual", "Individual config"],
                    ["shared", "Shared config"],
                    ["limits", "Soft limits"],
                  ].map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      role="tab"
                      aria-selected={editorTab === id}
                      className={`nav-link ${editorTab === id ? "active" : ""}`}
                      onClick={() => selectTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div>
                  <div className="commissioningFileMeta">
                    <code>
                      {editorTab === "shared"
                        ? "kanga_core_drive/config/motors/shared_motor_config.py"
                        : editorTab === "limits"
                          ? "kanga_core_drive/config/motors/soft_limits.yaml"
                          : `kanga_core_drive/config/motors/wheel_${motor.id}_motor_config.py`}
                    </code>
                  </div>
                  <textarea
                    className="commissioningTextEditor"
                    spellCheck="false"
                    aria-label={`${editorTab} configuration`}
                    value={draftConfigs[configKey]}
                    onChange={(event) =>
                      setDraftConfigs((current) => ({
                        ...current,
                        [configKey]: event.target.value,
                      }))
                    }
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
                    onClick={restoreDefaults}
                  >
                    Restore defaults
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={!currentEditorDirty}
                    onClick={resetEditor}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={!currentEditorDirty}
                    onClick={saveEditor}
                  >
                    Save file
                  </button>
                </div>
              </section>
            </div>

            <div className="col-xl-4">
              <section className="commissioningPanel p-3 mb-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
                  <h5 className="text-white mb-0">Commission motors</h5>
                  <span className="badge text-bg-secondary">can_core</span>
                </div>

                <dl className="commissioningMotorDetails">
                  <div>
                    <dt>Selected</dt>
                    <dd>{motor.label}</dd>
                  </div>
                  <div>
                    <dt>Namespace</dt>
                    <dd>/wheel_{motor.id}</dd>
                  </div>
                  <div>
                    <dt>Node</dt>
                    <dd>{motor.nodeId}</dd>
                  </div>
                  <div>
                    <dt>Serial</dt>
                    <dd>{motor.serial}</dd>
                  </div>
                </dl>

                {hasAnyDirty ? (
                  <div className="alert alert-warning py-2 small">
                    Save or reset all editor changes before commissioning.
                  </div>
                ) : null}

                <div className="commissioningActionGroup">
                  <div className="small text-white-50 mb-2">Selected motor</div>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={actionsDisabled}
                    onClick={() => beginSave([motor.id])}
                  >
                    Save {motor.shortLabel}
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={actionsDisabled}
                    onClick={() => beginCalibration([motor.id])}
                  >
                    Calibrate {motor.shortLabel}
                  </button>
                </div>

                <hr className="border-secondary" />

                <div className="commissioningActionGroup">
                  <div className="small text-white-50 mb-2">All core motors</div>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonMuted"
                    disabled={actionsDisabled}
                    onClick={() => beginSave(CORE_MOTORS.map((item) => item.id))}
                  >
                    Save all
                  </button>
                  <button
                    type="button"
                    className="commissioningButton commissioningButtonAccent"
                    disabled={actionsDisabled}
                    onClick={() => beginCalibration(CORE_MOTORS.map((item) => item.id))}
                  >
                    Calibrate all sequentially
                  </button>
                </div>

                <p className="small text-white-50 mt-3 mb-0">
                  Calibration runs one motor at a time and requires confirmation before each motor.
                </p>
              </section>

              <section className="commissioningPanel p-3">
                <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
                  <h5 className="text-white mb-0">
                    {job
                      ? job.operation === "save"
                        ? "Save progress"
                        : "Calibration progress"
                      : "Operation progress"}
                  </h5>
                  {job ? (
                    <span className={`commissioningJobState state-${job.state}`}>
                      {STATUS_LABELS[job.state] ?? job.state}
                    </span>
                  ) : null}
                </div>

                {job ? (
                  <ol className="commissioningProgressList">
                    {job.items.map((item, index) => (
                      <li key={item.id} className={`state-${item.state}`}>
                        <span className="commissioningProgressIndex">{index + 1}</span>
                        <span>
                          <strong>{item.label}</strong>
                          <small>wheel_{item.id}</small>
                        </span>
                        <span className="commissioningProgressStatus">
                          {STATUS_LABELS[item.state]}
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="small text-white-50 mb-0">
                    Choose an action above to preview individual or sequential progress.
                  </p>
                )}
              </section>
            </div>
          </div>
        )}
      </div>

      <Modal
        show={job?.state === "awaiting_confirmation"}
        onHide={cancelCalibration}
        centered
        backdrop="static"
        keyboard={false}
        contentClassName="commissioningModal"
        backdropClassName="commissioningModalBackdrop"
      >
        <Modal.Header>
          <Modal.Title>Prepare {currentJobMotor?.label}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="alert alert-warning py-2">Motor movement will occur.</div>
          <p>
            Calibration will energize <strong>{currentJobMotor?.label}</strong>{" "}
            (<code>/wheel_{currentJobMotor?.id}</code>). Make sure it cannot contact the ground,
            tools, cables, or people.
          </p>
          {job?.items.length > 1 ? (
            <small className="commissioningSequenceHint">
              Motor {job.activeIndex + 1} of {job.items.length}. You will confirm every motor separately.
            </small>
          ) : null}
        </Modal.Body>
        <Modal.Footer>
          <button type="button" className="btn btn-sm btn-outline-light" onClick={cancelCalibration}>
            Cancel sequence
          </button>
          <button
            type="button"
            className="btn btn-sm btn-warning"
            onClick={confirmCalibration}
          >
            Confirm & calibrate
          </button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
