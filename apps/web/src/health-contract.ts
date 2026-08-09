/**
 * The one thing both clients already need and neither can invent: the shape of
 * a backend health response, and the rule for reading it.
 *
 * This is not a placeholder. It is the smallest real artifact that makes the
 * scaffold non-empty and testable, and it encodes a decision worth pinning now:
 * a client decides "reachable" from the STATUS CODE and the parsed `status`
 * field, never from the presence of a body. A 200 with an unparseable body is a
 * proxy or a captive portal answering, not the service.
 *
 * When the web framework is chosen (its own phase, its own ADR), this moves into
 * the shared contract package. Until then it lives beside the client that reads
 * it rather than being copied into two.
 */

export interface BackendHealth {
  readonly status: 'ok';
  readonly service: string;
  readonly uptime_s: number;
}

export type HealthReading =
  | { readonly reachable: true; readonly health: BackendHealth }
  | { readonly reachable: false; readonly reason: string };

/** Narrow an unknown parsed body to the health contract. */
export function isBackendHealth(value: unknown): value is BackendHealth {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return v['status'] === 'ok' && typeof v['service'] === 'string' && typeof v['uptime_s'] === 'number';
}

/**
 * Read a health response. Separated from fetching so the decision rule is
 * testable without a socket.
 */
export function readHealth(status: number, body: unknown): HealthReading {
  if (status !== 200) {
    return { reachable: false, reason: `backend answered ${status}` };
  }
  if (!isBackendHealth(body)) {
    return {
      reachable: false,
      reason: 'backend answered 200 with a body that is not the health contract',
    };
  }
  return { reachable: true, health: body };
}
