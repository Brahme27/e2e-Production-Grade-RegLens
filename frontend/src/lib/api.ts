"use client";

import { useCallback, useEffect, useState } from "react";

// All calls go through our own Next.js proxy (same origin, API key added server-side).
export const API = "/api/proxy";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** Fetch JSON for `path`; exposes loading / error / reload. State is only set when the
 *  request settles (never synchronously inside the effect), as React recommends. */
export function useApi<T>(path: string | null) {
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null } | null>(null);
  const key = `${path}#${version}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    apiFetch<T>(path).then(
      (data) => !cancelled && setResult({ key, data, error: null }),
      (e: unknown) => !cancelled && setResult({ key, data: null, error: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      cancelled = true;
    };
  }, [path, key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const current = result?.key === key ? result : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: path !== null && current === null,
    reload,
  };
}

/** POST and read a Server-Sent Events stream, calling onEvent for each `event:/data:` pair. */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const type = /^event: (.*)$/m.exec(raw)?.[1] ?? "message";
      const data = /^data: (.*)$/m.exec(raw)?.[1] ?? "{}";
      onEvent(type, JSON.parse(data));
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export const pct = (x: number | null | undefined, digits = 1) =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;

export const num = (x: number | null | undefined, digits = 3) =>
  x === null || x === undefined ? "—" : x.toFixed(digits);
