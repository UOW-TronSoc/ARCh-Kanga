import React, { useEffect, useMemo, useRef, useState } from "react";
import { getApiBase, getWsBase } from "../../config";
import { ROS_LOG_INFO, ROS_LOG_WARN, http_level_value } from "./logLevels";
import "./LogViewer.css";

const LEVELS = [
  ["DEBUG", 10],
  ["INFO", 20],
  ["WARN", 30],
  ["ERROR", 40],
  ["FATAL", 50],
];

const HTTP_LINE = /^(\w+)\s+([\d\-:,\s.]+)\s+([^:]+):\s*(.*)$/;

function parseHttpLine(line) {
  const match = line.match(HTTP_LINE);
  if (!match) {
    return {
      seq: line,
      stamp: "",
      level: ROS_LOG_INFO,
      level_name: "INFO",
      name: "uvicorn",
      msg: line,
    };
  }
  const levelName = match[1].toUpperCase() === "WARNING" ? "WARN" : match[1].toUpperCase();
  return {
    seq: line,
    stamp: match[2].trim(),
    level: http_level_value(match[1]),
    level_name: levelName === "CRITICAL" ? "FATAL" : levelName,
    name: match[3].trim(),
    msg: match[4],
  };
}

function formatStamp(stamp) {
  if (!stamp) return "";
  try {
    const date = new Date(stamp);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString();
  } catch {
    /* keep raw */
  }
  return stamp;
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function stampForFilename() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return (
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-` +
    `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  );
}

export default function LogViewer() {
  const [rosOpen, setRosOpen] = useState(true);
  const [httpOpen, setHttpOpen] = useState(true);
  const [source, setSource] = useState("ros");
  const [leaf, setLeaf] = useState("all");
  const [levelFloor, setLevelFloor] = useState(ROS_LOG_WARN);
  const [nameQuery, setNameQuery] = useState("");
  const [paused, setPaused] = useState(false);
  const [rosRecords, setRosRecords] = useState([]);
  const [httpLines, setHttpLines] = useState([]);
  const [connected, setConnected] = useState(false);
  const pausedRef = useRef(false);
  const pendingRef = useRef([]);
  const streamRef = useRef(null);
  const stickToBottomRef = useRef(true);
  pausedRef.current = paused;

  useEffect(() => {
    if (source !== "ros") {
      setConnected(false);
      return undefined;
    }
    let alive = true;
    const ws = new WebSocket(`${getWsBase()}/ws/logs`);
    ws.onopen = () => {
      if (alive) setConnected(true);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.t === "snapshot" && Array.isArray(data.records)) {
          if (!pausedRef.current) setRosRecords(data.records);
          return;
        }
        if (data.t === "records" && Array.isArray(data.records)) {
          if (pausedRef.current) return;
          pendingRef.current.push(...data.records);
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      if (alive) setConnected(false);
    };
    return () => {
      alive = false;
      ws.close();
    };
  }, [source]);

  useEffect(() => {
    if (source !== "ros") return undefined;
    const timer = setInterval(() => {
      if (pausedRef.current || pendingRef.current.length === 0) return;
      const batch = pendingRef.current;
      pendingRef.current = [];
      setRosRecords((current) => {
        const merged = [...current, ...batch];
        return merged.length > 4000 ? merged.slice(merged.length - 4000) : merged;
      });
    }, 150);
    return () => clearInterval(timer);
  }, [source]);

  useEffect(() => {
    if (source !== "http") return undefined;
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`${getApiBase()}/django-logs/`, {
          credentials: "same-origin",
        });
        const body = await response.json();
        if (!cancelled && !pausedRef.current) {
          setHttpLines(Array.isArray(body.lines) ? body.lines : []);
        }
      } catch {
        /* keep last good buffer */
      }
    };
    load();
    const timer = setInterval(load, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [source]);

  const rosNames = useMemo(() => {
    const names = new Set(rosRecords.map((record) => record.name).filter(Boolean));
    return [...names].sort();
  }, [rosRecords]);

  const httpRecords = useMemo(
    () => httpLines.map(parseHttpLine),
    [httpLines],
  );

  const visible = useMemo(() => {
    if (source === "http") {
      return httpRecords.filter((record) => record.level >= levelFloor);
    }
    if (source !== "ros") return [];
    return rosRecords.filter((record) => {
      if (record.level < levelFloor) return false;
      if (leaf !== "all" && record.name !== leaf) return false;
      if (leaf === "all" && nameQuery) {
        const query = nameQuery.toLowerCase();
        return (
          record.name.toLowerCase().includes(query)
          || record.msg.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [source, httpRecords, rosRecords, levelFloor, leaf, nameQuery]);

  useEffect(() => {
    const node = streamRef.current;
    if (!node || !stickToBottomRef.current) return;
    node.scrollTop = node.scrollHeight;
  }, [visible]);

  const onStreamScroll = () => {
    const node = streamRef.current;
    if (!node) return;
    stickToBottomRef.current =
      node.scrollHeight - node.scrollTop - node.clientHeight < 40;
  };

  const selectRos = (nextLeaf) => {
    setSource("ros");
    setLeaf(nextLeaf);
  };

  const saveVisible = () => {
    const lines = visible.map(
      (record) =>
        `${record.stamp || "-"} ${record.level_name} ${record.name} ${record.msg}`,
    );
    const kind = source === "http" ? "http" : "ros";
    downloadText(`kanga-logs-${kind}-${stampForFilename()}.txt`, `${lines.join("\n")}\n`);
  };

  const stubSelected = source === "docker" || source === "stdout";

  return (
    <div className="logsPage">
      <div className="container-fluid px-3 py-2 d-flex flex-column flex-grow-1">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <div>
            <h3 className="text-white mb-1">Logs</h3>
            <p className="small text-white-50 mb-0">
              Choose a source in the tree. ROS is live `/rosout`; HTTP is the
              basestation uvicorn buffer.
            </p>
          </div>
        </div>

        <div className="logsLayout">
          <nav className="logsTree" aria-label="Log sources">
            <button
              type="button"
              className="logsFolder"
              onClick={() => setRosOpen((value) => !value)}
            >
              <span>ROS</span>
              <span>{rosOpen ? "▾" : "▸"}</span>
            </button>
            {rosOpen ? (
              <ul className="logsLeaves">
                <li>
                  <button
                    type="button"
                    className={`logsLeaf${source === "ros" && leaf === "all" ? " is-active" : ""}`}
                    onClick={() => selectRos("all")}
                  >
                    All
                  </button>
                </li>
                {rosNames.map((name) => (
                  <li key={name}>
                    <button
                      type="button"
                      className={`logsLeaf${source === "ros" && leaf === name ? " is-active" : ""}`}
                      onClick={() => selectRos(name)}
                    >
                      {name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            <button
              type="button"
              className="logsFolder"
              onClick={() => setHttpOpen((value) => !value)}
            >
              <span>HTTP</span>
              <span>{httpOpen ? "▾" : "▸"}</span>
            </button>
            {httpOpen ? (
              <ul className="logsLeaves">
                <li>
                  <button
                    type="button"
                    className={`logsLeaf${source === "http" ? " is-active" : ""}`}
                    onClick={() => {
                      setSource("http");
                      setLeaf("uvicorn");
                    }}
                  >
                    uvicorn
                  </button>
                </li>
              </ul>
            ) : null}

            <button type="button" className="logsFolder" disabled>
              <span>Docker</span>
              <span>later</span>
            </button>
            <button type="button" className="logsFolder" disabled>
              <span>Launch stdout</span>
              <span>later</span>
            </button>
          </nav>

          <section className="logsPane" aria-label="Log stream">
            {stubSelected ? (
              <p className="logsStub mb-0">This source is not wired yet.</p>
            ) : (
              <>
                <div className="logsToolbar">
                  <label htmlFor="logs-level">Level</label>
                  <select
                    id="logs-level"
                    value={levelFloor}
                    onChange={(event) => setLevelFloor(Number(event.target.value))}
                  >
                    {LEVELS.map(([label, value]) => (
                      <option key={label} value={value}>
                        {label}+
                      </option>
                    ))}
                  </select>
                  {source === "ros" && leaf === "all" ? (
                    <input
                      type="search"
                      placeholder="Filter name or message"
                      value={nameQuery}
                      onChange={(event) => setNameQuery(event.target.value)}
                    />
                  ) : null}
                  <button
                    type="button"
                    className="logsButton"
                    onClick={() => setPaused((value) => !value)}
                  >
                    {paused ? "Resume" : "Pause"}
                  </button>
                  <button type="button" className="logsButton" onClick={saveVisible}>
                    Save
                  </button>
                  <span className="small text-white-50">
                    {source === "ros"
                      ? (connected ? "Live" : "Connecting…")
                      : "HTTP poll"}
                    {` · ${visible.length} lines`}
                  </span>
                </div>
                <div
                  className="logsStream"
                  ref={streamRef}
                  onScroll={onStreamScroll}
                >
                  {visible.length === 0 ? (
                    <div className="logsEmpty">No log lines in this view.</div>
                  ) : (
                    visible.map((record, index) => (
                      <div className="logsRow" key={`${record.seq}-${index}`}>
                        <span className="text-white-50">{formatStamp(record.stamp)}</span>
                        <span className={`logsLevel logsLevel--${record.level_name}`}>
                          {record.level_name}
                        </span>
                        <span className="logsName" title={record.name}>{record.name}</span>
                        <span className="logsMsg">{record.msg}</span>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
