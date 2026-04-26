import { startTransition, useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { apiErrorDetail, applySnapshotIfNewer } from './api';
import type { SnapshotPayload } from './types';

interface SnapshotOptions {
  enabled?: boolean;
  pollMs?: number;
  keepPreviousOnError?: boolean;
}

type SnapshotDependency = string | number | boolean | null | undefined;

interface SnapshotResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setData: Dispatch<SetStateAction<T | null>>;
}

export function useSnapshotResource<T extends SnapshotPayload>(
  fetcher: () => Promise<T>,
  initialData: T | null,
  deps: SnapshotDependency[],
  options: SnapshotOptions = {},
): SnapshotResult<T> {
  const { enabled = true, pollMs, keepPreviousOnError = true } = options;
  const depsKey = JSON.stringify(deps.map((dependency) => [typeof dependency, dependency]));
  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState<boolean>(enabled && initialData === null);
  const [error, setError] = useState<string | null>(null);
  const requestCounter = useRef(0);
  const inFlightRequest = useRef<number | null>(null);
  const fetcherRef = useRef(fetcher);
  const enabledRef = useRef(enabled);
  const keepPreviousOnErrorRef = useRef(keepPreviousOnError);

  fetcherRef.current = fetcher;
  enabledRef.current = enabled;
  keepPreviousOnErrorRef.current = keepPreviousOnError;

  const runFetch = useCallback(async (force = false) => {
    if (!enabledRef.current) {
      return;
    }
    if (!force && inFlightRequest.current !== null) {
      return;
    }
    const requestId = requestCounter.current + 1;
    requestCounter.current = requestId;
    inFlightRequest.current = requestId;
    startTransition(() => {
      setLoading(true);
    });
    try {
      const payload = await fetcherRef.current();
      if (requestCounter.current !== requestId) {
        return;
      }
      startTransition(() => {
        setData((current) => applySnapshotIfNewer(current, payload));
        setLoading(false);
        setError(null);
      });
    } catch (fetchError) {
      if (requestCounter.current !== requestId) {
        return;
      }
      startTransition(() => {
        if (!keepPreviousOnErrorRef.current) {
          setData(null);
        }
        setLoading(false);
        setError(apiErrorDetail(fetchError));
      });
    } finally {
      if (inFlightRequest.current === requestId) {
        inFlightRequest.current = null;
      }
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void runFetch(true);
  }, [runFetch, enabled, depsKey]);

  useEffect(() => {
    if (!enabled || !pollMs) {
      return;
    }
    const handle = window.setInterval(() => {
      void runFetch(false);
    }, pollMs);
    return () => window.clearInterval(handle);
  }, [runFetch, enabled, pollMs, depsKey]);

  return {
    data,
    loading,
    error,
    refresh: () => runFetch(true),
    setData,
  };
}

export function useJsonEditor<T>(initialValue: T): [string, (next: string) => void, (fallback?: T) => T | null] {
  const serializedValue = JSON.stringify(initialValue, null, 2);
  const [draft, setDraft] = useState(() => ({
    source: serializedValue,
    text: serializedValue,
  }));

  const text = draft.source === serializedValue ? draft.text : serializedValue;
  const setText = (next: string) => {
    setDraft({
      source: serializedValue,
      text: next,
    });
  };

  const parse = (fallback?: T): T | null => {
    try {
      return JSON.parse(text) as T;
    } catch {
      return fallback ?? null;
    }
  };

  return [text, setText, parse];
}
