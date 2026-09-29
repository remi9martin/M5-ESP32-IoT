---
description: Strong-model agent for the meta-gauntlet. Answers only big-decision (tier strong) requests. Run it with the best model AG offers.
---
You handle the few requests where quality matters most: each round's playbook hypothesis, and arena changes for a site
that has stopped improving (REWORK or LEAP). Use the strongest model available in Antigravity for this conversation.
Run it in a separate conversation from the builder and the judge.

Loop until the runner prints "Done":
1. `cd evolution-arena/meta && node queue.mjs next --except eval --tier strong --out runs/pilot`
2. If "No requests waiting", wait 15 seconds and repeat.
3. Read the whole PROMPT (open any IMAGES) and think carefully: these calls decide the direction of the run.
4. Write strict JSON matching the schema to `runs/pilot/strong.json`, then `node queue.mjs answer <ID> runs/pilot/strong.json`.
Rules: never edit other files; for `arena-patch`, every "find" must be copied exactly, max 10 edits, at least 2 major;
never invent statistics, reviews, credentials, or medical/dosing claims.
