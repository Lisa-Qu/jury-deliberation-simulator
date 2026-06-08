import type { CaseInfo, GameEvent, Juror, LogItem, ViewState, Vote } from "./types";

export function initialState(caseInfo: CaseInfo | null = null): ViewState {
  return {
    caseInfo,
    jurors: [],
    round: 0,
    maxRounds: 0,
    log: [],
    tally: { GUILTY: 0, NOT_GUILTY: 0, UNDECIDED: 0 },
    status: "open",
    awaitingHuman: false,
    humanOptions: [],
    highlightedEvidence: [],
    activeJurorId: null,
    hint: null,
    scorecard: null,
    verdict: null,
    finished: false,
  };
}

function setVote(jurors: Juror[], jurorId: string, vote: Vote): Juror[] {
  return jurors.map((j) => (j.persona.id === jurorId ? { ...j, vote } : j));
}

function push(state: ViewState, item: Omit<LogItem, "id">): LogItem[] {
  return [...state.log, { ...item, id: state.log.length }];
}

/** Pure reducer: (state, SSE event) -> new state. Never mutates inputs. */
export function reduce(state: ViewState, ev: GameEvent): ViewState {
  switch (ev.type) {
    case "game_start":
      return {
        ...state,
        jurors: ev.jurors ?? [],
        round: ev.round ?? 1,
        maxRounds: ev.max_rounds ?? 0,
        tally: ev.tally ?? state.tally,
      };

    case "round_start":
      return {
        ...state,
        round: ev.round,
        highlightedEvidence: [],
        hint: null,
        log: push(state, { kind: "round", round: ev.round }),
      };

    case "thinking":
      return {
        ...state,
        activeJurorId: ev.juror_id,
        log: push(state, { kind: "thinking", jurorId: ev.juror_id, name: ev.name, text: ev.text }),
      };

    case "tool_call":
      return {
        ...state,
        activeJurorId: ev.juror_id,
        log: push(state, {
          kind: "tool_call",
          jurorId: ev.juror_id,
          name: ev.name,
          query: ev.query,
        }),
      };

    case "tool_result":
      return {
        ...state,
        highlightedEvidence: ev.evidence_ids ?? [],
        log: push(state, {
          kind: "tool_result",
          jurorId: ev.juror_id,
          name: ev.name,
          evidenceIds: ev.evidence_ids ?? [],
        }),
      };

    case "speak":
      return {
        ...state,
        activeJurorId: ev.juror_id,
        jurors: setVote(state.jurors, ev.juror_id, ev.vote),
        log: push(state, {
          kind: "speak",
          jurorId: ev.juror_id,
          name: ev.name,
          text: ev.text,
          vote: ev.vote,
        }),
      };

    case "awaiting_human":
      return {
        ...state,
        awaitingHuman: true,
        activeJurorId: "you",
        humanOptions: ev.options ?? [],
      };

    case "human_action": {
      const next = { ...state, awaitingHuman: false };
      if (ev.action === "SPEAK" && ev.text) {
        return { ...next, log: push(state, { kind: "human", name: "You", text: ev.text }) };
      }
      return next;
    }

    case "hint":
      return { ...state, hint: ev.text, log: push(state, { kind: "hint", text: ev.text }) };

    case "vote":
      return {
        ...state,
        jurors: setVote(state.jurors, ev.juror_id, ev.vote),
        log: push(state, {
          kind: "vote",
          jurorId: ev.juror_id,
          name: ev.name,
          vote: ev.vote,
          reason: ev.reason,
        }),
      };

    case "tally":
      return { ...state, tally: ev.votes ?? state.tally, status: ev.status ?? state.status };

    case "scorecard":
      return {
        ...state,
        verdict: ev.verdict ?? null,
        jurors: ev.jurors ?? state.jurors,
        tally: ev.tally ?? state.tally,
        scorecard: { verdict: ev.verdict ?? null, total: ev.total, dims: ev.dims, recap: ev.recap },
      };

    case "done":
      return { ...state, finished: true, awaitingHuman: false, activeJurorId: null };

    case "error":
      return {
        ...state,
        log: push(state, { kind: "error", text: `[${ev.stage}] ${ev.message}` }),
      };

    default:
      return state;
  }
}
