/**
 * Worker entry point.
 *
 * Phase 0: this process serves `/health` and does nothing else. It exists so the
 * deployment topology — port binding, shutdown, the probe contract — is settled
 * and testable BEFORE the render pipeline lands on top of it, rather than being
 * discovered during the first deploy of something that matters.
 *
 * Provider keys live in this process and never leave it (CLAUDE.md constraint 5).
 * Nothing here reads one yet, and nothing here logs the environment.
 */
import { pathToFileURL } from 'node:url';
import { readConfig } from './env.ts';
import { createHealthServer, HEALTH_PATH } from './health.ts';

const SERVICE = 'worker';
const DEFAULT_PORT = 8080;

export function main(): void {
  const config = readConfig(process.env, { port: DEFAULT_PORT, serviceName: SERVICE });
  const server = createHealthServer(config.serviceName);

  server.listen(config.port, config.host, () => {
    console.log(
      JSON.stringify({
        event: 'listening',
        service: config.serviceName,
        host: config.host,
        port: config.port,
        path: HEALTH_PATH,
      }),
    );
  });

  // SIGTERM is how every one of these platforms asks a container to stop. A
  // process that ignores it is killed on the grace timer instead, mid-request.
  const shutdown = (signal: string): void => {
    console.log(JSON.stringify({ event: 'shutdown', service: SERVICE, signal }));
    server.close(() => {
      process.exit(0);
    });
    // If connections refuse to drain, stop anyway rather than hang forever.
    setTimeout(() => process.exit(0), 10_000).unref();
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

// Run only when executed directly, so the module stays importable from tests.
// `pathToFileURL`, not string concatenation: on Windows `file://C:\a\b` is not
// the URL Node reports for the same file, so a hand-built comparison is false
// on one of the two platforms this repository is developed and shipped on.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
