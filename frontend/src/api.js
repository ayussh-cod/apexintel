// const BASE = "/api";
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";   

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  runPipeline: (field) =>
    request("/run", { method: "POST", body: JSON.stringify({ field }) }),
  getJobs: () => request("/jobs"),
  getJob: (id) => request(`/jobs/${id}`),
  getNotes: (id) => request(`/notes/${id}`),
  deleteJob: (id) => request(`/jobs/${id}`, { method: "DELETE" }),
};
