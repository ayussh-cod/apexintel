import { useEffect, useState } from "react";
import { api } from "../api";

export default function NotesViewer({ job, onBack }) {
  const [tree, setTree]         = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [copied, setCopied]     = useState(false);

  useEffect(() => {
    api.getNotes(job.id)
      .then(data => { setTree(data); setLoading(false); })
      .catch(e  => { setError(e.message); setLoading(false); });
  }, [job.id]);

  const handleCopy = () => {
    if (!selected) return;
    navigator.clipboard.writeText(selected.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="notes-root">
      {/* Header */}
      <div className="notes-header">
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button className="back-btn" onClick={onBack}>← Back</button>
          <div>
            <h2 className="notes-title">Notes Vault</h2>
            <div className="notes-field">{job.field}</div>
          </div>
        </div>
        {selected && (
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn-copy" onClick={handleCopy}>
              {copied ? "✓ Copied!" : "Copy Markdown"}
            </button>
            <a
              className="btn-obsidian"
              href={`obsidian://open?path=${encodeURIComponent(selected.name)}`}
            >
              Open in Obsidian ↗
            </a>
          </div>
        )}
      </div>

      {loading ? (
        <div className="notes-loading"><div className="spinner" /></div>
      ) : error ? (
        <div className="notes-error">Failed to load notes: {error}</div>
      ) : (
        <div className="notes-layout">
          {/* Sidebar */}
          <aside className="notes-sidebar">
            <div className="sidebar-label">VAULT FILES</div>
            <FileTree node={tree} selected={selected} onSelect={setSelected} depth={0} />
          </aside>

          {/* Content */}
          <div className="notes-content">
            {selected ? (
              <>
                <div className="content-topbar">
                  <div className="content-filename">{selected.name}</div>
                  <div className="content-path">{selected.path}</div>
                </div>
                <pre className="content-body">{selected.content}</pre>
              </>
            ) : (
              <div className="content-empty">
                <div className="empty-icon">◈</div>
                <p>Select a file from the vault</p>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .notes-root { display: flex; flex-direction: column; height: calc(100vh - 130px); gap: 16px; animation: fadeUp 0.3s ease; }
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:none; } }

        .notes-header {
          display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        .back-btn {
          background: none; border: none; color: var(--muted);
          font-family: var(--font); font-size: 13px; font-weight: 600;
          cursor: pointer; transition: color 0.15s;
        }
        .back-btn:hover { color: var(--text); }
        .notes-title { font-size: 22px; font-weight: 800; }
        .notes-field { font-size: 12px; color: var(--muted); text-transform: capitalize; margin-top: 2px; }

        .btn-copy {
          background: var(--surface2); border: 1px solid var(--border);
          color: var(--muted); font-family: var(--font); font-size: 12px; font-weight: 600;
          padding: 7px 16px; border-radius: 8px; cursor: pointer; transition: all 0.15s;
        }
        .btn-copy:hover { color: var(--text); border-color: var(--text); }
        .btn-obsidian {
          background: rgba(124,106,255,0.1); border: 1px solid rgba(124,106,255,0.3);
          color: var(--accent); font-family: var(--font); font-size: 12px; font-weight: 700;
          padding: 7px 16px; border-radius: 8px; cursor: pointer; text-decoration: none;
          transition: background 0.15s;
        }
        .btn-obsidian:hover { background: rgba(124,106,255,0.18); }

        .notes-loading {
          display: flex; align-items: center; justify-content: center; flex: 1;
        }
        .spinner {
          width: 36px; height: 36px;
          border: 3px solid var(--border); border-top-color: var(--accent);
          border-radius: 50%; animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .notes-error {
          color: var(--red); font-family: var(--mono); font-size: 13px;
          background: rgba(255,92,92,0.08); border: 1px solid rgba(255,92,92,0.2);
          padding: 16px 20px; border-radius: var(--radius);
        }

        .notes-layout {
          display: grid;
          grid-template-columns: 260px 1fr;
          gap: 16px;
          flex: 1;
          min-height: 0;
        }

        .notes-sidebar {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 16px 12px;
          overflow-y: auto;
        }
        .sidebar-label {
          font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
          color: var(--muted); padding: 0 6px; margin-bottom: 12px;
          font-family: var(--mono);
        }

        .notes-content {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 12px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          min-height: 0;
        }
        .content-topbar {
          padding: 14px 20px;
          border-bottom: 1px solid var(--border);
          background: var(--surface2);
          flex-shrink: 0;
        }
        .content-filename { font-size: 14px; font-weight: 700; font-family: var(--mono); }
        .content-path { font-size: 11px; color: var(--muted); font-family: var(--mono); margin-top: 2px; }

        .content-body {
          flex: 1; overflow-y: auto;
          padding: 24px 28px;
          font-family: var(--mono); font-size: 13px; line-height: 1.8;
          color: #c8c8e0; white-space: pre-wrap; word-break: break-word;
          margin: 0;
        }

        .content-empty {
          flex: 1; display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          gap: 12px; color: var(--muted);
        }
        .empty-icon { font-size: 40px; }
        .content-empty p { font-size: 14px; }
      `}</style>
    </div>
  );
}

function FileTree({ node, selected, onSelect, depth, parentPath = "" }) {
  const [open, setOpen] = useState(depth < 2);

  if (!node) return null;

  const path = parentPath ? `${parentPath}/${node.name}` : node.name;

  if (node.type === "file") {
    const ext  = node.name.split(".").pop();
    const icon = ext === "md" ? "📄" : "📋";
    const isSelected = selected?.path === path;

    return (
      <div
        className={`tree-file ${isSelected ? "selected" : ""}`}
        style={{ paddingLeft: depth * 14 + 8 }}
        onClick={() => onSelect({ ...node, path })}
      >
        <span>{icon}</span>
        <span className="tree-name">{node.name}</span>
      </div>
    );
  }

  // Directory
  return (
    <div>
      {depth > 0 && (
        <div
          className="tree-dir"
          style={{ paddingLeft: depth * 14 + 8 }}
          onClick={() => setOpen(o => !o)}
        >
          <span className="tree-arrow">{open ? "▾" : "▸"}</span>
          <span className="tree-folder-icon">📁</span>
          <span className="tree-dirname">{node.name}</span>
        </div>
      )}
      {(open || depth === 0) && node.children?.map((child, i) => (
        <FileTree
          key={i}
          node={child}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
          parentPath={path}
        />
      ))}
    </div>
  );
}
