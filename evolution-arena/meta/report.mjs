#!/usr/bin/env node
// Builds <run>/report.html from state.json + ledger.jsonl, and verifies the run is real:
// the ledger hash chain must be intact and every recorded page/screenshot hash must match the files on disk.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sha } from './llm.mjs';

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function verify(dir) {
  const problems = [];
  const lines = fs.readFileSync(path.join(dir, 'ledger.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l));
  let prev = 'genesis';
  lines.forEach((e, i) => {
    if (e.prev !== prev) problems.push(`ledger entry ${i + 1}: chain broken`);
    if (sha(e.prev + JSON.stringify({ t: e.t, type: e.type, data: e.data })) !== e.hash) problems.push(`ledger entry ${i + 1}: contents altered`);
    prev = e.hash;
  });
  const state = JSON.parse(fs.readFileSync(path.join(dir, 'state.json'), 'utf8'));
  const check = (label, outputs) => Object.entries(outputs || {}).forEach(([task, o]) => {
    const f = path.join(dir, o.htmlFile);
    if (!fs.existsSync(f)) return problems.push(`${label}/${task}: page file missing`);
    if (sha(fs.readFileSync(f, 'utf8')) !== o.htmlSha) problems.push(`${label}/${task}: page changed after it was scored`);
    for (const [v, s] of Object.entries(o.shotSha || {})) {
      const shot = path.join(dir, o.metrics.shots[v]);
      if (!fs.existsSync(shot) || sha(fs.readFileSync(shot)) !== s) problems.push(`${label}/${task}: ${v} screenshot missing or altered`);
    }
  });
  check('champion', state.champion?.outputs);
  check('baseline', state.baselineOutputs);
  return { ok: problems.length === 0, problems, entries: lines.length };
}

export function buildReport(dir) {
  const state = JSON.parse(fs.readFileSync(path.join(dir, 'state.json'), 'utf8'));
  const v = verify(dir);
  const H = state.history || [], kept = H.filter(h => h.kept);
  // Fitness line: judge score of the champion over rounds (avg across tasks of the kept candidate's score).
  let level = null; const pts = [];
  for (const h of H) { if (h.kept && h.results) level = h.results.reduce((n, r) => n + r.scoreCand, 0) / h.results.length; pts.push({ r: h.round, level, kept: h.kept, wins: h.wins ?? 0, of: h.of ?? 0 }); }
  const W = 640, Hh = 120, maxR = Math.max(1, H.length);
  const winBars = pts.map(p => `<rect x="${((p.r - 1) / maxR) * W + 1}" y="${Hh - (p.of ? (p.wins / p.of) * Hh : 0)}" width="${Math.max(2, W / maxR - 2)}" height="${p.of ? (p.wins / p.of) * Hh : 0}" rx="2" fill="${p.kept ? 'var(--good)' : 'var(--muted-bar)'}"><title>Round ${p.r}: ${p.wins}/${p.of} tasks won${p.kept ? ' (kept)' : ''}</title></rect>`).join('');
  const tasks = Object.keys(state.seedOutputs || {});
  const trainIds = state.trainIds || [];
  const img = p => p ? `<img loading="lazy" src="${esc(p)}" alt="">` : '<div class="empty">not run</div>';
  const compareRow = id => {
    const seed = state.seedOutputs[id], champ = state.champion?.outputs?.[id];
    const hold = state.holdout?.champion?.[id], holdDef = state.holdout?.default?.[id];
    const cols = trainIds.includes(id)
      ? [['Starting page', seed], ['Default playbook (round 0)', state.baselineOutputs?.[id]], [`Evolved champion (round ${state.champion?.round})`, champ]]
      : [['Starting page', seed], ['Default playbook', holdDef], ['Evolved playbook', hold]];
    return `<section class="task"><h3>${esc(id)} <span class="tag">${trainIds.includes(id) ? 'training' : 'held-out'}</span></h3>
      <div class="shots">${cols.map(([label, o]) => `<figure>${img(o?.metrics?.shots?.desktop)}<figcaption>${esc(label)}${o?.metrics ? ` · objective ${o.metrics.score}` : ''}</figcaption></figure>`).join('')}</div></section>`;
  };
  const diffFields = () => {
    const a = state.defaults, b = state.champion?.playbook; if (!a || !b) return '';
    const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => typeof v === 'object' && v ? flat(v, p + k + '.') : [[p + k, v]]);
    const A = Object.fromEntries(flat(a));
    const rows = flat(b).filter(([k, v]) => A[k] !== v);
    return rows.length ? rows.map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(A[k])}</td><td>${esc(v)}</td></tr>`).join('') : '<tr><td colspan="3">No changes yet: the default playbook is still the champion.</td></tr>';
  };
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meta-Gauntlet Report</title>
<style>
:root{--bg:#fbfbfa;--panel:#fff;--ink:#16181d;--dim:#667085;--line:#e6e7ea;--good:#138a5e;--bad:#c2410c;--muted-bar:#d0d4db;--accent:#2f5bea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1014;--panel:#161920;--ink:#e8eaee;--dim:#9aa3b2;--line:#262a33;--good:#3ecf8e;--bad:#fb923c;--muted-bar:#3a404c;--accent:#7c9cff}}
:root[data-theme="dark"]{--bg:#0e1014;--panel:#161920;--ink:#e8eaee;--dim:#9aa3b2;--line:#262a33;--good:#3ecf8e;--bad:#fb923c;--muted-bar:#3a404c;--accent:#7c9cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 16px 64px}h1{font-size:30px;letter-spacing:-.02em;margin:0 0 6px}h2{font-size:19px;margin:40px 0 12px}h3{font-size:15px;margin:0 0 10px}
.dim{color:var(--dim)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}.kpi b{display:block;font-size:24px;letter-spacing:-.02em}.kpi span{font-size:13px;color:var(--dim)}
.verdict{margin-top:20px;padding:14px 16px;border-radius:12px;border:1px solid var(--line);background:var(--panel)}.ok{color:var(--good)}.no{color:var(--bad)}
svg{width:100%;height:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--dim);font-weight:600}
td:nth-child(2),td:nth-child(3){max-width:380px;white-space:pre-wrap;word-break:break-word}
.task{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}
.shots{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}@media(max-width:700px){.shots{grid-template-columns:1fr}}
figure{margin:0}img{width:100%;border-radius:8px;border:1px solid var(--line);display:block}figcaption{font-size:12px;color:var(--dim);margin-top:4px}
.empty{aspect-ratio:16/10;border:1px dashed var(--line);border-radius:8px;display:grid;place-items:center;color:var(--dim);font-size:12px}
.tag{font-size:11px;font-weight:600;color:var(--accent);margin-left:6px}.scroll{overflow-x:auto}
</style></head><body><div class="wrap">
<h1>Meta-Gauntlet report</h1>
<p class="dim">${esc(state.mode === 'mock' ? 'MOCK RUN (fake model answers, for testing the machinery only)' : 'Live run, model answers from the Antigravity agent')} · started ${esc(state.created)} · ${state.iters} arena iterations per task</p>
<div class="verdict"><b class="${v.ok ? 'ok' : 'no'}">${v.ok ? 'Verified' : 'NOT VERIFIED'}</b>: ${v.ok ? `ledger chain intact (${v.entries} entries) and every champion page and screenshot matches its recorded hash.` : esc(v.problems.join('; '))}
<br><b class="${state.honeypot?.passed ? 'ok' : 'no'}">Honeypot ${state.honeypot?.passed ? 'passed' : 'FAILED'}</b>: the evaluator ${state.honeypot?.passed ? 'did not reward' : 'rewarded'} a page that asked AI judges for a perfect score.</div>
<div class="kpis">
<div class="kpi"><b>${H.length}</b><span>meta-rounds run</span></div>
<div class="kpi"><b>${kept.length}</b><span>playbook changes kept</span></div>
<div class="kpi"><b>${H.length ? Math.round(kept.length / H.length * 100) : 0}%</b><span>acceptance rate</span></div>
<div class="kpi"><b>${state.holdout ? `${state.holdout.wins}/${state.holdout.of}` : '—'}</b><span>held-out tasks won</span></div>
<div class="kpi"><b>${state.calls ?? 0}</b><span>model calls</span></div>
</div>
<h2>Tasks won per round</h2>
<p class="dim">Each bar is one round: how many training tasks the proposed playbook won against the champion. Green bars were kept. Real runs are noisy; a smooth climb to perfection is a warning sign.</p>
<svg viewBox="0 0 ${W} ${Hh}" role="img" aria-label="Tasks won per round">${winBars}</svg>
<h2>Before and after</h2>
${tasks.map(compareRow).join('')}
<h2>What changed in the playbook</h2>
<div class="scroll"><table><thead><tr><th>Field</th><th>Default</th><th>Champion</th></tr></thead><tbody>${diffFields()}</tbody></table></div>
<h2>Every round</h2>
<div class="scroll"><table><thead><tr><th>#</th><th>Hypothesis</th><th>Result</th><th>Cheat checks</th></tr></thead><tbody>
${H.map(h => `<tr><td>${h.round}</td><td>${esc(h.hypothesis)}<div class="dim">${esc((h.edits || []).map(e => e.field).join(', '))}</div></td>
<td class="${h.kept ? 'ok' : 'no'}">${h.kept ? 'Kept' : 'Rejected'}<div class="dim">${esc(h.reason)}</div></td>
<td>${(h.results || []).filter(r => Object.keys(r.fabricated || {}).length || r.manipulation).map(r => `${esc(r.task)}: ${r.manipulation ? 'manipulation ' : ''}${esc(Object.keys(r.fabricated || {}).join(', '))}`).join('<br>') || '<span class="dim">clean</span>'}</td></tr>`).join('')}
</tbody></table></div>
</div></body></html>`;
  const file = path.join(dir, 'report.html');
  fs.writeFileSync(file, html);
  return file;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dir = path.resolve(process.argv[2] || 'runs/pilot');
  const v = verify(dir);
  console.log(v.ok ? `Verified: ${v.entries} ledger entries, champion files intact.` : 'NOT VERIFIED:\n- ' + v.problems.join('\n- '));
  console.log('Report: ' + buildReport(dir));
}
