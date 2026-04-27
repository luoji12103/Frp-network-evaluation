import { startTransition } from 'react';
import type { ConflictDetail, SnapshotPayload } from './types';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export function apiErrorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
      return detail.message;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected request failure';
}

export function conflictDetail(error: unknown): ConflictDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409) {
    return null;
  }
  return typeof error.detail === 'object' && error.detail !== null ? (error.detail as ConflictDetail) : null;
}

export async function apiGet<T>(path: string): Promise<T> {
  return requestJson<T>(path, { method: 'GET' });
}

export async function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: 'POST',
    body: payload === undefined ? undefined : JSON.stringify(payload),
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
  });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
    ...init,
  });

  const text = await response.text();
  const data = text ? safeJsonParse(text) : null;
  if (!response.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data
        ? (data as Record<string, unknown>).detail
        : data ?? response.statusText;
    throw new ApiError(response.status, detail);
  }
  return (data ?? {}) as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function applySnapshotIfNewer<T extends SnapshotPayload>(current: T | null, incoming: T): T {
  const currentTs = snapshotTime(current?.generated_at);
  const incomingTs = snapshotTime(incoming.generated_at);
  if (current && currentTs !== null && incomingTs !== null && incomingTs < currentTs) {
    return current;
  }
  return incoming;
}

function snapshotTime(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

export function transition<T>(apply: () => T): void {
  startTransition(() => {
    apply();
  });
}
