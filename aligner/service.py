"""Aligner sidecar — the `/health` surface, and nothing else yet.

The aligner is the Python half of the topology: transcription and match run here
because the model libraries are Python (`aligner/spike-a/` is the evidence that
produced that decision). Phase 0 settles how it is reached and stopped, before
anything that matters runs inside it.

Standard library only, on purpose. The worker probes this process, and a probe
that cannot start because a wheel failed to build is a probe that reports the
build system rather than the service. The transcription dependencies arrive with
the transcription code, in its own phase and its own image layer.

Run:  python aligner/service.py
Env:  PORT (default 8081), HOST (default 0.0.0.0)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

SERVICE = "aligner"
HEALTH_PATH = "/health"
DEFAULT_PORT = 8081
_STARTED_AT = time.monotonic()


class ConfigError(ValueError):
    """A configuration value was supplied and could not be used."""


def read_port(raw: str | None, fallback: int) -> int:
    """Parse PORT the way the worker does, and refuse the same failures.

    An absent variable takes the fallback. A PRESENT but malformed one is an
    error: the platform assigned a port and this process would bind a different
    one, which presents as a healthy service nothing can reach.
    """
    if raw is None or raw == "":
        return fallback
    if not raw.isdigit():
        raise ConfigError(
            f"PORT is set to {raw!r}, which is not a port number. Refusing to fall "
            f"back to {fallback}: a malformed PORT means the platform assigned one "
            f"and this process would bind a different one."
        )
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ConfigError(f"PORT is {port}; a TCP port is 1-65535.")
    return port


def health_payload(uptime_seconds: float) -> dict[str, Any]:
    """The probe contract. Adding a key is safe; renaming one is breaking."""
    return {
        "status": "ok",
        "service": SERVICE,
        "uptime_s": round(uptime_seconds, 3),
        "python": sys.version.split()[0],
    }


class HealthHandler(BaseHTTPRequestHandler):
    server_version = "audiomax-aligner"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        # A cached 200 is a health check that reports the past.
        self.send_header("cache-control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _route(self) -> None:
        path = (self.path or "/").split("?", 1)[0]
        if path != HEALTH_PATH:
            # RFC 7807, the same error shape the API surface uses.
            self._send(
                404,
                {
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": f"No route for {path}. This process serves {HEALTH_PATH} only.",
                },
            )
            return
        self._send(200, health_payload(time.monotonic() - _STARTED_AT))

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's contract
        self._route()

    def do_HEAD(self) -> None:  # noqa: N802
        self._route()

    def do_POST(self) -> None:  # noqa: N802
        self.send_response(405)
        self.send_header("allow", "GET, HEAD")
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        # One JSON event per line, so the log is parseable by whatever collects
        # it. BaseHTTPRequestHandler's default writes free text to stderr.
        sys.stdout.write(
            json.dumps({"event": "request", "service": SERVICE, "line": fmt % args}) + "\n"
        )


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), HealthHandler)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    port = read_port(os.environ.get("PORT"), DEFAULT_PORT)
    host = os.environ.get("HOST", "0.0.0.0")
    httpd = build_server(host, port)

    def _stop(signum: int, _frame: Any) -> None:
        # SIGTERM is how every container platform asks a process to stop.
        print(json.dumps({"event": "shutdown", "service": SERVICE, "signal": signum}), flush=True)
        httpd.shutdown()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    print(
        json.dumps(
            {
                "event": "listening",
                "service": SERVICE,
                "host": host,
                "port": httpd.server_address[1],
                "path": HEALTH_PATH,
            }
        ),
        flush=True,
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
