import React, { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import logo from "assets/logo.png";
import "./MainNavbar.css";
import { getBackendBase } from "../../config";
import { useBattery } from "context/BatteryContext";

const navLinkClass = ({ isActive }) =>
  `nav-link${isActive ? " active" : ""}`;

export default function MainNavbar() {
  const [backendConnected, setBackendConnected] = useState(null);
  const batteryInfo = useBattery();

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const ctrl = new AbortController();
        const id = setTimeout(() => ctrl.abort(), 3000);
        const r = await fetch(`${getBackendBase()}/api/status/`, {
          credentials: "include",
          signal: ctrl.signal,
        });
        clearTimeout(id);
        setBackendConnected(r.ok && r.status < 500);
      } catch {
        setBackendConnected(false);
      }
    };
    checkBackend();
    const timer = setInterval(checkBackend, 5000);
    return () => clearInterval(timer);
  }, []);

  const activeFaults = Array.isArray(batteryInfo.fault_bits)
    ? batteryInfo.fault_bits
        .map((bit, idx) => (bit ? idx : null))
        .filter((v) => v !== null)
    : [];

  const batteryTooltip =
    "Battery telemetry not connected yet.\n" +
    `Display: ${batteryInfo.charge_pct}%\n` +
    (activeFaults.length ? `Faults: ${activeFaults.join(", ")}` : "Faults: OK");

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-dark sticky-top floating-navbar">
      <div className="container-fluid">
        <a className="navbar-brand d-flex align-items-center" href="/">
          <span
            className={`backend-dot ${backendConnected === true ? "backend-dot--connected" : backendConnected === false ? "backend-dot--disconnected" : "backend-dot--unknown"}`}
            title={backendConnected === true ? "Basestation connected" : backendConnected === false ? "Basestation not reachable" : "Checking…"}
            aria-label={backendConnected === true ? "Backend connected" : backendConnected === false ? "Backend disconnected" : "Checking connection"}
          />
          <img
            src={logo}
            alt="TronSoc"
            height="40"
            className="navbar-logo ms-2 me-2"
          />
          <span className="navbar-brand-text">Kanga Basestation</span>
        </a>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#mainNav"
          aria-controls="mainNav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon" />
        </button>
        <div className="collapse navbar-collapse" id="mainNav">
          <ul className="navbar-nav ms-auto mb-2 mb-lg-0 align-items-lg-center flex-column flex-lg-row">
            <li className="nav-item me-lg-3 mb-2 mb-lg-0">
              <div className="battery-wrapper" title={batteryTooltip}>
                <div className="battery">
                  <div
                    className={
                      "battery-level " +
                      (batteryInfo.charge_pct > 50
                        ? "battery-green"
                        : batteryInfo.charge_pct > 20
                        ? "battery-yellow"
                        : "battery-red")
                    }
                    style={{ width: `${batteryInfo.charge_pct}%` }}
                  />
                </div>
                <small className="text-light ms-2">{batteryInfo.charge_pct}%</small>
              </div>
            </li>
            <li className="nav-item">
              <NavLink className={navLinkClass} end to="/">
                Drive
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink className={navLinkClass} to="/commissioning">
                Commissioning
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink className={navLinkClass} to="/logs">
                Logs
              </NavLink>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
}
