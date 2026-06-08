"""
Tests for skills/repo-analyst/scripts/detect_brain.py.

detect_brain.py is a probe, not a gate: it ALWAYS exits 0 and prints a single
JSON verdict {"available": bool, "url": str, "reason": str}. These tests drive
the real CLI entry point as a subprocess (sys.executable detect_brain.py ...),
parse stdout as JSON, and assert the verdict — never reaching into internals.

Cases:
  - unreachable: --url at a closed port -> available False, reason non-empty.
  - reachable:   a real http.server on 127.0.0.1:<ephemeral> answering 200 on
                 /health -> available True. Bound to 127.0.0.1 + ephemeral port
                 so it is cross-platform and never collides.
  - malformed:   a structurally broken --url (no host) -> available False, no crash.

The reachable test starts a HTTPServer in a daemon thread and shuts it down in
tearDown, so no listener leaks between tests.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import _support

# _support knows the other scripts but not this one; resolve it the same way
# (PLUGIN_ROOT/skills/repo-analyst/scripts/) without modifying shared support.
DETECT_SCRIPT = _support.PLUGIN_ROOT / "skills" / "repo-analyst" / "scripts" / "detect_brain.py"


def _run(*args, timeout=30):
    """Run detect_brain.py as a subprocess; assert exit 0; return parsed JSON.

    Exit 0 is asserted for EVERY case because the script is a probe, not a gate.
    """
    result = _support.run_script(DETECT_SCRIPT, *args, timeout=timeout)
    assert result.returncode == 0, (
        f"probe must always exit 0; got {result.returncode}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    data = json.loads(result.stdout)
    return data, result


class _HealthHandler(BaseHTTPRequestHandler):
    """Answers 200 on /health, 404 on everything else. No logging to stderr."""

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler dispatch name.
        if self.path == "/health":
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, format, *args):  # silence the default stderr access log.
        pass


class TestUnreachable(unittest.TestCase):
    def test_closed_port_reports_unavailable(self):
        """Port 9 (discard) on loopback is effectively closed -> available False."""
        data, _ = _run("--url", "http://127.0.0.1:9", "--timeout", "1")
        self.assertIsInstance(data["available"], bool)
        self.assertIs(data["available"], False, data)
        self.assertEqual(data["url"], "http://127.0.0.1:9")
        self.assertTrue(data["reason"], "reason must be non-empty")


class TestReachable(unittest.TestCase):
    def setUp(self):
        # Bind 127.0.0.1:0 -> the OS hands us a free ephemeral port. Loopback +
        # ephemeral keeps this hermetic and cross-platform (no fixed-port clash).
        self.server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
        host, port = self.server.server_address[:2]
        self.url = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_live_server_reports_available(self):
        """A live server answering 200 on /health -> available True."""
        data, _ = _run("--url", self.url, "--timeout", "2")
        self.assertIs(data["available"], True, data)
        self.assertEqual(data["url"], self.url)
        self.assertTrue(data["reason"], "reason must be non-empty")
        # The probe tries /api/health first (404 here) then /health (200): the
        # reason should name the path that actually answered.
        self.assertIn("/health", data["reason"], data)


class TestMalformedUrl(unittest.TestCase):
    def test_garbage_url_does_not_crash(self):
        """A URL with no host ('http://') -> exit 0, available False, no traceback."""
        data, result = _run("--url", "http://", "--timeout", "1")
        self.assertIs(data["available"], False, data)
        self.assertTrue(data["reason"], "reason must be non-empty")
        self.assertEqual(result.stderr, "", f"unexpected stderr: {result.stderr!r}")

    def test_unknown_scheme_does_not_crash(self):
        """A nonsense scheme still collapses to available False without raising."""
        data, _ = _run("--url", "notaurl", "--timeout", "1")
        self.assertIs(data["available"], False, data)
        self.assertTrue(data["reason"], "reason must be non-empty")


if __name__ == "__main__":
    unittest.main()
