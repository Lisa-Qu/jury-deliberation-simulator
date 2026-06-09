import type { Vote } from "./types";

export type Lang = "en" | "zh";

const CHIP_EN: Record<Vote, string> = {
  GUILTY: "GUILTY",
  NOT_GUILTY: "NOT GUILTY",
  UNDECIDED: "UNDECIDED",
};
const CHIP_ZH: Record<Vote, string> = {
  GUILTY: "有罪",
  NOT_GUILTY: "无罪",
  UNDECIDED: "未决",
};

const EN = {
  subtitle: "Multi-agent LLM jury · RAG evidence tool · ReAct · LangChain + Gemini",
  start: {
    scripted: "Scripted jurors (deterministic)",
    dynamic: "LLM-generated jurors",
    convene: "Convene the jury",
    loading: "Loading case…",
    language: "Language",
  },
  deliberation: "Deliberation",
  evidence: "Evidence File",
  retrieved: "retrieved",
  guilty: "Guilty",
  notGuilty: "Not Guilty",
  undecided: "Undecided",
  status: { open: "open", unanimous: "unanimous", hung: "hung" } as Record<string, string>,
  controls: {
    yourTurn: "Your turn, juror.",
    placeholder: "Make your argument to the jury…",
    speak: "Speak",
    voteGuilty: "Vote Guilty",
    voteNotGuilty: "Vote Not Guilty",
    hint: "💡 Hint",
    abstain: "Abstain",
    exit: "Exit",
  },
  juror: { bias: "bias", speaking: "speaking", responding: "responding" },
  verdictLabel: "Verdict",
  dims: {
    persuasiveness: "Persuasiveness",
    evidence_use: "Evidence Use",
    consistency: "Consistency",
    engagement: "Engagement",
    open_mindedness: "Open-mindedness",
  } as Record<string, string>,
  chip: (v: Vote) => CHIP_EN[v] ?? v,
  round: (n: number) => `— Round ${n} —`,
  roundOf: (r: number, m: number) => `Round ${r}/${m}`,
  verdict: (v: string | null) => {
    if (!v) return "—";
    if (v === "hung") return "Hung jury";
    if (v === "exited") return "Exited";
    const [, vote] = v.split(":");
    return `Unanimous — ${CHIP_EN[(vote as Vote)] ?? vote}`;
  },
};

export type T = typeof EN;

const ZH: T = {
  subtitle: "多智能体 LLM 陪审团 · RAG 证据工具 · ReAct · LangChain + Gemini",
  start: {
    scripted: "脚本化陪审员（确定性）",
    dynamic: "LLM 动态生成陪审员",
    convene: "召集陪审团",
    loading: "案件加载中…",
    language: "语言",
  },
  deliberation: "评议",
  evidence: "证据卷宗",
  retrieved: "检索到",
  guilty: "有罪",
  notGuilty: "无罪",
  undecided: "未决",
  status: { open: "进行中", unanimous: "一致裁决", hung: "悬而未决" },
  controls: {
    yourTurn: "轮到你了，陪审员。",
    placeholder: "向陪审团陈述你的论点……",
    speak: "发言",
    voteGuilty: "投有罪",
    voteNotGuilty: "投无罪",
    hint: "💡 提示",
    abstain: "弃权",
    exit: "退出",
  },
  juror: { bias: "偏见", speaking: "发言欲", responding: "回应欲" },
  verdictLabel: "裁决",
  dims: {
    persuasiveness: "说服力",
    evidence_use: "证据运用",
    consistency: "一致性",
    engagement: "参与度",
    open_mindedness: "开放度",
  },
  chip: (v: Vote) => CHIP_ZH[v] ?? v,
  round: (n: number) => `— 第 ${n} 轮 —`,
  roundOf: (r: number, m: number) => `第 ${r}/${m} 轮`,
  verdict: (v: string | null) => {
    if (!v) return "—";
    if (v === "hung") return "悬而未决";
    if (v === "exited") return "已退出";
    const [, vote] = v.split(":");
    return `一致裁决 — ${CHIP_ZH[(vote as Vote)] ?? vote}`;
  },
};

export const TR: Record<Lang, T> = { en: EN, zh: ZH };
