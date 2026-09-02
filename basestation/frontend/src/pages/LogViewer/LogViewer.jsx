import React, { useEffect, useMemo, useRef, useState } from "react";
import { getApiBase, getWsBase } from "../../config";
import {
  HTTP_LEVEL_OPTIONS,
  HTTP_LOG_INFO,
  ROS_LEVEL_OPTIONS,
  ROS_LOG_WARN,
  http_level_name,
  http_level_value,
} from "./logLevels";
import {
  buildRosNameTree,
  nameMatchesSelection,
  sortedChildNodes,
} from "./rosNameTree";
import "./LogViewer.css";

const HTTP_LINE = /^(\w+)\s+([\d\-:,\s.]+)\s+([^:]+):\s*(.*)$/;

function parseHttpLine(line) {
  const match = line.match(HTTP_LINE);
  if (!match) {
    return {
      seq: line,
      stamp: "",
      level: HTTP_LOG_INFO,
      level_name: "INFO",
      name: "uvicorn",
      msg: line,
    };
  }
  return {
    seq: line,
    stamp: match[2].trim(),
    level: http_level_value(match[1]),
    level_name: http_level_name(match[1]),
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

function formatDisplayTime(stamp) {
  if (!stamp) return "";
  try {
    const date = new Date(stamp);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    }
  } catch {
    /* keep raw */
  }
  const timePart = stamp.match(/\d{1,2}:\d{2}:\d{2}/);
  return timePart ? timePart[0] : stamp;
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

function RosNameBranch({
  nodes,
  source,
  selection,
  expanded,
  onToggle,
  onSelectExact,
  onSelectPrefix,
}) {
  return (
    <ul className="logsLeaves">
      {nodes.map((node) => {
        const childNodes = sortedChildNodes(node);
        const hasChildren = childNodes.length > 0;
        const isOpen = hasChildren && expanded.has(node.path);
        const prefixActive =
          source === "ros"
          && selection.type === "prefix"
          && selection.path === node.path;
        const exactActive =
          source === "ros"
          && selection.type === "exact"
          && selection.path === node.path;

        return (
          <li key={node.path}>
            {hasChildren ? (
              <div className="logsNsRow">
                <button
                  type="button"
                  className="logsNsToggle"
                  aria-expanded={isOpen}
                  onClick={() => onToggle(node.path)}
                >
                  {isOpen ? "▾" : "▸"}
                </button>
                <button
                  type="button"
                  className={`logsFolder logsFolder--ns${prefixActive ? " is-active" : ""}`}
                  onClick={() => onSelectPrefix(node.path)}
                  title={node.path}
                >
                  {node.label}
                </button>
              </div>
            ) : (
              <button
                type="button"
                className={`logsLeaf${exactActive ? " is-active" : ""}`}
                onClick={() => onSelectExact(node.path)}
                title={node.path}
              >
                {node.label}
              </button>
            )}
            {hasChildren && isOpen && node.hasLogger ? (
              <button
                type="button"
                className={`logsLeaf logsLeaf--nested${exactActive ? " is-active" : ""}`}
                onClick={() => onSelectExact(node.path)}
                title={node.path}
              >
                {node.label}
              </button>
            ) : null}
            {hasChildren && isOpen ? (
              <RosNameBranch
                nodes={childNodes}
                source={source}
                selection={selection}
                expanded={expanded}
                onToggle={onToggle}
                onSelectExact={onSelectExact}
                onSelectPrefix={onSelectPrefix}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
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
  const [selection, setSelection] = useState({ type: "all" });
  const [expanded, setExpanded] = useState(() => new Set());
  const [levelFloor, setLevelFloor] = useState(ROS_LOG_WARN);
  const [nameQuery, setNameQuery] = useState("");
  const [paused, setPaused] = useState(false);
  const [treeOpen, setTreeOpen] = useState(true);
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

  const rosTree = useMemo(() => {
    const names = rosRecords.map((record) => record.name).filter(Boolean);
    return buildRosNameTree(names);
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
      if (!nameMatchesSelection(record.name, selection)) return false;
      if (selection.type === "all" && nameQuery) {
        const query = nameQuery.toLowerCase();
        return (
          record.name.toLowerCase().includes(query)
          || record.msg.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [source, httpRecords, rosRecords, levelFloor, selection, nameQuery]);

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

  const selectRosAll = () => {
    setSource("ros");
    setSelection({ type: "all" });
  };

  const selectRosExact = (path) => {
    setSource("ros");
    setSelection({ type: "exact", path });
  };

  const selectRosPrefix = (path) => {
    setSource("ros");
    setSelection({ type: "prefix", path });
  };

  const toggleNs = (path) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
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
          <button
            type="button"
            className="logsButton"
            onClick={() => setTreeOpen((value) => !value)}
            aria-expanded={treeOpen}
            aria-controls="logs-source-tree"
          >
            {treeOpen ? "Hide sources" : "Show sources"}
          </button>
        </div>

        <div className={`logsLayout${treeOpen ? "" : " logsLayout--treeCollapsed"}`}>
          <nav
            id="logs-source-tree"
            className="logsTree"
            aria-label="Log sources"
            aria-hidden={!treeOpen}
          >
            <button
              type="button"
              className="logsFolder"
              onClick={() => setRosOpen((value) => !value)}
            >
              <span>ROS</span>
              <span>{rosOpen ? "▾" : "▸"}</span>
            </button>
            {rosOpen ? (
              <>
                <ul className="logsLeaves">
                  <li>
                    <button
                      type="button"
                      className={`logsLeaf${source === "ros" && selection.type === "all" ? " is-active" : ""}`}
                      onClick={selectRosAll}
                    >
                      All
                    </button>
                  </li>
                </ul>
                <RosNameBranch
                  nodes={sortedChildNodes(rosTree)}
                  source={source}
                  selection={selection}
                  expanded={expanded}
                  onToggle={toggleNs}
                  onSelectExact={selectRosExact}
                  onSelectPrefix={selectRosPrefix}
                />
              </>
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
                      setSelection({ type: "all" });
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
                    {(source === "http" ? HTTP_LEVEL_OPTIONS : ROS_LEVEL_OPTIONS).map(
                      ([label, value]) => (
                        <option key={label} value={value}>
                          {label}+
                        </option>
                      ),
                    )}
                  </select>
                  {source === "ros" && selection.type === "all" ? (
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
                        <span className="logsTime text-white-50" title={formatStamp(record.stamp)}>
                          {formatDisplayTime(record.stamp)}
                        </span>
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
