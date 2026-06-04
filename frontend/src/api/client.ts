import type { CatalogResponse, PlanRequest, PlanResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function fetchCities() {
  return request<CatalogResponse>("/api/catalog/cities");
}

export function postPlan(body: PlanRequest) {
  return request<PlanResponse>("/api/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function healthCheck() {
  return request<{ status: string }>("/api/health");
}
