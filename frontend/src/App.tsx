import { useEffect, useReducer, useRef, useState } from "react";
import { createGame, listCases, postAction, streamGame } from "./api";
import {
  EvidencePanel,
  HumanControls,
  JurorCard,
  ScorecardView,
  TranscriptStream,
  VoteTally,
} from "./components";
import { initialState, reduce } from "./gameReducer";
import type { CaseInfo, GameEvent, ViewState } from "./types";

type Action = GameEvent | { type: "__reset"; caseInfo: CaseInfo | null };

function appReducer(state: ViewState, action: Action): ViewState {
  if (action.type === "__reset") return initialState((action as any).caseInfo);
  return reduce(state, action as GameEvent);
}

type Phase = "idle" | "playing";

export default function App() {
  const [view, dispatch] = useReducer(appReducer, initialState());
  const [phase, setPhase] = useState<Phase>("idle");
  const [mode, setMode] = useState<"scripted" | "dynamic">("scripted");
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [gid, setGid] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    listCases().then(setCases).catch((e) => setError(String(e)));
    return () => unsubRef.current?.();
  }, []);

  async function start() {
    setError(null);
    try {
      const res = await createGame(mode);
      dispatch({ type: "__reset", caseInfo: res.case });
      setGid(res.game_id);
      setPhase("playing");
      unsubRef.current?.();
      unsubRef.current = streamGame(res.game_id, (ev) => {
        dispatch(ev);
        if (ev.type === "done") unsubRef.current?.(); // stop EventSource auto-reconnect
      });
    } catch (e) {
      setError(String(e));
    }
  }

  function onAction(action: string, text = "") {
    if (gid) postAction(gid, action, text).catch((e) => setError(String(e)));
  }

  const charge = view.caseInfo?.charge ?? cases[0]?.charge;

  return (
    <div className="min-h-screen p-4 max-w-7xl mx-auto">
      <header className="mb-4">
        <h1 className="text-2xl font-black text-amber-400">⚖️ Jury Deliberation Simulator</h1>
        <p className="text-sm text-stone-400">
          Multi-agent LLM jury · RAG evidence tool · ReAct · LangChain + Gemini
        </p>
      </header>

      {error && (
        <div className="mb-3 rounded border border-red-700 bg-red-950/50 text-red-300 text-sm p-2">
          {error}
        </div>
      )}

      {phase === "idle" && (
        <div className="rounded-lg border border-stone-700 bg-stone-900/80 p-5 max-w-2xl">
          <h2 className="font-bold text-parchment mb-1">{cases[0]?.title ?? "Loading case…"}</h2>
          <p className="text-sm text-stone-400 mb-4">{cases[0]?.summary}</p>
          <div className="flex items-center gap-4 mb-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={mode === "scripted"}
                onChange={() => setMode("scripted")}
              />
              Scripted jurors (deterministic)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={mode === "dynamic"}
                onChange={() => setMode("dynamic")}
              />
              LLM-generated jurors
            </label>
          </div>
          <button
            className="px-4 py-2 rounded bg-amber-700 hover:bg-amber-600 font-semibold disabled:opacity-40"
            onClick={start}
            disabled={!cases.length}
          >
            Convene the jury
          </button>
        </div>
      )}

      {phase === "playing" && (
        <>
          <div className="mb-3 text-sm text-stone-400">{charge}</div>
          <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_320px] gap-3">
            <div className="space-y-2">
              {view.jurors.map((j) => (
                <JurorCard key={j.persona.id} juror={j} active={view.activeJurorId === j.persona.id} />
              ))}
            </div>

            <div className="space-y-3">
              <VoteTally
                tally={view.tally}
                status={view.status}
                round={view.round}
                maxRounds={view.maxRounds}
              />
              <TranscriptStream log={view.log} />
              {view.hint && !view.finished && (
                <div className="rounded border border-amber-700 bg-amber-950/30 text-amber-200 text-sm p-2">
                  💡 {view.hint}
                </div>
              )}
              {view.awaitingHuman && !view.finished && (
                <HumanControls options={view.humanOptions} onAction={onAction} />
              )}
              {view.finished && view.scorecard && (
                <ScorecardView scorecard={view.scorecard} verdict={view.verdict} />
              )}
            </div>

            <EvidencePanel
              evidence={view.caseInfo?.evidence ?? []}
              highlighted={view.highlightedEvidence}
            />
          </div>
        </>
      )}
    </div>
  );
}
