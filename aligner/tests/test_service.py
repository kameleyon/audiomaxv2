"""Tests for the aligner sidecar's health surface.

Run from the repository root:  python -m unittest discover -s aligner/tests -t aligner
"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from service import HEALTH_PATH, ConfigError, build_server, health_payload, read_port


class ReadPortTest(unittest.TestCase):
    def test_absent_or_empty_uses_the_fallback(self) -> None:
        self.assertEqual(read_port(None, 8081), 8081)
        self.assertEqual(read_port("", 8081), 8081)

    def test_accepts_a_platform_supplied_port(self) -> None:
        self.assertEqual(read_port("3000", 8081), 3000)
        self.assertEqual(read_port("65535", 8081), 65535)

    def test_refuses_a_malformed_port_instead_of_falling_back(self) -> None:
        for bad in ("8080abc", "abc", "80 80", "-1", "3.5", " 3000"):
            with self.subTest(bad=bad), self.assertRaises(ConfigError):
                read_port(bad, 8081)

    def test_rejects_out_of_range(self) -> None:
        with self.assertRaises(ConfigError):
            read_port("0", 8081)
        with self.assertRaises(ConfigError):
            read_port("70000", 8081)


class HealthPayloadTest(unittest.TestCase):
    def test_stable_shape(self) -> None:
        p = health_payload(1.23456)
        self.assertEqual(p["status"], "ok")
        self.assertEqual(p["service"], "aligner")
        self.assertEqual(p["uptime_s"], 1.235)
        self.assertIsInstance(p["python"], str)


class HealthServerTest(unittest.TestCase):
    httpd = None
    thread = None
    base = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = build_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        assert cls.httpd is not None
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_health_returns_200_and_no_store(self) -> None:
        with urllib.request.urlopen(f"{self.base}{HEALTH_PATH}", timeout=5) as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.headers["cache-control"], "no-store")
            body = json.loads(res.read())
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "aligner")

    def test_tolerates_a_query_string(self) -> None:
        with urllib.request.urlopen(f"{self.base}{HEALTH_PATH}?t=1", timeout=5) as res:
            self.assertEqual(res.status, 200)
            res.read()

    def test_other_paths_are_404_problem_json(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{self.base}/", timeout=5)
        self.assertEqual(caught.exception.code, 404)
        body = json.loads(caught.exception.read())
        self.assertEqual(body["title"], "Not Found")

    def test_post_is_405_with_allow(self) -> None:
        req = urllib.request.Request(f"{self.base}{HEALTH_PATH}", data=b"", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(caught.exception.code, 405)
        self.assertEqual(caught.exception.headers["allow"], "GET, HEAD")


if __name__ == "__main__":
    unittest.main()
