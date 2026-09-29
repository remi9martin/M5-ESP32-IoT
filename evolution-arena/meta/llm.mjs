// Model access for the meta-gauntlet. No API keys: in "queue" mode every model call is written
// to queue/req-<id>.json and answered by the Antigravity agent (see AGENTS.md); "mock" is for tests.
// Requests are content-addressed, so a crash or timeout never loses or repeats paid work.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const sleep = ms => new Promise(r => setTimeout(r, ms));
export const sha = s => crypto.createHash('sha256').update(s).digest('hex');

// Minimal checker for the Gemini-style schemas the arena uses (OBJECT/ARRAY/STRING/INTEGER/NUMBER/BOOLEAN, enum, required).
export function validate(value, schema, at = '$') {
  const t = schema.type;
  if (t === 'OBJECT') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return `${at} must be an object`;
    for (const k of schema.required || []) if (!(k in value)) return `${at}.${k} is required`;
    for (const [k, sub] of Object.entries(schema.properties || {})) {
      if (k in value) { const e = validate(value[k], sub, `${at}.${k}`); if (e) return e; }
    }
  } else if (t === 'ARRAY') {
    if (!Array.isArray(value)) return `${at} must be an array`;
    for (let i = 0; i < value.length; i++) { const e = validate(value[i], schema.items, `${at}[${i}]`); if (e) return e; }
  } else if (t === 'STRING') {
    if (typeof value !== 'string') return `${at} must be a string`;
    if (schema.enum && !schema.enum.includes(value)) return `${at} must be one of ${schema.enum.join(', ')}`;
  } else if (t === 'INTEGER') {
    if (!Number.isInteger(value)) return `${at} must be an integer`;
  } else if (t === 'NUMBER') {
    if (typeof value !== 'number') return `${at} must be a number`;
  } else if (t === 'BOOLEAN') {
    if (typeof value !== 'boolean') return `${at} must be true or false`;
  }
  return null;
}

// Generic mock: fills a schema with plausible values. Callers can pass a `mock` function for specifics.
export function mockFromSchema(schema) {
  switch (schema.type) {
    case 'OBJECT': return Object.fromEntries(Object.entries(schema.properties || {}).map(([k, s]) => [k, mockFromSchema(s)]));
    case 'ARRAY': return [mockFromSchema(schema.items)];
    case 'STRING': return schema.enum ? schema.enum[Math.floor(Math.random() * schema.enum.length)] : 'mock';
    case 'INTEGER': return 40 + Math.floor(Math.random() * 55);
    case 'NUMBER': return Math.random();
    case 'BOOLEAN': return false;
    default: return null;
  }
}

export function createLLM({ mode = 'queue', dir, log = console.log, pollMs = 1000 }) {
  const qdir = path.join(dir, 'queue'), cdir = path.join(dir, 'cache');
  fs.mkdirSync(qdir, { recursive: true }); fs.mkdirSync(cdir, { recursive: true });
  const stats = { calls: 0, cached: 0 };

  // images: array of base64 JPEG strings (no data: prefix) or Buffers.
  // tier: 'fast' (routine) or 'strong' (big decisions); lets AG route requests to a cheaper or stronger model.
  async function ask({ kind, text, images = [], schema, temperature = 0.3, mock, tier = 'fast' }) {
    const imgs = images.map(i => Buffer.isBuffer(i) ? i : Buffer.from(i, 'base64'));
    const id = sha(JSON.stringify({ kind, text, schema, temperature }) + imgs.map(b => sha(b)).join()).slice(0, 16);
    const cacheFile = path.join(cdir, id + '.json');
    if (fs.existsSync(cacheFile)) { stats.cached++; return JSON.parse(fs.readFileSync(cacheFile, 'utf8')); }
    stats.calls++;

    let answer;
    if (mode === 'mock') {
      answer = mock ? mock() : mockFromSchema(schema);
    } else {
      const req = path.join(qdir, `req-${id}.json`), res = path.join(qdir, `res-${id}.json`);
      const imagePaths = imgs.map((b, i) => { const p = path.join(qdir, `img-${id}-${i}.jpg`); fs.writeFileSync(p, b); return p; });
      if (!fs.existsSync(req)) fs.writeFileSync(req, JSON.stringify({ id, kind, tier, temperature, schema, images: imagePaths, created: new Date().toISOString(), prompt: text }, null, 2));
      log(`  waiting for agent: ${kind} request ${id} (queue/req-${id}.json)`);
      for (;;) {
        if (fs.existsSync(res)) {
          let parsed, err;
          try { parsed = JSON.parse(fs.readFileSync(res, 'utf8')); err = validate(parsed, schema); } catch (e) { err = 'invalid JSON: ' + e.message; }
          if (!err) { answer = parsed; break; }
          fs.writeFileSync(path.join(qdir, `err-${id}.txt`), `Rejected answer: ${err}\nFix it and write res-${id}.json again.\n`);
          fs.rmSync(res);
          log(`  answer ${id} rejected: ${err}`);
        }
        await sleep(pollMs);
      }
      for (const f of [req, res, path.join(qdir, `err-${id}.txt`), ...imagePaths]) fs.rmSync(f, { force: true });
    }
    const err = validate(answer, schema);
    if (err) throw new Error(`model answer failed schema (${err})`);
    fs.writeFileSync(cacheFile, JSON.stringify(answer));
    return answer;
  }
  return { ask, stats, mode };
}
