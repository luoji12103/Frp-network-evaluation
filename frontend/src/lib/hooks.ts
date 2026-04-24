import { startTransition, useEffect, useEffectEvent, useRef, useState, type DependencyList, type Dispatch, type SetStateAction } from 'react';
import { apiErrorDetail, applySnapshotIfNewer } from './api';
import type { SnapshotPayload } from './types';

interface SnapshotOptions {
  enabled?: boolean;
  pollMs?: number;
  keepPreviousOnError?: boolean;
}

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
  deps: DependencyList,
  options: SnapshotOptions = {},
): SnapshotResult<T> {
  const { enabled = true, pollMs, keepPreviousOnError = true } = options;
  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState<boolean>(enabled && initialData === null);
  const [error, setError] = useState<string | null>(null);
  const requestCounter = useRef(0);

  const commitPayload = useEffectEvent((payload: T) => {
    startTransition(() => {
      setData((current) => applySnapshotIfNewer(current, payload));
      setLoading(false);
      setError(null);
    });
  });

  const commitError = useEffectEvent((message: string) => {
    startTransition(() => {
      if (!keepPreviousOnError) {
        setData(null);
      }
      setLoading(false);
      setError(message);
    });
  });

  const runFetch = useEffectEvent(async () => {
    if (!enabled) {
      return;
    }
    const requestId = requestCounter.current + 1;
    requestCounter.current = requestId;
    startTransition(() => {
      setLoading(true);
    });
    try {
      const payload = await fetcher();
      if (requestCounter.current !== requestId) {
        return;
      }
      commitPayload(payload);
    } catch (fetchError) {
      if (requestCounter.current !== requestId) {
        return;
      }
      commitError(apiErrorDetail(fetchError));
    }
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void runFetch();
  }, [enabled, runFetch, ...deps]);

  useEffect(() => {
    if (!enabled || !pollMs) {
      return;
    }
    const handle = window.setInterval(() => {
      void runFetch();
    }, pollMs);
    return () => window.clearInterval(handle);
  }, [enabled, pollMs, runFetch, ...deps]);

  return {
    data,
    loading,
    error,
    refresh: runFetch,
    setData,
  };
}

export function useJsonEditor<T>(initialValue: T): [string, (next: string) => void, (fallback?: T) => T | null] {
  const [text, setText] = useState(() => JSON.stringify(initialValue, null, 2));

  useEffect(() => {
    setText(JSON.stringify(initialValue, null, 2));
  }, [initialValue]);

  const parse = (fallback?: T): T | null => {
    try {
      return JSON.parse(text) as T;
    } catch {
      return fallback ?? null;
    }
  };

  return [text, setText, parse];
}
