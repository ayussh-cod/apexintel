import { useEffect, useState } from "react";
import { api } from "../api";

const STATUS_META = {
  pending:   { color: "#ffd166", label: "PENDING",   dot: "○" },
  running:   { color: "#7c6aff", label: "RUNNING",   dot: "◉" },
  completed: { color: "#3dffa0", label: "DONE",      dot: "●" },
  failed:    { color: "#ff5c5c", label: "FAILED",    dot: "✕" },
};

export default function Dashboard({ onRun, onViewNotes, onViewLogs }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      const data = await api.getJobs();
      setJobs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = async (jobId, e) => {
    e.stopPropagation();
    await api.deleteJob(jobId);
    setJobs(j => j.filter(x => x.id !== jobId));
  };

  return (
    <div className="dashboard">
      <div className="dash-header">
        <div>
          <h1 className="dash-title">Intelligence Runs</h1>
          <p className="dash-sub">Top performer strategy extraction pipeline</p>
        </div>
        <button className="btn-primary" onClick={onRun}>
          <span>＋</span> New Run
        </button>
      </div>

      {loading ? (
        <div className="empty-state">
          <div className="spinner" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">◈</div>
          <p className="empty-title">No runs yet</p>
          <p className="empty-sub">Start your first pipeline to discover top performer strategies</p>
          <button className="btn-primary" onClick={onRun}>Launch Pipeline</button>
        </div>
      ) : (
        <div className="job-grid">
          {jobs.map(job => {
            const meta = STATUS_META[job.status] || STATUS_META.pending;
            return (
              <div key={job.id} className="job-card">
                <div className="job-card-top">
                  <div className="job-status" style={{ color: meta.color }}>
                    <span className={job.status === "running" ? "pulse-dot" : ""}>{meta.dot}</span>
                    {meta.label}
                  </div>
                  <button className="btn-icon" onClick={(e) => handleDelete(job.id, e)} title="Delete">✕</button>
                </div>

                <div className="job-field">{job.field}</div>
                <div className="job-id">ID: {job.id.slice(0, 8)}…</div>

                <div className="job-meta">
                  <span>{new Date(job.created_at).toLocaleString()}</span>
                  {job.completed_at && (
                    <span className="job-duration">
                      {Math.round((new Date(job.completed_at) - new Date(job.created_at)) / 1000)}s
                    </span>
                  )}
                </div>

                {job.error && (
                  <div className="job-error">{job.error.slice(0, 120)}</div>
                )}

                <div className="job-actions">
                  <button
                    className="btn-ghost"
                    onClick={() => onViewLogs(job)}
                  >
                    Logs
                  </button>
                  {job.status === "completed" && (
                    <button className="btn-ghost accent" onClick={() => onViewNotes(job)}>
                      View Notes
                    </button>
                  )}
                  {job.phoenix_url && (
                    <a className="btn-ghost phoenix" href={job.phoenix_url} target="_blank" rel="noreferrer">
                      Phoenix ↗
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        .dashboard { animation: fadeUp 0.35s ease; }
        @keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:none; } }

        .dash-header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          margin-bottom: 40px;
        }
        .dash-title {
          font-size: 36px;
          font-weight: 800;
          letter-spacing: -0.02em;
          background: linear-gradient(135deg, var(--text) 40%, var(--accent));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .dash-sub { color: var(--muted); margin-top: 4px; font-size: 14px; }

        .btn-primary {
          background: var(--accent);
          color: #fff;
          border: none;
          font-family: var(--font);
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 0.05em;
          padding: 10px 22px;
          border-radius: var(--radius);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: opacity 0.15s, transform 0.15s;
        }
        .btn-primary:hover { opacity: 0.88; transform: translateY(-1px); }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 360px;
          gap: 16px;
          text-align: center;
        }
        .empty-icon { font-size: 52px; color: var(--border); }
        .empty-title { font-size: 22px; font-weight: 700; color: var(--muted); }
        .empty-sub { color: var(--muted); font-size: 14px; max-width: 360px; line-height: 1.6; }

        .spinner {
          width: 36px; height: 36px;
          border: 3px solid var(--border);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .job-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: 20px;
        }

        .job-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 22px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          transition: border-color 0.2s, transform 0.2s;
        }
        .job-card:hover { border-color: var(--accent); transform: translateY(-2px); }

        .job-card-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .job-status {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.1em;
          display: flex;
          align-items: center;
          gap: 6px;
          font-family: var(--mono);
        }
        .pulse-dot { animation: pulse 1.2s ease infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

        .btn-icon {
          background: none;
          border: none;
          color: var(--muted);
          cursor: pointer;
          font-size: 13px;
          padding: 4px 8px;
          border-radius: 4px;
          transition: color 0.15s, background 0.15s;
        }
        .btn-icon:hover { color: var(--red); background: rgba(255,92,92,0.1); }

        .job-field {
          font-size: 20px;
          font-weight: 700;
          color: var(--text);
          text-transform: capitalize;
        }
        .job-id { font-size: 11px; color: var(--muted); font-family: var(--mono); }

        .job-meta {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: var(--muted);
          font-family: var(--mono);
        }
        .job-duration {
          color: var(--green);
          background: rgba(61,255,160,0.08);
          padding: 1px 6px;
          border-radius: 4px;
        }

        .job-error {
          font-size: 12px;
          color: var(--red);
          background: rgba(255,92,92,0.08);
          border: 1px solid rgba(255,92,92,0.2);
          border-radius: 6px;
          padding: 8px 10px;
          font-family: var(--mono);
        }

        .job-actions {
          display: flex;
          gap: 8px;
          margin-top: 4px;
          flex-wrap: wrap;
        }
        .btn-ghost {
          background: var(--surface2);
          border: 1px solid var(--border);
          color: var(--muted);
          font-family: var(--font);
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.04em;
          padding: 6px 14px;
          border-radius: 6px;
          cursor: pointer;
          text-decoration: none;
          display: inline-block;
          transition: all 0.15s;
        }
        .btn-ghost:hover { color: var(--text); border-color: var(--text); }
        .btn-ghost.accent { color: var(--accent); border-color: rgba(124,106,255,0.4); }
        .btn-ghost.accent:hover { background: rgba(124,106,255,0.12); border-color: var(--accent); }
        .btn-ghost.phoenix { color: #ff9e4a; border-color: rgba(255,158,74,0.3); }
        .btn-ghost.phoenix:hover { background: rgba(255,158,74,0.08); }
      `}</style>
    </div>
  );
}
