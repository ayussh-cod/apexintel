import { useState } from "react";
import Dashboard from "./components/Dashboard";
import RunPanel from "./components/RunPanel";
import NotesViewer from "./components/NotesViewer";
import LogStream from "./components/LogStream";

export default function App() {
  const [activeJob, setActiveJob] = useState(null);
  const [view, setView] = useState("dashboard"); // dashboard | run | logs | notes

  const handleJobStarted = (job) => {
    setActiveJob(job);
    setView("logs");
  };

  const handleViewNotes = (job) => {
    setActiveJob(job);
    setView("notes");
  };

  const handleViewLogs = (job) => {
    setActiveJob(job);
    setView("logs");
  };

  return (
    <div className="app-root">
      <Nav view={view} setView={setView} activeJob={activeJob} />
      <main className="main-content">
        {view === "dashboard" && (
          <Dashboard
            onRun={() => setView("run")}
            onViewNotes={handleViewNotes}
            onViewLogs={handleViewLogs}
          />
        )}
        {view === "run" && (
          <RunPanel
            onJobStarted={handleJobStarted}
            onBack={() => setView("dashboard")}
          />
        )}
        {view === "logs" && activeJob && (
          <LogStream
            job={activeJob}
            onViewNotes={() => setView("notes")}
            onBack={() => setView("dashboard")}
          />
        )}
        {view === "notes" && activeJob && (
          <NotesViewer job={activeJob} onBack={() => setView("dashboard")} />
        )}
      </main>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
          --bg:        #0a0a0f;
          --surface:   #111118;
          --surface2:  #18181f;
          --border:    #2a2a35;
          --accent:    #7c6aff;
          --accent2:   #ff6a9e;
          --green:     #3dffa0;
          --yellow:    #ffd166;
          --red:       #ff5c5c;
          --text:      #e8e8f0;
          --muted:     #6b6b80;
          --font:      'Syne', sans-serif;
          --mono:      'JetBrains Mono', monospace;
          --radius:    10px;
        }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: var(--font);
          min-height: 100vh;
          overflow-x: hidden;
        }

        .app-root {
          display: flex;
          flex-direction: column;
          min-height: 100vh;
        }

        .main-content {
          flex: 1;
          padding: 32px 40px;
          max-width: 1400px;
          margin: 0 auto;
          width: 100%;
        }

        /* scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--surface); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
      `}</style>
    </div>
  );
}

function Nav({ view, setView, activeJob }) {
  return (
    <nav>
      <div className="nav-inner">
        <div className="nav-logo" onClick={() => setView("dashboard")}>
          <span className="logo-mark">◈</span>
          <span className="logo-text">
            APEX<span className="logo-sub">INTEL</span>
          </span>
        </div>
        <div className="nav-links">
          <button
            className={view === "dashboard" ? "active" : ""}
            onClick={() => setView("dashboard")}
          >
            Dashboard
          </button>
          <button
            className={view === "run" ? "active" : ""}
            onClick={() => setView("run")}
          >
            New Run
          </button>
          {activeJob && (
            <>
              <button
                className={view === "logs" ? "active" : ""}
                onClick={() => setView("logs")}
              >
                Live Logs
              </button>
              <button
                className={view === "notes" ? "active" : ""}
                onClick={() => setView("notes")}
              >
                Notes Vault
              </button>
            </>
          )}
        </div>
      </div>
      <style>{`
        nav {
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          padding: 0 40px;
          position: sticky;
          top: 0;
          z-index: 100;
          backdrop-filter: blur(12px);
        }
        .nav-inner {
          max-width: 1400px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: 60px;
        }
        .nav-logo {
          display: flex;
          align-items: center;
          gap: 10px;
          cursor: pointer;
          user-select: none;
        }
        .logo-mark {
          font-size: 22px;
          color: var(--accent);
          line-height: 1;
        }
        .logo-text {
          font-size: 18px;
          font-weight: 800;
          letter-spacing: 0.12em;
          color: var(--text);
        }
        .logo-sub {
          color: var(--accent);
        }
        .nav-links {
          display: flex;
          gap: 4px;
        }
        .nav-links button {
          background: none;
          border: none;
          color: var(--muted);
          font-family: var(--font);
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.06em;
          padding: 6px 16px;
          border-radius: 6px;
          cursor: pointer;
          transition: color 0.15s, background 0.15s;
          text-transform: uppercase;
        }
        .nav-links button:hover { color: var(--text); background: var(--surface2); }
        .nav-links button.active { color: var(--accent); background: rgba(124,106,255,0.12); }
      `}</style>
    </nav>
  );
}
