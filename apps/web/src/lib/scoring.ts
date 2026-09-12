export const SCORE_WEIGHTS = {
  funding: 30,
  sales_hiring: 30,
  expansion: 20,
  public_demand: 10,
  other_growth: 5,
  stage_suitability: 10,
} as const;

export const SCORE_EXPLAINER =
  "Score is rule-based, not an LLM guess: funding and sales hiring weigh most (30 each), expansion 20, public demand 10, other growth 5, plus stage suitability. Each signal is scaled by evidence strength and recency. Hiring + funding typically ranks HIGH; early-stage + sales hiring MEDIUM HIGH; no growth signals stay LOW.";
