import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { isBackendHealth, readHealth } from './health-contract.ts';

describe('isBackendHealth', () => {
  it('accepts the worker payload', () => {
    assert.equal(isBackendHealth({ status: 'ok', service: 'worker', uptime_s: 1.5 }), true);
  });

  it('rejects anything that is not the contract', () => {
    for (const bad of [null, undefined, 'ok', 42, {}, { status: 'ok' }, { status: 'degraded', service: 'w', uptime_s: 1 }]) {
      assert.equal(isBackendHealth(bad), false);
    }
  });
});

describe('readHealth', () => {
  it('reports reachable only on 200 with a valid body', () => {
    const r = readHealth(200, { status: 'ok', service: 'worker', uptime_s: 0 });
    assert.equal(r.reachable, true);
  });

  it('treats a 200 with a foreign body as unreachable', () => {
    // A captive portal or a proxy answering 200 with HTML is the case this
    // exists for: "we got a 200" is not "we reached the backend".
    const r = readHealth(200, '<html>Sign in to continue</html>');
    assert.equal(r.reachable, false);
  });

  it('treats any non-200 as unreachable', () => {
    assert.equal(readHealth(503, { status: 'ok', service: 'w', uptime_s: 1 }).reachable, false);
  });
});
