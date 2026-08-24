import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import "./Dashboard.css";

import CameraPlaceholder from "components/CameraPlaceholder/CameraPlaceholder";
import DataDisplayCard from "components/DataDisplayCard/DataDisplayCard";
import DriveCard from "components/DriveCard/DriveCard";
import { useBattery } from "context/BatteryContext";
import { useControlWebSocket } from "hooks/useControlWebSocket";
import { useTelemetryWebSocket } from "hooks/useTelemetryWebSocket";
import { getApiBase } from "../../config";

const EPSILON = 0.01;
const MAX_TWIST = 20;
const CONTROL_KEYS = new Set(["w", "s", "a", "d", "q", "e"]);
const ZERO_VECTOR = { x: 0, y: 0, z: 0 };

const BUTTON_DRIVE_INPUT = 0;
const BUTTON_FULL_FORWARD = 12;
const BUTTON_FULL_BACKWARD = 13;
const BUTTON_FULL_ROTATE_LEFT = 14;
const BUTTON_FULL_ROTATE_RIGHT = 15;

const isButtonPressed = (gamepad, index) => Boolean(gamepad.buttons[index]?.pressed);

async function driveApi(path, body) {
  const res = await fetch(`${getApiBase()}${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  return data.ok === true;
}

const waitForTelemetry = (predicate, timeoutMs = 4000, intervalMs = 100) =>
  new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    const tick = () => {
      if (predicate()) {
        resolve(true);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(false);
        return;
      }
      setTimeout(tick, intervalMs);
    };
    tick();
  });

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
  const prevButtonsRef = useRef([]);
  const armBusyRef = useRef(false);
  const driveEnabledRef = useRef(driveEnabled);
  const drivestopRef = useRef(telemetry.drivestop);
  const closedLoopRef = useRef(telemetry.closed_loop);
  driveEnabledRef.current = driveEnabled;
  drivestopRef.current = telemetry.drivestop;
  closedLoopRef.current = telemetry.closed_loop;

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

  const toggleDriveInputArm = useCallback(async () => {
    if (driveEnabledRef.current) {
      setDriveEnabled(false);
      return;
    }

    if (drivestopRef.current === true) {
      return;
    }

    if (!closedLoopRef.current) {
      const armed = await driveApi("/drive/closed-loop", { enable: true });
      if (!armed) return;
      const closedLoopReady = await waitForTelemetry(() => closedLoopRef.current === true);
      if (!closedLoopReady) return;
    }

    setDriveEnabled(true);
  }, []);

  const requestDriveInputArm = useCallback(() => {
    if (armBusyRef.current) return;
    armBusyRef.current = true;
    toggleDriveInputArm().finally(() => {
      armBusyRef.current = false;
    });
  }, [toggleDriveInputArm]);

  useEffect(() => {
    document.title = "Drive";
  }, []);

  useEffect(() => {
    if (telemetry.drivestop === true) {
      setDriveEnabled(false);
    }
  }, [telemetry.drivestop]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.code === "Space" || event.key === " ") {
        event.preventDefault();
        if (event.repeat) return;
        requestDriveInputArm();
        return;
      }

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
      if (event.code === "Space" || event.key === " ") {
        event.preventDefault();
        return;
      }

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
  }, [recalcKeyboardTwist, requestDriveInputArm]);

  useEffect(() => {
    const pollGamepad = () => {
      const gp = navigator.getGamepads()[0];
      if (!gp) {
        prevButtonsRef.current = [];
        setGamepadLinear((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        setGamepadAngular((prev) => (vectorsAlmostEqual(prev, ZERO_VECTOR) ? prev : { ...ZERO_VECTOR }));
        updateControllerInfo({ name: "None", type: null, throttle: null });
        return;
      }

      const prevPressed = prevButtonsRef.current;
      const driveInputPressed = isButtonPressed(gp, BUTTON_DRIVE_INPUT);
      if (prevPressed.length > 0 && driveInputPressed && !prevPressed[BUTTON_DRIVE_INPUT]) {
        requestDriveInputArm();
      }
      prevButtonsRef.current = gp.buttons.map((button) => Boolean(button?.pressed));

      const controllerType = identifyControllerType(gp.id);
      if (!driveEnabledRef.current) {
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

      const fullForward = isButtonPressed(gp, BUTTON_FULL_FORWARD);
      const fullBackward = isButtonPressed(gp, BUTTON_FULL_BACKWARD);
      const fullRotateLeft = isButtonPressed(gp, BUTTON_FULL_ROTATE_LEFT);
      const fullRotateRight = isButtonPressed(gp, BUTTON_FULL_ROTATE_RIGHT);
      if (fullForward !== fullBackward) {
        nextLinear.x = fullForward ? baseScale : -baseScale;
      }
      if (fullRotateLeft !== fullRotateRight) {
        nextAngular.z = fullRotateLeft ? baseScale : -baseScale;
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
  }, [requestDriveInputArm, updateControllerInfo]);

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
