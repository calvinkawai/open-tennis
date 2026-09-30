"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError } from "../lib/api";

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}${error.code ? ` (${error.code})` : ""}${error.requestId ? ` · 请求 ${error.requestId}` : ""}`;
  }
  return error instanceof Error ? error.message : "操作未完成，请保留输入并重新尝试。";
}

export function Notice({ children, warning = false }: { children: ReactNode; warning?: boolean }) {
  return <div className={`notice ${warning ? "warning" : ""}`} role={warning ? "alert" : "status"}>{children}</div>;
}

export function useLoad<T>(load: () => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    load().then(
      (data) => { if (!cancelled) setState({ data, loading: false }); },
      (error: unknown) => { if (!cancelled) setState({ error: errorText(error), loading: false }); },
    );
    return () => { cancelled = true; };
  }, [load, revision]);
  return { ...state, reload: useCallback(() => setRevision((value) => value + 1), []) };
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const act = async (work: () => Promise<void>, success?: string) => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      await work();
      if (success) setMessage(success);
    } catch (error) {
      setFailed(true);
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  return {
    busy, act,
    feedback: message ? <Notice warning={failed}>{message}</Notice> : null,
  };
}

export function Loading() {
  return <div className="loading-state" role="status"><span className="loading-dot" />正在打开你的球场手册…</div>;
}

export function Failure({ message, retry }: { message: string; retry: () => void }) {
  return <div className="empty-state"><Notice warning>{message}</Notice><button className="button secondary" onClick={retry}>重新加载</button></div>;
}

export function downloadJson(value: object, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
