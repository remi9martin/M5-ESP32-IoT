#!/usr/bin/env node
// Helper for the Antigravity agent that answers the meta-gauntlet's model requests.
//   node queue.mjs status              how many requests are waiting
//   node queue.mjs next                print the oldest request (prompt, schema, image files)
//   node queue.mjs answer <id> <file>  validate a JSON answer and hand it to the runner ("-" = stdin)
//   --only eval | --except eval         split the work: grading requests should go to a separate agent
import fs from 'node:fs';
import path from 'node:path';
import { validate } from './llm.mjs';

const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const out = outIdx >= 0 ? args.splice(outIdx, 2)[1] : latestRun();
const onlyIdx = args.indexOf('--only'), only = onlyIdx >= 0 ? args.splice(onlyIdx, 2)[1] : null;
const exIdx = args.indexOf('--except'), except = exIdx >= 0 ? args.splice(exIdx, 2)[1] : null;
const kindOk = f => { try { const k = JSON.parse(fs.readFileSync(f, 'utf8')).kind; return (!only || k.startsWith(only)) && (!except || !k.startsWith(except)); } catch { return false; } };
const qdir = path.join(out, 'queue');

function latestRun() {
  const runs = path.resolve('runs');
  if (!fs.existsSync(runs)) return 'runs/pilot';
  const dirs = fs.readdirSync(runs).map(d => path.join(runs, d)).filter(d => fs.existsSync(path.join(d, 'queue')));
  dirs.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  return dirs[0] || 'runs/pilot';
}
const pending = () => fs.existsSync(qdir)
  ? fs.readdirSync(qdir).filter(f => /^req-.*\.json$/.test(f) && !fs.existsSync(path.join(qdir, f.replace('req-', 'res-'))))
      .map(f => path.join(qdir, f)).filter(kindOk).sort((a, b) => fs.statSync(a).mtimeMs - fs.statSync(b).mtimeMs)
  : [];

const [cmd, id, file] = args;
if (cmd === 'status' || !cmd) {
  console.log(`${out}: ${pending().length} request(s) waiting`);
} else if (cmd === 'next') {
  const f = pending()[0];
  if (!f) { console.log('No requests waiting.'); process.exit(0); }
  const r = JSON.parse(fs.readFileSync(f, 'utf8'));
  const err = path.join(qdir, `err-${r.id}.txt`);
  console.log(`ID: ${r.id}\nKIND: ${r.kind}\nTEMPERATURE: ${r.temperature}`);
  if (fs.existsSync(err)) console.log('PREVIOUS ANSWER WAS REJECTED: ' + fs.readFileSync(err, 'utf8'));
  if (r.images.length) console.log('IMAGES (look at each):\n' + r.images.map(p => '  ' + p).join('\n'));
  console.log('ANSWER JSON SCHEMA:\n' + JSON.stringify(r.schema));
  console.log('ANSWER WITH: node queue.mjs answer ' + r.id + ' <file-with-json>');
  console.log('----- PROMPT -----\n' + r.prompt);
} else if (cmd === 'answer' && id) {
  const req = path.join(qdir, `req-${id}.json`);
  if (!fs.existsSync(req)) { console.error('No such request: ' + id); process.exit(1); }
  const raw = file === '-' || !file ? fs.readFileSync(0, 'utf8') : fs.readFileSync(file, 'utf8');
  let obj;
  try { obj = JSON.parse(raw.replace(/^```(?:json)?\s*|\s*```$/g, '')); } catch (e) { console.error('Not valid JSON: ' + e.message); process.exit(1); }
  const e = validate(obj, JSON.parse(fs.readFileSync(req, 'utf8')).schema);
  if (e) { console.error('Answer does not match the schema: ' + e); process.exit(1); }
  fs.writeFileSync(path.join(qdir, `res-${id}.json`), JSON.stringify(obj));
  console.log(`Accepted answer for ${id}. ${pending().length} request(s) still waiting.`);
} else {
  console.log('Usage: node queue.mjs status | next | answer <id> <file|->  [--out runs/<name>]');
}
