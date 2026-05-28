// Typed API client
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Commands
  executeCommand: (text: string, source = "text") =>
    request("/commands/execute", {
      method: "POST",
      body: JSON.stringify({ text, source }),
    }),

  getHistory: (limit = 50) => request(`/commands/history?limit=${limit}`),
  getIntents:  () => request("/commands/intents"),

  // Voice
  getVoiceStatus: () => request("/voice/status"),
  activate:        () => request("/voice/activate", { method: "POST" }),
  deactivate:      () => request("/voice/deactivate", { method: "POST" }),

  // Settings
  getSettings:     () => request("/settings"),
  updateSettings:  (patch: Record<string, unknown>) =>
    request("/settings", { method: "PATCH", body: JSON.stringify(patch) }),

  // Workflows
  listWorkflows:   () => request("/workflows"),
  createWorkflow:  (body: unknown) =>
    request("/workflows", { method: "POST", body: JSON.stringify(body) }),
  runWorkflow:     (id: string) =>
    request(`/workflows/${id}/run`, { method: "POST" }),
  deleteWorkflow:  (id: string) =>
    request(`/workflows/${id}`, { method: "DELETE" }),

  // Automation logs
  getLogs: (limit = 100) => request(`/automation/logs?limit=${limit}`),

  // Auth
  login:    (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, display_name?: string) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password, display_name }) }),
};
