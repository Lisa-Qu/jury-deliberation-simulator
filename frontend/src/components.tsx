import { useEffect, useRef, useState } from "react";
import type { T } from "./i18n";
import type { Juror, LogItem, Scorecard, Vote } from "./types";

const VOTE_STYLE: Record<Vote, string> = {
  GUILTY: "bg-red-900/70 text-red-200 border-red-600",
  NOT_GUILTY: "bg-emerald-900/70 text-emerald-200 border-emerald-600",
  UNDECIDED: "bg-stone-700/70 text-stone-300 border-stone-500",
};

function VoteChip({ vote, t }: { vote: Vote; t: T }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${VOTE_STYLE[vote]}`}>
      {t.chip(vote)}
    </span>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-1 text-[10px] text-stone-400">
      <span className="w-16 shrink-0">{label}</span>
      <div className="h-1.5 flex-1 bg-stone-800 rounded">
        <div className="h-full bg-amber-600 rounded" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

export function JurorCard({ juror, active, t }: { juror: Juror; active: boolean; t: T }) {
  const p = juror.persona;
  return (
    <div
      className={`rounded-lg border p-3 transition bg-stone-900/80 ${
        active ? "border-amber-500 shadow-lg shadow-amber-900/40" : "border-stone-700"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-parchment">{p.name}</span>
        <VoteChip vote={juror.vote} t={t} />
      </div>
      <div className="text-xs text-stone-400 mt-0.5">{p.archetype}</div>
      {!juror.is_human && <div className="text-[10px] text-amber-700 mt-1 italic">{t.juror.bias}: {p.bias}</div>}
      {!juror.is_human && (
        <div className="mt-2 space-y-1">
          <Bar label={t.juror.speaking} value={juror.speaking_score} />
          <Bar label={t.juror.responding} value={juror.responding_score} />
        </div>
      )}
      {!juror.is_human && juror.opinion != null && (
        <div className="mt-1 space-y-1 border-t border-stone-800 pt-1">
          <Bar label={t.belief.lean} value={(juror.opinion + 1) / 2} />
          <Bar label={t.belief.conviction} value={juror.conviction ?? 0} />
        </div>
      )}
      {active && juror.inner_reasoning && (
        <div className="mt-2 text-[11px] text-stone-300 bg-stone-800/80 rounded p-1.5 italic">
          💭 {juror.inner_reasoning}
        </div>
      )}
    </div>
  );
}

export function EvidencePanel({
  evidence,
  highlighted,
  t,
}: {
  evidence: string[];
  highlighted: number[];
  t: T;
}) {
  const hi = new Set(highlighted);
  return (
    <div className="rounded-lg border border-stone-700 bg-stone-900/80 p-3">
      <h3 className="font-semibold text-parchment mb-2">📁 {t.evidence}</h3>
      <div className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1">
        {evidence.map((e, i) => (
          <div
            key={i}
            className={`text-xs rounded border p-1.5 transition ${
              hi.has(i) ? "evidence-hit bg-amber-950/40 border-amber-600" : "border-stone-800 text-stone-400"
            }`}
          >
            {e}
          </div>
        ))}
      </div>
    </div>
  );
}

const KIND_ICON: Record<string, string> = {
  thinking: "💭",
  tool_call: "🔧",
  tool_result: "📄",
  speak: "🗣️",
  vote: "🗳️",
  hint: "💡",
  human: "🧑‍⚖️",
  error: "⚠️",
  belief_update: "🧠",
  strategy: "🎯",
  metrics: "📊",
  reflection: "🪞",
};

export function TranscriptStream({ log, t }: { log: LogItem[]; t: T }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [log.length]);

  return (
    <div ref={ref} className="rounded-lg border border-stone-700 bg-stone-900/80 p-3 h-[60vh] overflow-y-auto">
      <h3 className="font-semibold text-parchment mb-2 sticky top-0 bg-stone-900/95 py-1">
        ⚖️ {t.deliberation}
      </h3>
      <div className="space-y-1.5">
        {log.map((it) => {
          if (it.kind === "round")
            return (
              <div key={it.id} className="text-center text-amber-500 text-xs font-bold my-2">
                {t.round(it.round ?? 0)}
              </div>
            );
          if (it.kind === "tool_call")
            return (
              <div key={it.id} className="text-xs text-amber-300 pl-4">
                🔧 {it.name} → lookup_evidence(<span className="italic">"{it.query}"</span>)
              </div>
            );
          if (it.kind === "tool_result")
            return (
              <div key={it.id} className="text-xs text-amber-200 pl-4">
                📄 {t.retrieved} {(it.evidenceIds ?? []).map((i) => `E${i + 1}`).join(", ")}
              </div>
            );
          if (it.kind === "thinking")
            return (
              <div key={it.id} className="text-xs text-stone-500 italic pl-4">
                💭 {it.name}: {it.text}
              </div>
            );
          if (it.kind === "reflection")
            return (
              <div key={it.id} className="text-xs text-sky-400/80 italic pl-4">
                🪞 {it.name}: {it.text}
              </div>
            );
          if (it.kind === "belief_update")
            return (
              <div key={it.id} className="text-xs text-purple-300 pl-4">
                🧠 {it.name} → {it.stance} ({(it.delta ?? 0) >= 0 ? "+" : ""}{it.delta})
              </div>
            );
          if (it.kind === "strategy")
            return (
              <div key={it.id} className="text-xs text-teal-300 pl-4">
                🎯 {it.name} {t.strategy.targets} {it.target} · {t.strategy.tactic[it.tactic ?? "assert"] ?? it.tactic}
                {it.targetPoint ? ` (${it.targetPoint})` : ""}
              </div>
            );
          if (it.kind === "metrics")
            return (
              <div key={it.id} className="text-xs text-amber-400 border-t border-stone-700 mt-1 pt-1">
                📊 {t.metrics.convergence} {it.convergence} · {t.metrics.polarization} {it.polarization}
                {it.topInfluencer ? ` · ${t.metrics.top}: ${it.topInfluencer}` : ""}
              </div>
            );
          return (
            <div key={it.id} className="text-sm">
              <span className="mr-1">{KIND_ICON[it.kind] ?? "•"}</span>
              {it.name && <span className="font-semibold text-parchment">{it.name}</span>}
              {it.vote && <span className="ml-1"><VoteChip vote={it.vote} t={t} /></span>}{" "}
              <span className={it.kind === "error" ? "text-red-400" : "text-stone-300"}>
                {it.text || it.reason}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function HumanControls({
  options,
  onAction,
  t,
}: {
  options: string[];
  onAction: (action: string, text?: string) => void;
  t: T;
}) {
  const [text, setText] = useState("");
  const has = (o: string) => options.includes(o);
  return (
    <div className="rounded-lg border border-amber-700 bg-stone-900 p-3 space-y-2">
      <div className="font-semibold text-amber-400">{t.controls.yourTurn}</div>
      {has("SPEAK") && (
        <div className="flex gap-2">
          <input
            className="flex-1 bg-stone-800 border border-stone-600 rounded px-2 py-1 text-sm text-parchment"
            placeholder={t.controls.placeholder}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && text.trim()) {
                onAction("SPEAK", text.trim());
                setText("");
              }
            }}
          />
          <button
            className="px-3 py-1 rounded bg-amber-700 hover:bg-amber-600 text-sm disabled:opacity-40"
            disabled={!text.trim()}
            onClick={() => {
              onAction("SPEAK", text.trim());
              setText("");
            }}
          >
            {t.controls.speak}
          </button>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {has("VOTE") && (
          <>
            <button
              className="px-3 py-1 rounded border border-red-600 text-red-300 hover:bg-red-900/40 text-sm"
              onClick={() => onAction("VOTE", "GUILTY")}
            >
              {t.controls.voteGuilty}
            </button>
            <button
              className="px-3 py-1 rounded border border-emerald-600 text-emerald-300 hover:bg-emerald-900/40 text-sm"
              onClick={() => onAction("VOTE", "NOT_GUILTY")}
            >
              {t.controls.voteNotGuilty}
            </button>
          </>
        )}
        {has("HINT") && (
          <button
            className="px-3 py-1 rounded border border-amber-600 text-amber-300 hover:bg-amber-900/40 text-sm"
            onClick={() => onAction("HINT")}
          >
            {t.controls.hint}
          </button>
        )}
        {has("REJECT") && (
          <button
            className="px-3 py-1 rounded border border-stone-600 text-stone-300 hover:bg-stone-800 text-sm"
            onClick={() => onAction("REJECT")}
          >
            {t.controls.abstain}
          </button>
        )}
        {has("EXIT") && (
          <button
            className="px-3 py-1 rounded border border-stone-600 text-stone-400 hover:bg-stone-800 text-sm"
            onClick={() => onAction("EXIT")}
          >
            {t.controls.exit}
          </button>
        )}
      </div>
    </div>
  );
}

export function VoteTally({
  tally,
  status,
  round,
  maxRounds,
  t,
}: {
  tally: Record<string, number>;
  status: string;
  round: number;
  maxRounds: number;
  t: T;
}) {
  return (
    <div className="rounded-lg border border-stone-700 bg-stone-900/80 p-3 flex items-center justify-between text-sm">
      <span className="text-stone-400">{t.roundOf(round, maxRounds)}</span>
      <div className="flex gap-3">
        <span className="text-red-300">{t.guilty} {tally.GUILTY ?? 0}</span>
        <span className="text-emerald-300">{t.notGuilty} {tally.NOT_GUILTY ?? 0}</span>
        <span className="text-stone-400">{t.undecided} {tally.UNDECIDED ?? 0}</span>
      </div>
      <span className="uppercase text-xs text-amber-500">{t.status[status] ?? status}</span>
    </div>
  );
}

export function ScorecardView({
  scorecard,
  verdict,
  t,
}: {
  scorecard: Scorecard;
  verdict: string | null;
  t: T;
}) {
  return (
    <div className="rounded-lg border border-amber-600 bg-stone-900 p-4 space-y-3">
      <div className="text-lg font-bold text-amber-400">
        {t.verdictLabel}: {t.verdict(verdict)}
      </div>
      <div className="text-3xl font-black text-parchment">
        {scorecard.total}
        <span className="text-base text-stone-500">/100</span>
      </div>
      <div className="space-y-1">
        {Object.entries(scorecard.dims ?? {}).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs">
            <span className="w-32 text-stone-400">{t.dims[k] ?? k}</span>
            <div className="h-2 flex-1 bg-stone-800 rounded">
              <div className="h-full bg-amber-500 rounded" style={{ width: `${v}%` }} />
            </div>
            <span className="w-8 text-right text-stone-300">{v}</span>
          </div>
        ))}
      </div>
      <p className="text-sm text-stone-300 italic border-t border-stone-700 pt-2">{scorecard.recap}</p>
    </div>
  );
}
