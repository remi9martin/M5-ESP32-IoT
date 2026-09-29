# Agent notes

## evolution-arena/meta (self-improving meta-gauntlet)
- Real runs only: results come from `node run.mjs`, which boots every page, measures it, and writes a hash-chained
  `ledger.jsonl`. Never write, simulate or summarise rounds that the runner did not produce.
- Model requests are answered through `node queue.mjs` (`.agent/workflows/`: meta-gauntlet = builder on a fast model,
  meta-strong = big decisions on the strongest model, meta-judge = separate judge). Grading must be done by a different conversation than building.
- Do not edit `meta/eval.mjs`, `meta/tasks/`, or anything under `meta/runs/` by hand.
- Tests: `cd evolution-arena/meta && npm test` (mock mode, no model needed).
