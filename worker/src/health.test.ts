import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';
import type { AddressInfo } from 'node:net';
import { ConfigError, readConfig, readPort } from './env.ts';
import { createHealthServer, HEALTH_PATH, healthPayload } from './health.ts';

describe('readPort', () => {
  it('uses the fallback only when PORT is absent or empty', () => {
    assert.equal(readPort(undefined, 8080), 8080);
    assert.equal(readPort('', 8080), 8080);
  });

  it('accepts a platform-supplied port', () => {
    assert.equal(readPort('3000', 8080), 3000);
    assert.equal(readPort('65535', 8080), 65535);
  });

  it('REFUSES a malformed PORT instead of falling back', () => {
    // The failure this guards: `Number('8080abc')` is NaN and `parseInt` is
    // 8080. Both make a misconfiguration look like a working service.
    for (const bad of ['8080abc', 'abc', '80 80', '-1', '3.5', ' 3000']) {
      assert.throws(() => readPort(bad, 8080), ConfigError, `expected ${bad} to be refused`);
    }
  });

  it('rejects a numeric value outside the TCP range', () => {
    assert.throws(() => readPort('0', 8080), ConfigError);
    assert.throws(() => readPort('70000', 8080), ConfigError);
  });
});

describe('readConfig', () => {
  it('binds 0.0.0.0 by default', () => {
    const c = readConfig({}, { port: 8080, serviceName: 'worker' });
    assert.equal(c.host, '0.0.0.0');
    assert.equal(c.port, 8080);
  });

  it('honours an explicit HOST and PORT', () => {
    const c = readConfig({ HOST: '127.0.0.1', PORT: '9999' }, { port: 8080, serviceName: 'worker' });
    assert.equal(c.host, '127.0.0.1');
    assert.equal(c.port, 9999);
  });
});

describe('healthPayload', () => {
  it('reports a stable shape', () => {
    const p = healthPayload('worker', 1.23456);
    assert.equal(p.status, 'ok');
    assert.equal(p.service, 'worker');
    assert.equal(p.uptime_s, 1.235);
    assert.equal(typeof p.node, 'string');
  });
});

describe('the health server', () => {
  const server = createHealthServer('worker');
  let base = '';

  before(async () => {
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    const addr = server.address() as AddressInfo;
    base = `http://127.0.0.1:${addr.port}`;
  });

  after(async () => {
    await new Promise<void>((resolve, reject) =>
      server.close((err) => (err ? reject(err) : resolve())),
    );
  });

  it('answers GET /health with 200 and no-store', async () => {
    const res = await fetch(`${base}${HEALTH_PATH}`);
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('cache-control'), 'no-store');
    const body = (await res.json()) as { status: string; service: string };
    assert.equal(body.status, 'ok');
    assert.equal(body.service, 'worker');
  });

  it('tolerates a query string, because probes append one', async () => {
    const res = await fetch(`${base}${HEALTH_PATH}?t=1`);
    assert.equal(res.status, 200);
    await res.body?.cancel();
  });

  it('returns 404 as RFC 7807 for any other path', async () => {
    const res = await fetch(`${base}/`);
    assert.equal(res.status, 404);
    const body = (await res.json()) as { status: number; title: string };
    assert.equal(body.status, 404);
    assert.equal(body.title, 'Not Found');
  });

  it('returns 405 with Allow for a write method', async () => {
    const res = await fetch(`${base}${HEALTH_PATH}`, { method: 'POST' });
    assert.equal(res.status, 405);
    assert.equal(res.headers.get('allow'), 'GET, HEAD');
    await res.body?.cancel();
  });
});
