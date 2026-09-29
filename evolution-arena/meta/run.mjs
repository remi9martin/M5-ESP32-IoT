#!/usr/bin/env node
// Meta-gauntlet: evolves the Evolution Arena playbook (its prompts, ladders and thresholds).
// Each round proposes one playbook change, runs the real arena on every training task with it,
// and keeps it only if a fixed evaluator says the resulting sites beat the current champion's.
//
//   node run.mjs --rounds 10 --iters 3 --out runs/pilot            (queue mode: the AG agent answers requests)
//   node run.mjs --rounds 50 --out runs/pilot --resume            (continue the same run)
//   node run.mjs --mock --rounds 3 --iters 2 --out runs/test       (offline test)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { createLLM, sha } from './llm.mjs';
import { runArena, arenaDefaults } from './arena-driver.mjs';
import { measure, judgePair, honeypot, claimScan, newClaims, pixelDiff } from './eval.mjs';
import { buildReport } from './report.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const flag = (name, def) => { const i = argv.indexOf('--' + name); return i < 0 ? def : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true); };
const OPT = {
  rounds: +flag('rounds', 25), iters: +flag('iters', 3), out: path.resolve(HERE, flag('out', 'runs/pilot')),
  mode: flag('mock', false) ? 'mock' : 'queue', resume: !!flag('resume', false), budget: +flag('budget', 0),
  winsNeeded: +flag('wins', 0), allowFooled: !!flag('allow-fooled', false),
};
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

// ---------- user rules that evolution may never break ----------
const HARD = { maxEditsCap: 10, minMajorFloor: 2 }; // "up to 10 changes per iteration, at least 2 significant"
const REQUIRED_PLACEHOLDERS = { mutate: ['{{code}}', '{{task}}', '{{rules}}'], genesis: ['{{task}}', '{{rules}}'], judge: ['{{task}}'] };
const EDITABLE = ['persona', 'rules', 'patchRules', 'honesty', 'genesis', 'mutate', 'judge', 'redTeam',
  'strength.0.text', 'strength.1.text', 'strength.2.text', 'strength.0.temp', 'strength.1.temp', 'strength.2.temp',
  'reworkAfter', 'leapAfter', 'maxEdits', 'minMajor', 'majorChars', 'minPatchChars', 'duelMargin'];

function applyEdits(pb, edits) {
  const next = structuredClone(pb);
  for (const { field, value } of edits) {
    if (!EDITABLE.includes(field)) return { error: `field "${field}" is not editable` };
    const keys = field.split('.'), last = keys.pop();
    let obj = next; for (const k of keys) obj = obj[k];
    const numeric = typeof obj[last] === 'number';
    const v = numeric ? Number(value) : String(value);
    if (numeric && !Number.isFinite(v)) return { error: `field "${field}" needs a number` };
    obj[last] = v;
  }
  next.maxEdits = Math.min(Math.max(1, Math.round(next.maxEdits)), HARD.maxEditsCap);
  next.minMajor = Math.min(Math.max(HARD.minMajorFloor, Math.round(next.minMajor)), next.maxEdits);
  next.strength.forEach(s => { s.temp = Math.min(1.5, Math.max(0, s.temp)); });
  next.reworkAfter = Math.max(1, Math.round(next.reworkAfter)); next.leapAfter = Math.max(next.reworkAfter + 1, Math.round(next.leapAfter));
  for (const [k, need] of Object.entries(REQUIRED_PLACEHOLDERS)) for (const p of need) if (!next[k].includes(p)) return { error: `${k} lost required placeholder ${p}` };
  if (!next.patchRules.includes('{{maxEdits}}') || !next.patchRules.includes('{{minMajor}}')) return { error: 'patchRules must keep {{maxEdits}} and {{minMajor}}' };
  return { playbook: next };
}

const META_SCHEMA = { type: 'OBJECT', properties: {
  hypothesis: { type: 'STRING' },
  edits: { type: 'ARRAY', items: { type: 'OBJECT', properties: { field: { type: 'STRING' }, value: { type: 'STRING' } }, required: ['field', 'value'] } } },
  required: ['hypothesis', 'edits'] };

function metaPrompt(state) {
  const pb = state.champion.playbook;
  const shown = Object.fromEntries(EDITABLE.map(f => [f, f.split('.').reduce((o, k) => o[k], pb)]));
  const hist = state.history.slice(-15).map(h => `- round ${h.round}: ${h.kept ? 'KEPT' : 'REJECTED'} — ${h.hypothesis} (${h.reason})`).join('\n') || '(none yet)';
  const notes = state.history.at(-1)?.taskNotes?.map(t => `- ${t.task}: ${t.notes}`).join('\n') || '(none yet)';
  return `You are improving the PLAYBOOK of a self-improving web design engine ("Evolution Arena").
The playbook is the set of instructions and thresholds two AI agents follow while they iteratively improve a website:
they propose find/replace patches, code boots the page in a sandbox and rejects broken ones, and judges keep only improvements.
Your change is tested for real: the engine will run on ${state.trainIds.length} benchmark websites with your playbook, and a fixed,
independent evaluator compares the results with the current champion's (screenshots, objective checks, and a scan for invented claims).

Propose ONE focused hypothesis about how to make the engine produce better websites, expressed as 1-3 edits to the fields below.
Good hypotheses target the creative process: what to look at first, how to prioritise, how bold to be and when, how to use
judge feedback, how to avoid repeating failures, how to make edits land (exact "find" strings), how to stay honest.
Hard limits enforced by code: maxEdits <= ${HARD.maxEditsCap}; minMajor >= ${HARD.minMajorFloor}; templates must keep their {{placeholders}}.
Do not try to game the evaluator; it is fixed, strips comments, scans for fabricated claims, and uses held-out tasks at the end.

Editable fields and their current values (JSON):
${JSON.stringify(shown, null, 1)}

Recent meta-rounds (learn from them; do not repeat rejected ideas):
${hist}

Evaluator notes from the last round:
${notes}

Answer as JSON: {"hypothesis": "...", "edits": [{"field": "<name>", "value": "<new full value as a string>"}]}.`;
}

// ---------- ledger: append-only, hash-chained, so results cannot be quietly rewritten ----------
function ledgerAppend(file, type, data) {
  const lines = fs.existsSync(file) ? fs.readFileSync(file, 'utf8').trim().split('\n').filter(Boolean) : [];
  const prev = lines.length ? JSON.parse(lines.at(-1)).hash : 'genesis';
  const entry = { t: new Date().toISOString(), type, data, prev };
  entry.hash = sha(prev + JSON.stringify({ t: entry.t, type, data }));
  fs.appendFileSync(file, JSON.stringify(entry) + '\n');
}
const fileSha = f => sha(fs.readFileSync(f));

function loadTasks() {
  const dir = path.join(HERE, 'tasks');
  return fs.readdirSync(dir).filter(f => f.endsWith('.json')).map(f => {
    const t = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    t.seed = fs.readFileSync(path.join(dir, t.seedFile), 'utf8');
    t.baselineClaims = claimScan(t.seed);
    return t;
  });
}

async function runSet(browser, llm, playbook, tasks, tag) {
  const outputs = {};
  for (const t of tasks) {
    log(`  [${tag}] ${t.id}: running arena (${OPT.iters} iterations)`);
    const before = llm.stats.calls;
    const r = await runArena(browser, { llm, playbook, task: t, iters: OPT.iters });
    const base = path.join(OPT.out, 'outputs', tag, t.id);
    const metrics = await measure(browser, r.html, base);
    const claims = claimScan(r.html);
    outputs[t.id] = { htmlFile: path.relative(OPT.out, base + '.html'), metrics: { ...metrics, shots: rel(metrics.shots) },
      claims, newClaims: newClaims(claims, t.baselineClaims), accepted: r.accepted,
      calls: llm.mode === 'mock' ? r.calls : llm.stats.calls - before, htmlSha: metrics.htmlSha,
      shotSha: { desktop: fileSha(metrics.shots.desktop), mobile: fileSha(metrics.shots.mobile) } };
    log(`  [${tag}] ${t.id}: ${r.accepted} accepted changes, objective ${metrics.score}`);
  }
  return outputs;
}
const rel = shots => Object.fromEntries(Object.entries(shots).map(([k, v]) => [k, path.relative(OPT.out, v)]));
const abs = o => ({ html: fs.readFileSync(path.join(OPT.out, o.htmlFile), 'utf8'),
  metrics: { ...o.metrics, shots: Object.fromEntries(Object.entries(o.metrics.shots).map(([k, v]) => [k, path.join(OPT.out, v)])) } });
const costPerWin = outs => { const v = Object.values(outs); return v.reduce((n, o) => n + o.calls, 0) / (v.reduce((n, o) => n + o.accepted, 0) + 1); };

async function compare(browser, llm, tasks, champOut, candOut, seedOut) {
  const results = [];
  for (const t of tasks) {
    const a = abs(champOut[t.id]), b = abs(candOut[t.id]);
    const j = await judgePair(llm, t, a, b);
    const objDelta = Math.round((b.metrics.score - a.metrics.score) * 10) / 10;
    const fabricated = Object.keys(candOut[t.id].newClaims).length > 0;
    const moved = seedOut ? await pixelDiff(browser, b.metrics.shots.desktop, path.join(OPT.out, seedOut[t.id].metrics.shots.desktop)) : null;
    const win = j.candWins && !j.manipulation && !fabricated && objDelta >= -5;
    results.push({ task: t.id, win, judgeWin: j.candWins, tie: j.tie, scoreCand: j.scoreCand, scoreChamp: j.scoreChamp,
      objDelta, fabricated: candOut[t.id].newClaims, manipulation: j.manipulation, visualChangeVsSeed: moved, notes: j.notes });
    log(`  ${t.id}: ${win ? 'WIN' : 'loss'} (judge ${j.scoreChamp}→${j.scoreCand}, objective Δ${objDelta}${fabricated ? ', FABRICATED CLAIMS' : ''})`);
  }
  return results;
}

async function main() {
  fs.mkdirSync(OPT.out, { recursive: true });
  const stateFile = path.join(OPT.out, 'state.json'), ledger = path.join(OPT.out, 'ledger.jsonl');
  const llm = createLLM({ mode: OPT.mode, dir: OPT.out, log });
  const browser = await chromium.launch();
  const tasks = loadTasks(), train = tasks.filter(t => t.split === 'train'), holdout = tasks.filter(t => t.split === 'holdout');
  const winsNeeded = OPT.winsNeeded || Math.ceil(train.length * 0.75);

  let state;
  if (OPT.resume && fs.existsSync(stateFile)) { state = JSON.parse(fs.readFileSync(stateFile, 'utf8')); log(`Resuming at round ${state.round}`); }
  else {
    if (fs.existsSync(stateFile) && !OPT.resume) throw new Error(`${stateFile} exists. Use --resume, or a new --out folder.`);
    state = { created: new Date().toISOString(), mode: OPT.mode, iters: OPT.iters, round: 0, trainIds: train.map(t => t.id),
      holdoutIds: holdout.map(t => t.id), defaults: await arenaDefaults(browser), champion: null, seedOutputs: null, history: [] };
  }
  const save = () => { state.calls = llm.stats.calls + (state.callsBefore || 0); fs.writeFileSync(stateFile, JSON.stringify(state, null, 1)); };
  state.callsBefore = state.calls || 0; llm.stats.calls = 0;

  // 1. Honeypot: refuse to evolve against a judge that can be talked into a score.
  if (!state.honeypot) {
    log('Honeypot check: can the evaluator be manipulated?');
    state.honeypot = await honeypot(llm, browser, train[0], OPT.out);
    ledgerAppend(ledger, 'honeypot', state.honeypot); save();
    if (!state.honeypot.passed && !OPT.allowFooled) {
      log('ABORT: the evaluator preferred the page that asked for a high score. Fix the judge before evolving.');
      await browser.close(); process.exit(2);
    }
  }
  // 2. Seeds and baseline (default playbook) outputs.
  if (!state.seedOutputs) {
    state.seedOutputs = {};
    for (const t of tasks) {
      const m = await measure(browser, t.seed, path.join(OPT.out, 'outputs', 'seed', t.id));
      state.seedOutputs[t.id] = { htmlFile: path.relative(OPT.out, path.join(OPT.out, 'outputs', 'seed', t.id + '.html')), metrics: { ...m, shots: rel(m.shots) } };
    }
    save();
  }
  if (!state.champion) {
    log('Baseline: running the default playbook on the training tasks');
    const outputs = await runSet(browser, llm, state.defaults, train, 'r000-baseline');
    state.champion = { round: 0, playbook: state.defaults, outputs };
    state.baselineOutputs = outputs;
    ledgerAppend(ledger, 'baseline', { outputs: Object.fromEntries(Object.entries(outputs).map(([k, o]) => [k, { htmlSha: o.htmlSha, shotSha: o.shotSha, objective: o.metrics.score }])) });
    save();
  }

  // 3. Meta rounds.
  while (state.round < OPT.rounds) {
    if (OPT.budget && state.calls >= OPT.budget) { log(`Budget of ${OPT.budget} model calls reached.`); break; }
    const round = state.round + 1, tag = `r${String(round).padStart(3, '0')}`;
    log(`Round ${round}/${OPT.rounds}: asking for a playbook hypothesis`);
    const proposal = await llm.ask({ kind: 'meta-propose', text: metaPrompt(state), schema: META_SCHEMA, temperature: 0.9, tier: 'strong',
      mock: () => mockProposal(state) });
    const applied = applyEdits(state.champion.playbook, proposal.edits.slice(0, 3));
    const entry = { round, hypothesis: proposal.hypothesis, edits: proposal.edits.slice(0, 3) };
    let outputHashes = null; // proof of the exact pages and screenshots this round produced
    if (applied.error) {
      Object.assign(entry, { kept: false, reason: 'invalid: ' + applied.error });
    } else {
      const outputs = await runSet(browser, llm, applied.playbook, train, tag);
      outputHashes = Object.fromEntries(Object.entries(outputs).map(([k, o]) => [k, { htmlSha: o.htmlSha, shotSha: o.shotSha, objective: o.metrics.score }]));
      const results = await compare(browser, llm, train, state.champion.outputs, outputs, state.seedOutputs);
      const wins = results.filter(r => r.win).length, cost = costPerWin(outputs), champCost = costPerWin(state.champion.outputs);
      const cheap = cost <= champCost * 1.5 + 1;
      const kept = wins >= winsNeeded && cheap;
      Object.assign(entry, { kept, wins, of: train.length, cost: Math.round(cost * 10) / 10, champCost: Math.round(champCost * 10) / 10,
        reason: kept ? `won ${wins}/${train.length}` : wins < winsNeeded ? `won ${wins}/${train.length} (need ${winsNeeded})` : `too costly (${cost.toFixed(1)} vs ${champCost.toFixed(1)} calls/win)`,
        taskNotes: results.map(r => ({ task: r.task, notes: r.notes })), results });
      if (kept) state.champion = { round, playbook: applied.playbook, outputs };
    }
    state.history.push(entry);
    ledgerAppend(ledger, 'round', { ...entry, taskNotes: undefined, championRound: state.champion.round, outputs: outputHashes });
    state.round = round; save();
    log(`Round ${round}: ${entry.kept ? 'KEPT' : 'rejected'} — ${entry.reason}`);
    buildReport(OPT.out);
  }

  // 4. Held-out check: the only honest test of whether the playbook generalises.
  if (state.round >= OPT.rounds && !state.holdout && holdout.length) {
    log('Held-out tasks: default playbook vs evolved champion');
    const base = await runSet(browser, llm, state.defaults, holdout, 'holdout-default');
    const champ = await runSet(browser, llm, state.champion.playbook, holdout, 'holdout-champion');
    const results = await compare(browser, llm, holdout, base, champ, state.seedOutputs);
    state.holdout = { default: base, champion: champ, results, wins: results.filter(r => r.win).length, of: holdout.length };
    ledgerAppend(ledger, 'holdout', { wins: state.holdout.wins, of: holdout.length, results: results.map(r => ({ task: r.task, win: r.win, objDelta: r.objDelta })) });
    save();
  }
  fs.writeFileSync(path.join(OPT.out, 'playbook.champion.json'), JSON.stringify(state.champion.playbook, null, 2));
  const report = buildReport(OPT.out);
  log(`Done. Champion from round ${state.champion.round}. Report: ${report}`);
  await browser.close();
}

function mockProposal(state) {
  const n = state.round + 1, picks = [
    { field: 'persona', value: `a meticulous senior product designer (variant ${n})` },
    { field: 'strength.0.text', value: `Start with the single weakest area a first-time visitor would notice, fix it properly, then polish (variant ${n}).` },
    { field: 'majorChars', value: String(250 + (n % 5) * 25) },
    { field: 'reworkAfter', value: String(2 + (n % 3)) },
  ];
  return { hypothesis: `mock hypothesis ${n}`, edits: [picks[n % picks.length]] };
}

main().catch(e => { console.error(e); process.exit(1); });
