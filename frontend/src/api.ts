import type { CaseInfo, GameEvent } from "./types";

// Vite proxies /api to the FastAPI backend in dev.
async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function listCases(): Promise<CaseInfo[]> {
  return fetch("/api/cases").then(json<CaseInfo[]>);
}

export interface CreateResult {
  game_id: string;
  case: CaseInfo;
  mode: string;
}

export function createGame(mode: "scripted" | "dynamic", caseId?: string): Promise<CreateResult> {
  return fetch("/api/game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, case_id: caseId ?? null }),
  }).then(json<CreateResult>);
}

export function postAction(gid: string, action: string, text = ""): Promise<void> {
  return fetch(`/api/game/${gid}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, text }),
  }).then((r) => json<unknown>(r)).then(() => undefined);
}

/** Subscribe to the deliberation event stream. Returns an unsubscribe fn. */
export function streamGame(
  gid: string,
  onEvent: (ev: GameEvent) => void,
  onError?: (e: Event) => void
): () => void {
  const es = new EventSource(`/api/game/${gid}/stream`);
  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as GameEvent);
    } catch {
      /* ignore malformed frame */
    }
  };
  es.onerror = (e) => {
    onError?.(e);
  };
  return () => es.close();
}
