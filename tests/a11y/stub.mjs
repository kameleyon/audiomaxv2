/**
 * stub.mjs — serves the fixture over real HTTP.
 *
 * IT EXISTS FOR ONE REASON. Without it, `drive.mjs`'s HTTP transport — URL
 * building, verbs, JSON parsing, status handling — would be the one part of
 * this harness that nothing executes, and it is the part a live run depends on
 * entirely. `--self-test` drives this server with the SAME fetch transport a
 * live run uses, so "the driver works" is observed rather than assumed.
 *
 * IT IS NOT AN IMPLEMENTATION. It answers from a hand-written fixture. Passing
 * against it says the checks and the wiring agree with each other; it says
 * nothing at all about audiomax, and `--stub` prints that on every run.
 */

import { createServer } from 'node:http';
import { transportFor } from './fixture.mjs';

/** Start a stub over `data`. Returns { origin, close }. */
export async function startStub(data) {
  const respond = transportFor(data);
  const server = createServer((req, res) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', async () => {
      let body = null;
      if (chunks.length) {
        try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { body = null; }
      }
      let out;
      try {
        out = await respond(req.method, req.url, body);
      } catch (err) {
        // A stub that 500s is itself a finding — A-NO-5XX will see it.
        out = { status: 500, body: { code: 'stub_error', message: String(err?.message ?? err) } };
      }
      res.writeHead(out.status, { 'content-type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(out.body));
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  return {
    origin: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

/** The transport a live run uses. The stub is driven through this one too. */
export function httpTransport(origin, token) {
  return async (method, path, body) => {
    const headers = { accept: 'application/json' };
    if (token) headers.authorization = `Bearer ${token}`;
    if (body !== undefined && body !== null) headers['content-type'] = 'application/json';
    const res = await fetch(new URL(path, origin), {
      method,
      headers,
      body: body === undefined || body === null ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let parsed = null;
    if (text) { try { parsed = JSON.parse(text); } catch { parsed = { _unparseable: text.slice(0, 200) }; } }
    return { status: res.status, body: parsed };
  };
}
