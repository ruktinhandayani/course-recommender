import type {
  AuthUser,
  DataMode,
  EvaluationResponse,
  ExportResponse,
  HealthResponse,
  RefreshJob,
  ResearchSummaryResponse,
  UserResponse,
} from "./types";

// In Docker, the browser talks only to the UI origin and Nginx proxies /ui/api
// to the internal ML service. A configured absolute URL remains supported for
// standalone development.
const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

interface ApiErrorPayload {
  detail?: string;
  error?: {
    code?: string;
    message?: string;
  };
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new Error("Could not connect to the ML service through the dashboard proxy.");
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new Error(payload.error?.message || payload.detail || `Request failed with status ${response.status}.`);
  }

  return response.json() as Promise<T>;
}

function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

function postJson<T>(path: string, body?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function getCurrentAdmin(): Promise<AuthUser> {
  return getJson<AuthUser>("/ui/api/auth/me");
}

export function loginAdmin(username: string, password: string): Promise<AuthUser> {
  return postJson<AuthUser>("/ui/api/auth/login", { username, password });
}

export function logoutAdmin(): Promise<AuthUser> {
  return postJson<AuthUser>("/ui/api/auth/logout");
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/ui/api/health");
}

export function getUserRecommendations(userId: string, mode: DataMode): Promise<UserResponse> {
  const query = new URLSearchParams({ mode });
  return getJson<UserResponse>(
    `/ui/api/recommendations/user/${encodeURIComponent(userId)}?${query.toString()}`,
  );
}

export function getExportPage(
  cursor: string | null,
  limit: number,
  mode: DataMode,
): Promise<ExportResponse> {
  const query = new URLSearchParams({ limit: String(limit), mode });
  if (cursor) query.set("cursor", cursor);
  return getJson<ExportResponse>(`/ui/api/recommendations/export?${query.toString()}`);
}

export function getEvaluationSummary(): Promise<EvaluationResponse> {
  return getJson<EvaluationResponse>("/ui/api/evaluation/summary");
}

export function getResearchSummary(): Promise<ResearchSummaryResponse> {
  return getJson<ResearchSummaryResponse>("/ui/api/research/summary");
}

export function startRefresh(topK: number, maxUsers: number | null): Promise<RefreshJob> {
  return postJson<RefreshJob>("/ui/api/refresh/start", {
    top_k: topK,
    max_users: maxUsers,
    mode: "normal",
  });
}

export function getRefreshStatus(jobId: string): Promise<RefreshJob> {
  return getJson<RefreshJob>(`/ui/api/refresh/status/${encodeURIComponent(jobId)}`);
}
