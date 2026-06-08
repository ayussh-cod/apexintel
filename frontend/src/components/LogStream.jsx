import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const LEVEL_STYLE = {
  info:    { color: "#7c9fff", prefix: "ℹ" },
  success: { color: "#3dffa0", prefix: "✓" },
  error:   { color: "#ff5c5c", prefix: "✕" },
  done:    { color: "#ffd166", prefix: "★" },
  close:   null,
};

export default function LogStream({ job, onViewNotes, onBack }) {
  const [logs, setLogs]         = useState([]);
  const [status, setStatus]     = useState(job.status);
  const [phoenixUrl, setPhoenix] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef  = useRef(null);
  const esRef      = useRef(null);

  // Poll job status
  useEffect(() => {
    const poll = async () => {
      const data = await api.getJob(job.id).catch(() => null);
      if (data) {
        setStatus(data.status);
        if (data.phoenix_url) setPhoenix(data.phoenix_url);
      }
    };
    poll();
    const t = setInterval(poll, 3000);
    return () => clearInterval(t);
  }, [job.id]);

  // SSE stream
  useEffect(() => {
    const es = new EventSource(`/api/stream/${job.id}`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed.level === "close" || parsed.level === "done") {
          es.close();
          return;
        }
        setLogs(prev => [...prev, parsed]);
      } catch {}
    };

    es.onerror = () => es.close();
    return () => es.close();
  }, [job.id]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const isDone   = status === "completed";
  const isFailed = status === "failed";
  const isRunning = status === "running" || status === "pending";

  return (
    <div className="log-panel">
      {/* Header */}
      <div className="log-header">
        <div className="log-header-left">
          <button className="back-btn" onClick={onBack}>← Back</button>
          <div className="log-title-block">
            <h2 className="log-title">{job.field}</h2>
            <div className="log-job-id">job: {job.id.slice(0, 8)}…</div>
          </div>
        </div>
        <div className="log-header-right">
          <StatusBadge status={status} />
          {phoenixUrl && (
            <a className="phoenix-btn" href={phoenixUrl} target="_blank" rel="noreferrer">
              <span className="phoenix-dot" />
              Phoenix Traces ↗
            </a>
          )}
          {isDone && (
            <button className="btn-notes" onClick={onViewNotes}>
              View Notes →
            </button>
          )}
        </div>
      </div>

      {/* Terminal */}
      <div className="terminal" onScroll={e => {
        const el = e.currentTarget;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        setAutoScroll(atBottom);
      }}>
        <div className="terminal-topbar">
          <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
          <span className="terminal-title">pipeline output — {job.field}</span>
          <label className="autoscroll-toggle">
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            auto-scroll
          </label>
        </div>

        <div className="log-lines">
          {logs.length === 0 && isRunning && (
            <div className="log-waiting">
              <span className="waiting-spinner" /> Waiting for pipeline to start…
            </div>
          )}
          {logs.map((log, i) => {
            const meta = LEVEL_STYLE[log.level] || LEVEL_STYLE.info;
            return (
              <div key={i} className="log-line">
                <span className="log-ts">{log.ts?.slice(11, 19)}</span>
                <span className="log-prefix" style={{ color: meta.color }}>{meta.prefix}</span>
                <span className="log-msg" style={{ color: log.level === "error" ? "#ff5c5c" : undefined }}>
                  {log.msg}
                </span>
              </div>
            );
          })}
          {isRunning && logs.length > 0 && (
            <div className="log-line">
              <span className="cursor-blink">█</span>
            </div>
          )}
          {isDone && (
            <div className="log-line done-line">
              <span className="log-prefix" style={{ color: "#ffd166" }}>★</span>
              <span>Pipeline complete</span>
            </div>
          )}
          {isFailed && (
            <div className="log-line">
              <span className="log-prefix" style={{ color: "#ff5c5c" }}>✕</span>
              <span style={{ color: "#ff5c5c" }}>Pipeline failed</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Stats bar */}
      <div className="log-footer">
        <span>{logs.length} log lines</span>
        {isDone && <span className="footer-ok">✓ completed successfully</span>}
        {isFailed && <span className="footer-err">✕ failed</span>}
      </div>

      <style>{`
        .log-panel { display: flex; flex-direction: column; gap: 20px; animation: fadeUp 0.3s ease; height: calc(100vh - 130px); }
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:none; } }

        .log-header {
          display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        .log-header-left { display: flex; align-items: center; gap: 20px; }
        .log-header-right { display: flex; align-items: center; gap: 12px; }

        .back-btn {
          background: none; border: none; color: var(--muted);
          font-family: var(--font); font-size: 13px; font-weight: 600;
          cursor: pointer; transition: color 0.15s; flex-shrink: 0;
        }
        .back-btn:hover { color: var(--text); }

        .log-title { font-size: 22px; font-weight: 800; text-transform: capitalize; }
        .log-job-id { font-size: 11px; color: var(--muted); font-family: var(--mono); }

        .phoenix-btn {
          display: flex; align-items: center; gap: 8px;
          background: rgba(255,158,74,0.08); border: 1px solid rgba(255,158,74,0.25);
          color: #ff9e4a; text-decoration: none;
          font-family: var(--font); font-size: 12px; font-weight: 700;
          padding: 7px 14px; border-radius: 8px;
          transition: background 0.15s;
        }
        .phoenix-btn:hover { background: rgba(255,158,74,0.14); }
        .phoenix-dot {
          width: 7px; height: 7px; border-radius: 50%;
          background: #ff9e4a; animation: pulse 1.4s ease infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

        .btn-notes {
          background: var(--accent); color: #fff; border: none;
          font-family: var(--font); font-size: 13px; font-weight: 700;
          padding: 8px 18px; border-radius: 8px; cursor: pointer;
          transition: opacity 0.15s;
        }
        .btn-notes:hover { opacity: 0.85; }

        .terminal {
          flex: 1;
          background: #080810;
          border: 1px solid var(--border);
          border-radius: 14px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          min-height: 0;
        }
        .terminal-topbar {
          display: flex; align-items: center; gap: 8px;
          padding: 10px 16px;
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          flex-shrink: 0;
        }
        .dot { width: 11px; height: 11px; border-radius: 50%; }
        .dot.red    { background: #ff5f57; }
        .dot.yellow { background: #febc2e; }
        .dot.green  { background: #28c840; }
        .terminal-title {
          font-size: 12px; color: var(--muted); font-family: var(--mono);
          flex: 1; text-align: center;
        }
        .autoscroll-toggle {
          display: flex; align-items: center; gap: 6px;
          font-size: 11px; color: var(--muted); font-family: var(--mono); cursor: pointer;
        }
        .autoscroll-toggle input { cursor: pointer; accent-color: var(--accent); }

        .log-lines {
          flex: 1; overflow-y: auto; padding: 16px 20px;
          display: flex; flex-direction: column; gap: 3px;
        }

        .log-waiting {
          display: flex; align-items: center; gap: 10px;
          color: var(--muted); font-family: var(--mono); font-size: 13px;
        }
        .waiting-spinner {
          width: 12px; height: 12px;
          border: 2px solid var(--border); border-top-color: var(--accent);
          border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .log-line {
          display: flex; align-items: baseline; gap: 10px;
          font-family: var(--mono); font-size: 13px; line-height: 1.6;
        }
        .log-ts { color: #3a3a50; font-size: 11px; flex-shrink: 0; width: 65px; }
        .log-prefix { flex-shrink: 0; width: 14px; text-align: center; }
        .log-msg { color: #c0c0d8; word-break: break-word; }
        .done-line .log-msg { color: var(--yellow); font-weight: 600; }

        .cursor-blink {
          color: var(--accent); animation: blink 1s step-end infinite; font-size: 14px;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

        .log-footer {
          display: flex; justify-content: space-between; align-items: center;
          padding: 8px 4px; font-size: 11px; color: var(--muted); font-family: var(--mono);
          flex-shrink: 0;
        }
        .footer-ok  { color: var(--green); }
        .footer-err { color: var(--red); }
      `}</style>
    </div>
  );
}

function StatusBadge({ status }) {
  const MAP = {
    pending:   ["#ffd166", "PENDING"],
    running:   ["#7c6aff", "RUNNING"],
    completed: ["#3dffa0", "DONE"],
    failed:    ["#ff5c5c", "FAILED"],
  };
  const [color, label] = MAP[status] || MAP.pending;
  return (
    <span style={{
      color, background: `${color}18`, border: `1px solid ${color}44`,
      fontFamily: "var(--mono)", fontSize: "11px", fontWeight: 700,
      letterSpacing: "0.1em", padding: "4px 12px", borderRadius: "20px",
    }}>
      {label}
    </span>
  );
}
