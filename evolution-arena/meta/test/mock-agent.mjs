// Stands in for the Antigravity agent: answers every queued request with schema-valid fake JSON.
import fs from 'node:fs';
import path from 'node:path';
import { mockFromSchema } from '../llm.mjs';
const qdir = path.resolve(process.argv[2], 'queue');
let answered = 0;
for (;;) {
  if (fs.existsSync(qdir)) for (const f of fs.readdirSync(qdir).filter(f => f.startsWith('req-'))) {
    const res = path.join(qdir, f.replace('req-', 'res-'));
    if (fs.existsSync(res)) continue;
    try {
      const r = JSON.parse(fs.readFileSync(path.join(qdir, f), 'utf8'));
      fs.writeFileSync(res, JSON.stringify(mockFromSchema(r.schema)));
      answered++;
    } catch {} // request still being written
  }
  if (fs.existsSync(path.resolve(process.argv[2], 'report.html')) && fs.existsSync(path.resolve(process.argv[2], 'playbook.champion.json'))) break;
  await new Promise(r => setTimeout(r, 200));
}
console.log(`mock agent answered ${answered} requests`);
