import React from "react";
import styles from "./CameraPlaceholder.module.css";

export default function CameraPlaceholder({ label = "Camera feed" }) {
  return (
    <div className={`card bg-transparent rounded-3 p-0 ${styles.card}`}>
      <div className="ratio ratio-16x9 overflow-hidden rounded-3">
        <div className={styles.placeholder}>
          <div className={styles.title}>{label}</div>
          <p className={styles.hint}>
            Live video arrives in Phase 2 (MediaMTX / WebRTC). Drive and
            telemetry work without cameras.
          </p>
        </div>
      </div>
    </div>
  );
}
