/**
 * The one decision the mobile client cannot defer to its framework: what a
 * screen reader is told while the backend is unreachable.
 *
 * "Text before audio" (CLAUDE.md constraint 3) means extracted text is served
 * the moment parsing finishes and reading never waits on TTS. On a phone that
 * also means reading must not wait on the NETWORK once the text is local. This
 * module holds the state machine for that, so the answer is one function rather
 * than a condition scattered through a UI that does not exist yet.
 *
 * The messages here are placeholders for the message catalogue (spec §9,
 * `GET /i18n/messages?locale=`), not final copy — Guide writes the strings and
 * Proof grades them. What is NOT a placeholder is the rule: every state has a
 * message, because an untranslated enum token is not a status a user can
 * receive (WCAG 4.1.3), and a silent state is worse still.
 */

export type Connectivity = 'online' | 'offline';

export type ReadingCapability =
  /** Text and audio are both available. */
  | 'text_and_audio'
  /** Text is local; audio needs the network and is not available. */
  | 'text_only'
  /** Nothing is local and nothing is reachable. */
  | 'unavailable';

export interface DocumentAvailability {
  readonly textCached: boolean;
  readonly audioCached: boolean;
}

export function capability(
  connectivity: Connectivity,
  cached: DocumentAvailability,
): ReadingCapability {
  // Online, the backend serves both, cached or not.
  if (connectivity === 'online') return 'text_and_audio';
  if (cached.textCached && cached.audioCached) return 'text_and_audio';
  if (cached.textCached) return 'text_only';
  return 'unavailable';
}

/** Every capability has an announceable message. No state is silent. */
export const CAPABILITY_MESSAGE_KEY: Record<ReadingCapability, string> = {
  text_and_audio: 'reading.capability.text_and_audio',
  text_only: 'reading.capability.text_only',
  unavailable: 'reading.capability.unavailable',
};
