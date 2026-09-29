// Runs the real Evolution Arena page (../index.html) headlessly on one task with a given playbook.
// The page does all booting, probing, patch applying and rollback; model calls are bridged to llm.mjs.
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ARENA = pathToFileURL(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'index.html')).href;

const kindOf = schema => {
  const p = schema?.properties || {};
  return p.edits ? 'arena-patch' : p.html ? 'arena-rewrite' : p.winner ? 'arena-judge' : p.failures ? 'arena-redteam' : 'arena';
};

export async function arenaDefaults(browser) {
  const page = await browser.newPage();
  await page.goto(ARENA);
  const pb = await page.evaluate(() => window.arenaAPI.defaults());
  await page.close();
  return pb;
}

// task: { task, judges[], gates[], seed }  →  { html, calls, accepted, log }
export async function runArena(browser, { llm, playbook, task, iters }) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } }); // fresh storage per run
  const page = await context.newPage();
  if (llm.mode !== 'mock') {
    await page.exposeFunction('arenaLLM', async (model, parts, schema, temperature) => {
      const text = parts.filter(p => p.text).map(p => p.text).join('\n');
      const images = parts.filter(p => p.inlineData).map(p => p.inlineData.data);
      return JSON.stringify(await llm.ask({ kind: kindOf(schema), text, images, schema, temperature }));
    });
  }
  await page.goto(ARENA);
  await page.evaluate(({ playbook, cfg }) => { window.arenaAPI.setPlaybook(playbook); window.arenaAPI.configure(cfg); }, {
    playbook,
    cfg: { task: task.task, judges: task.judges, seed: task.seed, iters, gates: task.gates || [], patch: true, visual: false,
      model: llm.mode === 'mock' ? 'mock' : 'agent' },
  });
  await page.evaluate(() => window.arenaAPI.run());
  const res = await page.evaluate(() => window.arenaAPI.result());
  const log = await page.evaluate(() => window.arenaAPI.log());
  await context.close();
  const lanes = res?.lanes || [];
  const accepted = lanes.reduce((n, L) => n + L.gen, 0);
  // Return a surviving version, not the highest score ever seen: scores from different judgments are not comparable,
  // so prefer the lane that survived the most accepted changes (each one beat its predecessor), then its score.
  const pick = [...lanes].sort((a, b) => b.gen - a.gen || b.score - a.score)[0];
  return { html: pick?.code || task.seed, calls: res?.calls || 0, accepted, log };
}
