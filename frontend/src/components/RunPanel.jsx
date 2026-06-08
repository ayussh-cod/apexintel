import { useState } from "react";
import { api } from "../api";

const EXAMPLES = [
  "venture capital", "competitive programming", "machine learning research",
  "professional chess", "quantitative trading", "open source software",
  "scientific research", "product management",
];

export default function RunPanel({ onJobStarted, onBack }) {
  const [field, setField]   = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");

  const handleSubmit = async () => {
    if (!field.trim()) { setError("Please enter a field."); return; }
    setError("");
    setLoading(true);
    try {
      const data = await api.runPipeline(field.trim());
      onJobStarted({ id: data.job_id, field: field.trim(), status: data.status });
    } catch (e) {
      setError(e.message || "Failed to start pipeline.");
      setLoading(false);
    }
  };

  return (
    <div className="run-panel">
      <button className="back-btn" onClick={onBack}>← Back</button>

      <div className="run-hero">
        <div className="hero-badge">PIPELINE CONFIG</div>
        <h1 className="hero-title">Who masters <em>your</em> field?</h1>
        <p className="hero-sub">
          Enter a domain and the pipeline will discover top performers,
          extract their strategies, and synthesise actionable Obsidian notes.
        </p>
      </div>

      <div className="run-form">
        <div className="field-wrap">
          <label className="field-label">Research Field</label>
          <input
            className={`field-input ${error ? "err" : ""}`}
            type="text"
            placeholder="e.g. competitive programming"
            value={field}
            onChange={e => { setField(e.target.value); setError(""); }}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            autoFocus
          />
          {error && <p className="field-error">{error}</p>}
        </div>

        <div className="examples">
          <span className="examples-label">Quick picks:</span>
          {EXAMPLES.map(ex => (
            <button key={ex} className="example-chip" onClick={() => setField(ex)}>
              {ex}
            </button>
          ))}
        </div>

        <div className="pipeline-steps">
          {[
            { icon: "◎", label: "Query Agent", desc: "Gemini discovers top performers via Tavily" },
            { icon: "⬡", label: "URL Extractor", desc: "Tavily Extract pulls full article content" },
            { icon: "◈", label: "Synthesizer", desc: "Gemini distils strategies into Obsidian notes" },
          ].map((step, i) => (
            <div key={i} className="step-card">
              <div className="step-icon">{step.icon}</div>
              <div>
                <div className="step-label">{step.label}</div>
                <div className="step-desc">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <button className="launch-btn" onClick={handleSubmit} disabled={loading}>
          {loading ? (
            <><span className="btn-spinner" /> Starting…</>
          ) : (
            <><span>▶</span> Launch Pipeline</>
          )}
        </button>
      </div>

      <style>{`
        .run-panel { max-width: 680px; margin: 0 auto; animation: fadeUp 0.3s ease; }
        @keyframes fadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:none; } }

        .back-btn {
          background: none; border: none; color: var(--muted);
          font-family: var(--font); font-size: 13px; font-weight: 600;
          cursor: pointer; padding: 0; margin-bottom: 36px;
          transition: color 0.15s;
        }
        .back-btn:hover { color: var(--text); }

        .run-hero { margin-bottom: 40px; }
        .hero-badge {
          display: inline-block;
          font-size: 10px; font-weight: 700; letter-spacing: 0.14em;
          color: var(--accent); border: 1px solid rgba(124,106,255,0.35);
          background: rgba(124,106,255,0.08);
          padding: 4px 12px; border-radius: 20px; margin-bottom: 16px;
          font-family: var(--mono);
        }
        .hero-title {
          font-size: 42px; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1;
          margin-bottom: 14px;
        }
        .hero-title em { color: var(--accent); font-style: normal; }
        .hero-sub { color: var(--muted); font-size: 16px; line-height: 1.65; max-width: 520px; }

        .run-form { display: flex; flex-direction: column; gap: 28px; }

        .field-wrap { display: flex; flex-direction: column; gap: 8px; }
        .field-label { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: var(--muted); text-transform: uppercase; }

        .field-input {
          background: var(--surface);
          border: 1.5px solid var(--border);
          color: var(--text);
          font-family: var(--font);
          font-size: 18px;
          font-weight: 600;
          padding: 16px 20px;
          border-radius: var(--radius);
          outline: none;
          transition: border-color 0.2s;
        }
        .field-input:focus { border-color: var(--accent); }
        .field-input.err { border-color: var(--red); }
        .field-input::placeholder { color: var(--muted); font-weight: 400; }
        .field-error { font-size: 12px; color: var(--red); font-family: var(--mono); }

        .examples { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        .examples-label { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: 0.05em; margin-right: 4px; }
        .example-chip {
          background: var(--surface2); border: 1px solid var(--border);
          color: var(--muted); font-family: var(--font); font-size: 12px; font-weight: 600;
          padding: 5px 12px; border-radius: 20px; cursor: pointer;
          transition: all 0.15s;
        }
        .example-chip:hover { color: var(--accent); border-color: rgba(124,106,255,0.4); background: rgba(124,106,255,0.06); }

        .pipeline-steps {
          display: flex; flex-direction: column; gap: 12px;
          border: 1px solid var(--border); border-radius: 12px;
          padding: 20px; background: var(--surface);
        }
        .step-card {
          display: flex; align-items: center; gap: 16px;
          padding: 12px 0;
          border-bottom: 1px solid var(--border);
        }
        .step-card:last-child { border-bottom: none; padding-bottom: 0; }
        .step-card:first-child { padding-top: 0; }
        .step-icon { font-size: 22px; color: var(--accent); width: 28px; text-align: center; flex-shrink: 0; }
        .step-label { font-size: 14px; font-weight: 700; margin-bottom: 2px; }
        .step-desc { font-size: 12px; color: var(--muted); }

        .launch-btn {
          background: linear-gradient(135deg, var(--accent), #a855f7);
          color: #fff; border: none;
          font-family: var(--font); font-size: 16px; font-weight: 700;
          padding: 16px 32px; border-radius: var(--radius);
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          gap: 10px; letter-spacing: 0.04em;
          transition: opacity 0.2s, transform 0.2s;
          box-shadow: 0 4px 24px rgba(124,106,255,0.3);
        }
        .launch-btn:hover:not(:disabled) { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 8px 32px rgba(124,106,255,0.4); }
        .launch-btn:disabled { opacity: 0.55; cursor: not-allowed; }

        .btn-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
