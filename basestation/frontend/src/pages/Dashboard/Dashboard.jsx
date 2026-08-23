import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import "./Dashboard.css";

import CameraPlaceholder from "components/CameraPlaceholder/CameraPlaceholder";
import DataDisplayCard from "components/DataDisplayCard/DataDisplayCard";
import DriveCard from "components/DriveCard/DriveCard";
import { useBattery } from "context/BatteryContext";
import { useControlWebSocket } from "hooks/useControlWebSocket";
import { useTelemetryWebSocket } from "hooks/useTelemetryWebSocket";

const EPSILON = 0.01;
const MAX_TWIST = 20;
const CONTROL_KEYS = new Set(["w", "s", "a", "d", "q", "e"]);
const ZERO_VECTOR = { x: 0, y: 0, z: 0 };

const vectorsAlmostEqual = (a, b, epsilon = EPSILON) =>
  Math.abs(a.x - b.x) < epsilon &&
  Math.abs(a.y - b.y) < epsilon &&
  Math.abs(a.z - b.z) < epsilon;

const applyAxisDeadzone = (value, deadzone = 0.3) => {
  const v = typeof value === "number" ? value : 0;
  const a = Math.abs(v);
  if (a < deadzone) return 0;
  return Math.sign(v) * (a - deadzone) / (1 - deadzone);
};

const identifyControllerType = (id = "") => {
  const lower = id.toLowerCase();
  if (lower.includes("046d") && lower.includes("c215")) return "logitech-extreme-3d";
  if (lower.includes("logitech") && lower.includes("extreme") && lower.includes("3d")) {
    return "logitech-extreme-3d";
  }
  return "generic-gamepad";
};

export default function Dashboard() {
  const batteryInfo = useBattery();
  const telemetry = useTelemetryWebSocket();

  const [driveEnabled, setDriveEnabled] = useState(false);
  const [speedScale, setSpeedScale] = useState(20);

  const [keyboardLinear, setKeyboardLinear] = useState({ ...ZERO_VECTOR });
  const [keyboardAngular, setKeyboardAngular] = useState({ ...ZERO_VECTOR });
  const [gamepadLinear, setGamepadLinear] = useState({ ...ZERO_VECTOR });
  const [gamepadAngular, setGamepadAngular] = useState({ ...ZERO_VECTOR });
  const [controllerInfo, setControllerInfo] = useState({
    name: "None",
    type: null,
    throttle: null,
  });

  const pressedKeysRef = useRef(new Set());

  const recalcKeyboardTwist = useCallback(() => {
    const scale = MAX_TWIST;
    const keys = pressedKeysRef.current;
    const nextLinear = { ...ZERO_VECTOR };
    const nextAngular = { ...ZERO_VECTOR };

    if (keys.has("w")) nextLinear.x += scale;
    if (keys.has("s")) nextLinear.x -= scale;
    if (keys.has("q")) nextLinear.y += scale;
    if (keys.has("e")) nextLinear.y -= scale;
    if (keys.has("a")) nextAngular.z += scale;
    if (keys.has("d")) nextAngular.z -= scale;

    setKeyboardLinear((prev) => (vectorsAlmostEqual(prev, nextLinear) ? prev : nextLinear));
    setKeyboardAngular((prev) => (vectorsAlmostEqual(prev, nextAngular) ? prev : nextAngular));
  }, []);

  const updateControllerInfo = useCallback((info) => {
    setControllerInfo((prev) => {
      if (
        prev.name === info.name &&
        prev.type === info.type &&
        (prev.throttle ?? null) === (info.throttle ?? null)
      ) {
        return prev;
      }
      return info;
    });
  }, []);

  useEffect(() => {
    document.title = "Drive";
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      const key = event.key.toLowerCase();
      if (!CONTROL_KEYS.has(key)) return;
      event.preventDefault();
      const keys = pressedKeysRef.current;
      if (!keys.has(key)) {
        keys.add(key);
        recalcKeyboardTwist();
      }
    };
    const handleKeyUp = (event) => {
      const key = event.key.toLowerCase();
      if (!CONTROL_KEYS.has(key)) return;
      event.preventDefault();
      const keys = pressedKeysRef.current;
      if (keys.delete(key)) recalcKeyboardTwist();
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [recalcKeyboardTwist]);

  useEffect(() => {
    const pollGamepad = () => {
      const gp = navigator.getGamepads()[0];
      if (!gp) {
        setGamepadLinear((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        setGamepadAngular((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        updateControllerInfo({ name: "None", type: null, throttle: null });
        return;
      }

      const controllerType = identifyControllerType(gp.id);
      if (!driveEnabled) {
        updateControllerInfo({ name: gp.id || "Unknown Controller", type: controllerType, throttle: 0 });
        setGamepadLinear((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        setGamepadAngular((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        return;
      }

      const baseScale = MAX_TWIST;
      let throttle = 1;
      let nextLinear = { ...ZERO_VECTOR };
      let nextAngular = { ...ZERO_VECTOR };

      if (controllerType === "logitech-extreme-3d") {
        const throttleAxis = gp.axes[3] ?? -1;
        throttle = Math.min(Math.max((1 - throttleAxis) / 2, 0), 1);
        const scale = baseScale * throttle;
        nextLinear = {
          x: applyAxisDeadzone(-(gp.axes[1] ?? 0), 0.3) * scale,
          y: applyAxisDeadzone(gp.axes[0] ?? 0, 0.3) * scale,
          z: 0,
        };
        nextAngular = {
          x: 0,
          y: 0,
          z: applyAxisDeadzone(gp.axes[2] ?? 0, 0.3) * scale,
        };
      } else {
        const scale = baseScale;
        nextLinear = {
          x: applyAxisDeadzone(-(gp.axes[1] ?? 0), 0.3) * scale,
          y: applyAxisDeadzone(gp.axes[0] ?? 0, 0.3) * scale,
          z: 0,
        };
        nextAngular = {
          x: 0,
          y: 0,
          z: applyAxisDeadzone(-(gp.axes[2] ?? gp.axes[3] ?? 0), 0.3) * scale,
        };
      }

      updateControllerInfo({
        name: gp.id || "Unknown Controller",
        type: controllerType,
        throttle,
      });
      setGamepadLinear((prev) => (vectorsAlmostEqual(prev, nextLinear) ? prev : nextLinear));
      setGamepadAngular((prev) => (vectorsAlmostEqual(prev, nextAngular) ? prev : nextAngular));
    };

    const interval = setInterval(pollGamepad, 50);
    return () => clearInterval(interval);
  }, [driveEnabled, updateControllerInfo]);

  const combinedLinear = useMemo(
    () => ({
      x: keyboardLinear.x + gamepadLinear.x,
      y: keyboardLinear.y + gamepadLinear.y,
      z: keyboardLinear.z + gamepadLinear.z,
    }),
    [keyboardLinear, gamepadLinear]
  );

  const combinedAngular = useMemo(
    () => ({
      x: keyboardAngular.x + gamepadAngular.x,
      y: keyboardAngular.y + gamepadAngular.y,
      z: keyboardAngular.z + gamepadAngular.z,
    }),
    [keyboardAngular, gamepadAngular]
  );

  const effectiveTwist = useMemo(
    () => (
      driveEnabled
        ? { linear: { ...combinedLinear }, angular: { ...combinedAngular } }
        : { linear: { ...ZERO_VECTOR }, angular: { ...ZERO_VECTOR } }
    ),
    [combinedLinear, combinedAngular, driveEnabled]
  );

  const getWsCommand = useCallback(() => {
    const x = Math.max(-1, Math.min(1, effectiveTwist.linear.x / MAX_TWIST));
    const yaw = Math.max(-1, Math.min(1, effectiveTwist.angular.z / MAX_TWIST));
    return { x, yaw, scale: speedScale };
  }, [effectiveTwist, speedScale]);

  const onControlConnect = useCallback(() => {
    setDriveEnabled(false);
  }, []);

  const { linkState, bumped, retakeControl } = useControlWebSocket({
    enabled: driveEnabled,
    getCommand: getWsCommand,
    onConnect: onControlConnect,
  });

  return (
    <div className="dashboardPage">
      <div className="container-fluid px-3">
        {(linkState === "bumped" || linkState === "reconnecting") && (
          <div className="alert alert-warning py-2 mb-2 d-flex justify-content-between align-items-center">
            <span>
              {bumped
                ? "Another tab took drive control."
                : "Control link reconnecting…"}
            </span>
            {bumped && (
              <button type="button" className="btn btn-sm btn-warning" onClick={retakeControl}>
                Take control back
              </button>
            )}
          </div>
        )}

        <div className="row dashboardRow1 gx-2 gy-1">
          <div className="col-lg-8">
            <CameraPlaceholder label="Primary camera" />
          </div>
          <div className="col-lg-4">
            <DataDisplayCard
              battery={batteryInfo}
              telemetry={telemetry}
              linkLatencyMs={null}
              linkClientIp={null}
            />
          </div>
        </div>

        <div className="row dashboardRow2 gx-2 gy-1 mt-1 pb-2">
          <div className="col-lg-4">
            <CameraPlaceholder label="Secondary camera" />
          </div>
          <div className="col-lg-4">
            <CameraPlaceholder label="Tertiary camera" />
          </div>
          <div className="col-lg-4">
            <DriveCard
              drivestop={telemetry.drivestop}
              whsOnline={telemetry.whs_online}
              closedLoop={telemetry.closed_loop}
              enabled={driveEnabled}
              setEnabled={setDriveEnabled}
              controllerInfo={controllerInfo}
              speedScale={speedScale}
              setSpeedScale={setSpeedScale}
              linkState={linkState}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
