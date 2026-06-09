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
import { TR, type Lang } from "./i18n";
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
  const [lang, setLang] = useState<Lang>("en");
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [gid, setGid] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unsubRef = useRef<(() => void) | null>(null);

  const t = TR[lang];

  // (Re)load the case preview whenever the chosen language changes (idle only).
  useEffect(() => {
    listCases(lang).then(setCases).catch((e) => setError(String(e)));
  }, [lang]);

  useEffect(() => () => unsubRef.current?.(), []);

  async function start() {
    setError(null);
    try {
      const res = await createGame(mode, lang);
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
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-amber-400">⚖️ Jury Deliberation Simulator</h1>
          <p className="text-sm text-stone-400">{t.subtitle}</p>
        </div>
        {/* Language switch — locked once a game is convened */}
        <div className="flex items-center gap-1 text-sm shrink-0">
          {(["en", "zh"] as Lang[]).map((l) => (
            <button
              key={l}
              disabled={phase !== "idle"}
              onClick={() => setLang(l)}
              className={`px-2 py-1 rounded border ${
                lang === l ? "border-amber-500 text-amber-300" : "border-stone-700 text-stone-500"
              } ${phase !== "idle" ? "opacity-50 cursor-not-allowed" : "hover:border-stone-500"}`}
            >
              {l === "en" ? "EN" : "中文"}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="mb-3 rounded border border-red-700 bg-red-950/50 text-red-300 text-sm p-2">
          {error}
        </div>
      )}

      {phase === "idle" && (
        <div className="rounded-lg border border-stone-700 bg-stone-900/80 p-5 max-w-2xl">
          <h2 className="font-bold text-parchment mb-1">{cases[0]?.title ?? t.start.loading}</h2>
          <p className="text-sm text-stone-400 mb-4">{cases[0]?.summary}</p>
          <div className="flex items-center gap-4 mb-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" checked={mode === "scripted"} onChange={() => setMode("scripted")} />
              {t.start.scripted}
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={mode === "dynamic"} onChange={() => setMode("dynamic")} />
              {t.start.dynamic}
            </label>
          </div>
          <button
            className="px-4 py-2 rounded bg-amber-700 hover:bg-amber-600 font-semibold disabled:opacity-40"
            onClick={start}
            disabled={!cases.length}
          >
            {t.start.convene}
          </button>
        </div>
      )}

      {phase === "playing" && (
        <>
          <div className="mb-3 text-sm text-stone-400">{charge}</div>
          <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_320px] gap-3">
            <div className="space-y-2">
              {view.jurors.map((j) => (
                <JurorCard
                  key={j.persona.id}
                  juror={j}
                  active={view.activeJurorId === j.persona.id}
                  t={t}
                />
              ))}
            </div>

            <div className="space-y-3">
              <VoteTally
                tally={view.tally}
                status={view.status}
                round={view.round}
                maxRounds={view.maxRounds}
                t={t}
              />
              <TranscriptStream log={view.log} t={t} />
              {view.hint && !view.finished && (
                <div className="rounded border border-amber-700 bg-amber-950/30 text-amber-200 text-sm p-2">
                  💡 {view.hint}
                </div>
              )}
              {view.awaitingHuman && !view.finished && (
                <HumanControls options={view.humanOptions} onAction={onAction} t={t} />
              )}
              {view.finished && view.scorecard && (
                <ScorecardView scorecard={view.scorecard} verdict={view.verdict} t={t} />
              )}
            </div>

            <EvidencePanel
              evidence={view.caseInfo?.evidence ?? []}
              highlighted={view.highlightedEvidence}
              t={t}
            />
          </div>
        </>
      )}
    </div>
  );
}
