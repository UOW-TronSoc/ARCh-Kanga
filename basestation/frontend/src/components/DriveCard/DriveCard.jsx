import React, { useState } from "react";
import Modal from "react-bootstrap/Modal";
import { getApiBase } from "../../config";
import styles from "./DriveCard.module.css";

async function driveAction(path, body) {
  const opts = body === undefined
    ? { method: "POST", credentials: "same-origin" }
    : {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      };
  const res = await fetch(`${getApiBase()}${path}`, opts);
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (typeof data.ok !== "boolean") {
    return {
      ok: res.ok,
      message: data.message || data.detail || `Request failed (${res.status})`,
    };
  }
  return data;
}

export default function DriveCard({
  drivestop,
  whsOnline,
  closedLoop,
  enabled,
  setEnabled,
  controllerInfo,
  speedScale,
  setSpeedScale,
  linkState,
}) {
  const [feedback, setFeedback] = useState("");
  const [feedbackErr, setFeedbackErr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showDrivestopConfirm, setShowDrivestopConfirm] = useState(false);

  const isStopped = drivestop === true;
  const whsReachable = whsOnline || drivestop !== null;

  const showFeedback = (text, isError) => {
    setFeedback(text);
    setFeedbackErr(isError);
  };

  const run = async ({ guard, path, body, successMsg, failMsg }) => {
    if (guard) {
      showFeedback(guard, true);
      return;
    }
    setBusy(true);
    setFeedback("");
    try {
      const data = await driveAction(path, body);
      if (data.ok) {
        showFeedback(successMsg || data.message || "Done.", false);
      } else {
        showFeedback(data.message || failMsg || "That action failed.", true);
      }
    } catch {
      showFeedback(failMsg || "That action failed.", true);
    } finally {
      setBusy(false);
    }
  };

  const toggleDrivestop = () => {
    if (!whsReachable) {
      showFeedback("WHS is offline — drivestop cannot be changed.", true);
      return;
    }
    if (isStopped) {
      setShowDrivestopConfirm(true);
      return;
    }
    run({
      path: "/drive/drivestop",
      body: { stop: true },
      successMsg: "Drivestop asserted — drive is stopped.",
      failMsg: "Could not assert drivestop.",
    });
    setEnabled(false);
  };

  const confirmReleaseDrivestop = () => {
    setShowDrivestopConfirm(false);
    run({
      path: "/drive/drivestop",
      body: { stop: false },
      successMsg: "Drivestop released — you can enter closed loop.",
      failMsg: "Could not release drivestop.",
    });
  };

  const toggleClosedLoop = () => {
    const wantClosed = !closedLoop;

    if (!whsReachable) {
      showFeedback("WHS is offline — drive mode cannot be changed.", true);
      return;
    }
    if (wantClosed && isStopped) {
      showFeedback(
        "Cannot enter closed loop while drivestop is active — release stop first.",
        true,
      );
      return;
    }

    run({
      path: "/drive/closed-loop",
      body: { enable: wantClosed },
      successMsg: wantClosed ? "Motors in closed loop." : "Motors idle.",
      failMsg: wantClosed
        ? "Could not enter closed loop."
        : "Could not return motors to idle.",
    });
  };

  const clearFaults = () => {
    run({
      path: "/drive/clear-errors",
      successMsg: "Drive faults cleared.",
      failMsg: "Could not clear drive faults.",
    });
  };

  return (
    <div className={`card h-100 ${styles.card}`}>
      <h5 className={styles.title}>Drive</h5>

      <div className={styles.actions}>
        <button
          type="button"
          className={enabled ? styles.btnClear : styles.btnMuted}
          onClick={() => setEnabled(!enabled)}
        >
          Drive Input: {enabled ? "Enabled" : "Disabled"}
        </button>

        <div className={styles.speedSection}>
          <label htmlFor="speedScale" className="form-label small mb-1">
            Speed max: {speedScale}%
          </label>
          <input
            id="speedScale"
            type="range"
            className="form-range"
            min="0"
            max="100"
            value={speedScale}
            onChange={(e) => setSpeedScale(Number(e.target.value))}
          />
          <div className="small text-secondary">
            Control: {linkState === "connected" ? "connected" : linkState}
          </div>
        </div>

        <button
          type="button"
          className={isStopped ? styles.btnDanger : styles.btnClear}
          disabled={busy || !whsReachable}
          onClick={toggleDrivestop}
        >
          Drivestop: {isStopped ? "Enabled" : "Disabled"}
        </button>

        <button
          type="button"
          className={closedLoop ? styles.btnClosedLoop : styles.btnIdle}
          disabled={busy || !whsReachable || isStopped}
          onClick={toggleClosedLoop}
        >
          Odrive State: {closedLoop ? "Closed Loop" : "Idle"}
        </button>

        <button
          type="button"
          className={styles.btnMuted}
          disabled={busy}
          onClick={clearFaults}
        >
          Clear faults
        </button>
      </div>

      <div className={styles.deviceInfo}>
        <div>
          <strong>Active device:</strong> {controllerInfo?.name ?? "None"}
        </div>
        <div className="small text-muted">
          B0 drive input · B12 forward · B13 back · B14 rotate left · B15 rotate right
        </div>
        {controllerInfo?.type === "logitech-extreme-3d" &&
          typeof controllerInfo?.throttle === "number" && (
            <div className="small text-muted">
              Throttle: {Math.round(controllerInfo.throttle * 100)}%
            </div>
          )}
      </div>

      {feedback ? (
        <div className={`${styles.feedback} ${feedbackErr ? styles.feedbackErr : styles.feedbackOk}`}>
          {feedback}
        </div>
      ) : null}

      <Modal
        show={showDrivestopConfirm}
        onHide={() => setShowDrivestopConfirm(false)}
        centered
        contentClassName={styles.modalContent}
        backdropClassName={styles.modalBackdrop}
      >
        <Modal.Header closeButton className={styles.modalHeader}>
          <Modal.Title className={styles.modalTitle}>Release drivestop?</Modal.Title>
        </Modal.Header>
        <Modal.Body className={styles.modalBody}>
          This allows the rover to enter closed loop and accept drive commands.
          Only continue if you intend to drive.
        </Modal.Body>
        <Modal.Footer className={styles.modalFooter}>
          <button
            type="button"
            className={styles.modalBtnCancel}
            onClick={() => setShowDrivestopConfirm(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className={styles.modalBtnConfirm}
            onClick={confirmReleaseDrivestop}
            disabled={busy}
          >
            Release drivestop
          </button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
