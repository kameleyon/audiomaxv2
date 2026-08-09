/**
 * Process configuration, read once and validated loudly.
 *
 * PORT is the one variable a platform sets FOR you — Railway, Fly, Cloud Run and
 * Heroku all inject it — and it is the one most often read wrong. Three failures
 * this module exists to prevent:
 *
 *   1. `Number(process.env.PORT)` on an unset variable yields NaN, `listen(NaN)`
 *      binds an EPHEMERAL port, the process reports healthy, and the platform's
 *      health probe hits the port it assigned and finds nothing. The service is
 *      "up" and unreachable.
 *   2. `parseInt` accepts "8080abc" and returns 8080, so a corrupted value is
 *      silently repaired into a plausible one.
 *   3. Binding 127.0.0.1 inside a container makes the process reachable only from
 *      itself. Containers bind 0.0.0.0.
 *
 * Failing at boot is correct here. A worker that cannot be reached has nothing
 * to degrade to, and CLAUDE.md's no-fallback rule applies to configuration as
 * much as to providers.
 */

export interface ServiceConfig {
  readonly port: number;
  readonly host: string;
  readonly serviceName: string;
}

export class ConfigError extends Error {
  override readonly name = 'ConfigError';
}

/**
 * Parse a port from an environment value.
 *
 * @param raw   the value as the platform supplied it, or undefined when unset
 * @param fallback the port to use when the variable is ABSENT — never when it is
 *                 present and malformed, because a malformed value means someone
 *                 configured something and it did not take effect.
 */
export function readPort(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw === '') return fallback;
  if (!/^\d{1,5}$/.test(raw)) {
    throw new ConfigError(
      `PORT is set to ${JSON.stringify(raw)}, which is not a port number. ` +
        `Refusing to fall back to ${fallback}: a malformed PORT means the platform ` +
        `assigned one and this process would bind a different one, which presents as ` +
        `a healthy service nothing can reach.`,
    );
  }
  const port = Number(raw);
  if (port < 1 || port > 65535) {
    throw new ConfigError(`PORT is ${port}; a TCP port is 1–65535.`);
  }
  return port;
}

export function readConfig(
  env: NodeJS.ProcessEnv,
  defaults: { port: number; serviceName: string },
): ServiceConfig {
  return {
    port: readPort(env['PORT'], defaults.port),
    // 0.0.0.0 unless explicitly overridden. Inside a container 127.0.0.1 makes
    // the process reachable only from itself.
    host: env['HOST'] ?? '0.0.0.0',
    serviceName: defaults.serviceName,
  };
}
