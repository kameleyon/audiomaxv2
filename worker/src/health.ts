/**
 * `/health` — the liveness surface, and nothing else.
 *
 * It answers one question: is this process able to serve? It deliberately does
 * NOT probe the database, the queue or a provider. A health endpoint that fails
 * when a dependency fails takes the whole service out of rotation for a fault it
 * could have degraded around, and — worse here — it makes the platform restart a
 * worker that is fine. Dependency state belongs in a readiness surface with its
 * own path and its own contract; that arrives with the dependencies, not before.
 *
 * The payload is JSON with a stable shape because a probe is a contract: adding
 * a field is safe, renaming one is a breaking change for whatever reads it.
 */
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';

export interface HealthPayload {
  readonly status: 'ok';
  readonly service: string;
  readonly uptime_s: number;
  readonly node: string;
}

export const HEALTH_PATH = '/health';

export function healthPayload(service: string, uptimeSeconds: number): HealthPayload {
  return {
    status: 'ok',
    service,
    uptime_s: Math.round(uptimeSeconds * 1000) / 1000,
    node: process.versions.node,
  };
}

function send(res: ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(json),
    // A probe response must never be served from a cache; a cached 200 is a
    // health check that reports the past.
    'cache-control': 'no-store',
  });
  res.end(json);
}

export function handle(req: IncomingMessage, res: ServerResponse, service: string): void {
  // `req.url` is a path with an optional query; a probe may append one.
  const path = (req.url ?? '/').split('?')[0];
  if (path !== HEALTH_PATH) {
    // RFC 7807 shape, which §9 of the design spec adopts for every error.
    send(res, 404, {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
      detail: `No route for ${path}. This process serves ${HEALTH_PATH} only.`,
    });
    return;
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('allow', 'GET, HEAD');
    send(res, 405, {
      type: 'about:blank',
      title: 'Method Not Allowed',
      status: 405,
      detail: `${HEALTH_PATH} accepts GET and HEAD.`,
    });
    return;
  }
  send(res, 200, healthPayload(service, process.uptime()));
}

export function createHealthServer(service: string): Server {
  const server = createServer((req, res) => {
    handle(req, res, service);
  });
  // A probe that hangs is worse than one that fails: the platform waits out its
  // whole timeout before acting.
  server.requestTimeout = 5_000;
  server.headersTimeout = 5_000;
  return server;
}
