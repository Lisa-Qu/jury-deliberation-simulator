export type Vote = "GUILTY" | "NOT_GUILTY" | "UNDECIDED";

export interface Persona {
  id: string;
  name: string;
  archetype: string;
  bias: string;
  initial_leaning: Vote;
  voice: string;
}

export interface Juror {
  persona: Persona;
  vote: Vote;
  speaking_score: number;
  responding_score: number;
  inner_reasoning: string;
  is_human: boolean;
}

export interface CaseInfo {
  id: string;
  title: string;
  charge: string;
  summary: string;
  evidence: string[];
}

export interface Scorecard {
  verdict: string | null;
  total: number;
  dims: Record<string, number>;
  recap: string;
}

/** A flattened, render-friendly deliberation log item. */
export interface LogItem {
  id: number;
  kind:
    | "round"
    | "thinking"
    | "tool_call"
    | "tool_result"
    | "speak"
    | "vote"
    | "hint"
    | "human"
    | "error";
  jurorId?: string;
  name?: string;
  text?: string;
  vote?: Vote;
  query?: string;
  evidenceIds?: number[];
  reason?: string;
  round?: number;
}

export interface ViewState {
  caseInfo: CaseInfo | null;
  jurors: Juror[];
  round: number;
  maxRounds: number;
  log: LogItem[];
  tally: Record<string, number>;
  status: string; // open | unanimous | hung
  awaitingHuman: boolean;
  humanOptions: string[];
  highlightedEvidence: number[];
  activeJurorId: string | null;
  hint: string | null;
  scorecard: Scorecard | null;
  verdict: string | null;
  finished: boolean;
}

/** Raw SSE event from the backend (loosely typed). */
export type GameEvent = { type: string; [k: string]: any };
