// End-to-end checks for the meta-gauntlet machinery (no model needed). Run: node test/smoke.mjs
import { spawnSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verify } from '../report.mjs';

const META = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runs = p => path.join(META, 'runs', p);
const node = (args, env = {}) => spawnSync(process.execPath, args, { cwd: META, env: { ...process.env, ...env }, encoding: 'utf8' });
let failed = 0;
const check = (name, ok, extra = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  (' + extra + ')' : ''}`); if (!ok) failed++; };
for (const d of ['smoke-mock', 'smoke-fooled', 'smoke-resume', 'smoke-queue']) fs.rmSync(runs(d), { recursive: true, force: true });

// 1. Mock run completes, report verifies.
let r = node(['run.mjs', '--mock', '--rounds', '2', '--iters', '1', '--out', 'runs/smoke-mock']);
const st = r.status === 0 && JSON.parse(fs.readFileSync(runs('smoke-mock/state.json'), 'utf8'));
check('mock run completes', r.status === 0, r.status !== 0 ? r.stderr.slice(-300) : '');
check('state has 2 rounds and a held-out result', st && st.round === 2 && !!st.holdout);
check('report verifies', verify(runs('smoke-mock')).ok);

// 2. Tampering with a scored page is detected.
const champ = Object.values(st.champion.outputs)[0], file = path.join(runs('smoke-mock'), champ.htmlFile);
fs.appendFileSync(file, '<!-- edited after scoring -->');
check('tampered page is detected', !verify(runs('smoke-mock')).ok);

// 3. A judge that falls for the honeypot aborts the run.
r = node(['run.mjs', '--mock', '--rounds', '1', '--iters', '1', '--out', 'runs/smoke-fooled'], { MOCK_FOOLED: '1' });
check('fooled evaluator aborts the run', r.status === 2);

// 4. Crash mid-run, then --resume finishes without redoing finished rounds.
const child = spawn(process.execPath, ['run.mjs', '--mock', '--rounds', '3', '--iters', '1', '--out', 'runs/smoke-resume'], { cwd: META });
await new Promise(res => {
  const t = setInterval(() => {
    try { if (JSON.parse(fs.readFileSync(runs('smoke-resume/state.json'), 'utf8')).round >= 1) { child.kill('SIGKILL'); clearInterval(t); res(); } } catch {}
  }, 200);
});
const before = JSON.parse(fs.readFileSync(runs('smoke-resume/state.json'), 'utf8')).round;
r = node(['run.mjs', '--mock', '--rounds', '3', '--iters', '1', '--out', 'runs/smoke-resume', '--resume']);
const after = JSON.parse(fs.readFileSync(runs('smoke-resume/state.json'), 'utf8'));
check('resume continues after a crash', r.status === 0 && after.round === 3 && after.history.length === 3, `killed at round ${before}`);
check('resumed ledger still verifies', verify(runs('smoke-resume')).ok);

// 5. Queue mode: a stand-in agent answers the request files.
const agent = spawn(process.execPath, ['test/mock-agent.mjs', 'runs/smoke-queue'], { cwd: META, stdio: 'inherit' });
r = node(['run.mjs', '--rounds', '1', '--iters', '1', '--out', 'runs/smoke-queue', '--allow-fooled']);
await new Promise(res => agent.on('exit', res));
check('queue mode completes through file handoff', r.status === 0, r.status !== 0 ? r.stderr.slice(-300) : '');
check('queue left no pending requests', fs.readdirSync(runs('smoke-queue/queue')).filter(f => f.startsWith('req-')).length === 0);

console.log(failed ? `\n${failed} check(s) failed` : '\nAll checks passed');
process.exit(failed ? 1 : 0);
