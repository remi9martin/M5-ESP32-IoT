# Meta-gauntlet

A gauntlet for the gauntlet. It evolves the Evolution Arena **playbook**: the prompts, strength ladder,
patch rules and thresholds that decide how the arena improves a website. It then proves on a fixed benchmark
whether each change makes the arena produce better sites.

It is built to be **real and hard to fool**:
- **Code does the work.** Every candidate playbook runs the real arena (`../index.html`) in headless Chromium. Pages
  are booted, patched, rolled back and measured by code.
- **A fixed evaluator** (`eval.mjs`) that the playbook can never change. It has three parts:
  - objective checks at desktop and mobile sizes: JS errors, mobile overflow, contrast, tap targets, weight
  - a scan for invented claims: credentials, dosing, made-up numbers, guarantees
  - a blind, randomised side-by-side comparison judged mainly from screenshots, with comments stripped from the code
- **A honeypot** at the start: if the judge prefers a page that asks AI judges for a perfect score, the run aborts.
- **Held-out tasks** (docs page, mobile checkout) are never used during evolution. They are the final test of whether
  the improvements are general or just overfit to the training tasks.
- **A tamper-evident record:** `ledger.jsonl` is hash-chained, and every scored page and screenshot is hashed. `report.html`
  says NOT VERIFIED if anything was altered or is missing.
- **Visual change is measured**, so a run where the sites look the same shows up as small pixel differences.

## User rules enforced in code
- The arena may make at most 10 edits per iteration, and at least 2 of them must be major (300+ characters changed).
- Evolution can tune these numbers within those limits but can never break them.

## Run it (Antigravity, no API key)
Use the two workflows in `.agent/workflows/`:
- `meta-gauntlet` is the builder. It starts the runner and answers requests.
- `meta-judge` is the independent judge, run in a separate conversation.

Manually:
```
npm install && npx playwright install chromium
node run.mjs --rounds 10 --iters 3 --out runs/pilot          # pilot
node run.mjs --rounds 50 --iters 3 --out runs/pilot --resume # extend the same run to 50
node queue.mjs next | answer <id> <file>                      # answer requests
node report.mjs runs/pilot                                    # verify + rebuild the report
npm test                                                      # smoke tests in mock mode
```
Cost: about 45–50 model answers per round with 4 training tasks and 3 iterations each. Use `--budget N` to cap it.
The final playbook is written to `runs/<name>/playbook.champion.json`. Load it in the arena with **Import playbook**.
