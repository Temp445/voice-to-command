import { invoke } from '@tauri-apps/api/core';

// Ensure we don't accidentally use a dev tunnel URL when running locally, but allow it for remote devices
const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

function getBaseUrl() {
  if (typeof window === 'undefined') return "http://127.0.0.1:8000/api";
  if (window.location.hostname.includes("devtunnels.ms")) {
    return window.location.origin.replace("-3000", "-8000") + "/api";
  }
  return "http://127.0.0.1:8000/api";
}

let resolvedBaseUrl: string | null = null;
export let resolvedBackendPort = 8000;

export async function getResolvedBaseUrl(): Promise<string> {
  if (resolvedBaseUrl) return resolvedBaseUrl;

  let port = 8000;
  if (typeof window !== 'undefined' && (window as any).__TAURI_IPC__) {
    try {
      port = await invoke('get_backend_port');
    } catch (e) {
      console.warn("Failed to get backend port from Tauri, using default 8000", e);
    }
  } else if (process.env.NEXT_PUBLIC_API_PORT) {
    port = parseInt(process.env.NEXT_PUBLIC_API_PORT, 10);
  }

  let base = `http://127.0.0.1:${port}/api`;
  if (!isLocalhost && !(typeof window !== 'undefined' && (window as any).__TAURI_IPC__)) {
    base = process.env.NEXT_PUBLIC_API_URL || getBaseUrl();
  }
  
  if (base.endsWith('/')) base = base.slice(0, -1);
  if (!base.endsWith('/api')) base += "/api";
  
  resolvedBaseUrl = base;
  resolvedBackendPort = port;
  return base;
}

export async function getBackendWsUrl(): Promise<string> {
  const base = await getResolvedBaseUrl();
  let wsUrl = base.replace(/\/api$/, "/ws");
  return wsUrl.replace(/^http/, "ws");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const base = await getResolvedBaseUrl();
  const headers: Record<string, string> = { "Content-Type": "application/json", ...((options.headers as Record<string, string>) || {}) };
  
  // Attach local JWT token if available
  try {
    const token = localStorage.getItem("ace-local-token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } catch (e) {}

  const res = await fetch(`${base}${path}`, {
    headers,
    cache: "no-store",
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
  executeCommand: (text: string, source = "text", id?: string) =>
    request("/commands/execute", {
      method: "POST",
      body: JSON.stringify({ text, source, id }),
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
  sync:     (access_token: string) =>
    request("/auth/sync", { method: "POST", body: JSON.stringify({ access_token }) }),
    
  // LLM / AI Assistant
  getLLMProviders: () => request("/llm/providers"),
  getLLMStatus:    () => request("/llm/status"),
  testLLM:         () => request("/llm/test", { method: "POST" }),
  chatLLM:         (message: string) => request("/llm/chat", { method: "POST", body: JSON.stringify({ message }) }),
  clearLLMHistory: () => request("/llm/history", { method: "DELETE" }),

  // Health / Ping
  getHealthPing: async () => {
    const base = await getResolvedBaseUrl();
    const start = performance.now();
    const res = await fetch(`${base}/health`, { cache: "no-store" });
    const processTime = res.headers.get("X-Process-Time");
    const networkTime = Math.round(performance.now() - start);
    return { processTime, networkTime, ok: res.ok };
  },
};
