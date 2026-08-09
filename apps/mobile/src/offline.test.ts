import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { CAPABILITY_MESSAGE_KEY, capability, type ReadingCapability } from './offline.ts';

describe('capability', () => {
  it('serves text and audio when online', () => {
    assert.equal(capability('online', { textCached: false, audioCached: false }), 'text_and_audio');
  });

  it('serves cached text offline even with no audio — text before audio', () => {
    assert.equal(capability('offline', { textCached: true, audioCached: false }), 'text_only');
  });

  it('serves both offline when both are cached', () => {
    assert.equal(capability('offline', { textCached: true, audioCached: true }), 'text_and_audio');
  });

  it('is unavailable offline with nothing cached', () => {
    assert.equal(capability('offline', { textCached: false, audioCached: false }), 'unavailable');
  });
});

describe('CAPABILITY_MESSAGE_KEY', () => {
  it('has a message key for EVERY capability — no silent state', () => {
    const all: ReadingCapability[] = ['text_and_audio', 'text_only', 'unavailable'];
    for (const c of all) {
      assert.equal(typeof CAPABILITY_MESSAGE_KEY[c], 'string');
      assert.ok(CAPABILITY_MESSAGE_KEY[c].length > 0, `${c} has no message key`);
    }
    assert.equal(Object.keys(CAPABILITY_MESSAGE_KEY).length, all.length);
  });
});
