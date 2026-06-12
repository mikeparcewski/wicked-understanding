"""
Tests for skills/repo-analyst/scripts/detect_brain.py.

detect_brain.py is a probe, not a gate: it ALWAYS exits 0 and prints a single
JSON verdict {"available": bool, "url": str, "reason": str}. These tests drive
the real CLI entry point as a subprocess (sys.executable detect_brain.py ...),
parse stdout as JSON, and assert the verdict — never reaching into internals.

Cases:
  - unreachable: --url at a closed port -> available False, reason non-empty.
  - reachable:   a real http.server on 127.0.0.1:<ephemeral> that answers the
                 wicked-brain `health` action on POST /api with a brain-shaped
                 200 body -> available True. Bound to 127.0.0.1 + ephemeral port
                 so it is cross-platform and never collides.
  - port-live-but-not-brain (regression for the false-positive bug): a server
                 that is LISTENING but returns 404 on POST /api (port-live, but
                 NOT a brain) -> available False. Confirms detection validates a
                 real brain response, not mere port-liveness.
  - generic 200: a server that 200s with a non-JSON / non-brain body -> available
                 False (a random web server on the port is not a brain).
  - malformed:   a structurally broken --url (no host) -> available False, no crash.

Each server-backed test starts a HTTPServer in a daemon thread and shuts it down
in tearDown, so no listener leaks between tests.
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


def _serve(handler_cls):
    """Start an ephemeral loopback HTTPServer in a daemon thread; return (server, url)."""
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url, thread


class _BrainHandler(BaseHTTPRequestHandler):
    """Mimics a real wicked-brain: POST /api with {"action":"health"} -> brain
    health JSON ({"status":"ok", "uptime":..., "brain_id":...}). GET 404s, just
    like the real server (which only serves the read-only viewer HTML on GET /).
    """

    def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler dispatch name.
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)  # drain the request body
        if self.path == "/api":
            body = b'{"status": "ok", "uptime": 12345, "brain_id": "test-brain", "read_only": false}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_GET(self):  # noqa: N802
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):  # silence the default stderr access log.
        pass


class _NotBrainHandler(BaseHTTPRequestHandler):
    """Port-live but NOT a brain: 404 on every method/path (incl. POST /api).

    This is the exact false-positive the fix targets: a process IS listening on
    the port, but it is not a wicked-brain. The probe must report available=False.
    """

    def _four_oh_four(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        self._four_oh_four()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        self._four_oh_four()

    def log_message(self, format, *args):
        pass


class _Generic200Handler(BaseHTTPRequestHandler):
    """A live web server that 200s with a non-brain (HTML) body on everything.

    Status alone is fine; the body is not a brain health envelope -> available
    must be False. Guards against "any 200 is a brain".
    """

    def _ok_html(self):
        body = b"<!DOCTYPE html><html><body>hello, not a brain</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._ok_html()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        self._ok_html()

    def log_message(self, format, *args):
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
        self.server, self.url, self.thread = _serve(_BrainHandler)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_live_brain_reports_available(self):
        """A live brain answering the health action on POST /api -> available True."""
        data, _ = _run("--url", self.url, "--timeout", "2")
        self.assertIs(data["available"], True, data)
        self.assertEqual(data["url"], self.url)
        self.assertTrue(data["reason"], "reason must be non-empty")
        # The reason should reflect a confirmed brain health response.
        self.assertIn("ok", data["reason"].lower(), data)


class TestPortLiveButNotBrain(unittest.TestCase):
    """Regression for the false-positive: port-liveness is NOT brain-availability."""

    def setUp(self):
        self.server, self.url, self.thread = _serve(_NotBrainHandler)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_404_server_is_not_available(self):
        """A listening server that 404s on POST /api -> available False.

        Pre-fix, the probe treated any status < 500 (incl. 404) as 'available',
        so this exact server falsely passed. The fix requires a real brain health
        response, so a 404 must now report available=False with a clear reason.
        """
        data, _ = _run("--url", self.url, "--timeout", "2")
        self.assertIs(data["available"], False, data)
        self.assertEqual(data["url"], self.url)
        self.assertTrue(data["reason"], "reason must be non-empty")
        # The reason should make clear this is not a brain (mentions 404 or 'brain').
        self.assertTrue(
            "404" in data["reason"] or "brain" in data["reason"].lower(),
            f"reason should explain it is not a brain: {data['reason']!r}",
        )


class TestGeneric200NotBrain(unittest.TestCase):
    """A generic 200-returning web server (non-brain body) is NOT available."""

    def setUp(self):
        self.server, self.url, self.thread = _serve(_Generic200Handler)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_generic_200_is_not_available(self):
        """200 + non-JSON/non-brain body -> available False (not just 'something listening')."""
        data, _ = _run("--url", self.url, "--timeout", "2")
        self.assertIs(data["available"], False, data)
        self.assertTrue(data["reason"], "reason must be non-empty")


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
