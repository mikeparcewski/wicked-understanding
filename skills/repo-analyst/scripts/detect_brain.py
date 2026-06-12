#!/usr/bin/env python3
"""
detect_brain.py — Deterministic availability probe for the wicked-brain server.

wicked-understanding's analysis knowledge source is pluggable: when a wicked-brain
server is reachable it acts as a build-time enricher; otherwise the pipeline falls
back to the built-in lenses (the fallback floor). This script is ONLY the detection
probe — it tells `repo-analyst` which source to use. It is a probe, not a gate:
it NEVER raises and ALWAYS exits 0. The single JSON line on stdout is the verdict.

Usage:
    # Probe the default URL (env WICKED_BRAIN_URL, else http://localhost:4242)
    python3 detect_brain.py

    # Probe an explicit URL with a custom timeout
    python3 detect_brain.py --url http://localhost:4242 --timeout 2

Output: a single JSON object to stdout, e.g.
    {"available": true,  "url": "http://localhost:4242", "reason": "brain health ok (status=ok)"}
    {"available": false, "url": "http://localhost:4242", "reason": "connection refused"}
    {"available": false, "url": "http://localhost:4242", "reason": "timed out after 2s"}
    {"available": false, "url": "http://localhost:4242", "reason": "/api returned 404 (not a brain)"}

"Available" means the server at the URL is actually a working wicked-brain: it
answers the `health` action on `POST /api` with a 200 and a brain-shaped JSON
body (the documented {"status":"ok", ...} health response). Port-liveness alone
is NOT enough — a random web server (or any service) that returns 200/404 on a
plain GET is NOT a brain and reports available:false. 4xx/5xx, a non-JSON body,
a JSON body without the health marker, connection refused, timeout, DNS failure,
or a malformed URL all → available:false. Exit code is always 0.
"""

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request

# Default base URL when neither --url nor WICKED_BRAIN_URL is set.
DEFAULT_URL = "http://localhost:4242"

# The wicked-brain server exposes a single endpoint: POST /api with an action.
# We confirm the brain by invoking the `health` action and validating the reply.
API_PATH = "/api"
HEALTH_BODY = json.dumps({"action": "health"}).encode("utf-8")


def _is_brain_health(payload) -> bool:
    """True iff the decoded JSON body looks like a wicked-brain health response.

    The documented health action returns {"status": "ok", "uptime": <ms>,
    "brain_id": <str>, ...}. We accept it as a brain when the body is a JSON
    object that is NOT an error and carries a recognizable health marker —
    `status == "ok"`, or one of the brain-specific fields (`brain_id`,
    `uptime`). This rejects a generic 200 (e.g. {"error": "..."} or a body
    with no brain shape) so port-liveness alone can't pass.
    """
    if not isinstance(payload, dict):
        return False
    if "error" in payload:
        return False
    status = payload.get("status")
    if isinstance(status, str) and status.lower() == "ok":
        return True
    # Fall back to brain-specific fields the health action always emits.
    return ("brain_id" in payload) or ("uptime" in payload)


def _probe_health(base: str, timeout: float):
    """POST the `health` action to /api and validate the brain-shaped reply.

    Returns (True, reason) when a working brain is confirmed, else (False, reason).
    Raises only the urllib/socket errors the caller translates into a hard
    available:false (connection refused, timeout, DNS) — never anything else.
    """
    url = base.rstrip("/") + API_PATH
    req = urllib.request.Request(
        url, data=HEALTH_BODY, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        # The server responded with an error status. A live port that 4xx/5xx
        # on the brain API is NOT a working brain.
        return False, f"{API_PATH} returned {exc.code} (not a brain)"

    if status is None or status >= 400:
        return False, f"{API_PATH} returned {status} (not a brain)"

    # Status is a 2xx/3xx — now require a brain-shaped JSON body. A 200 from a
    # non-brain server (or a brain error envelope) must NOT count as available.
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False, f"{API_PATH} returned non-JSON body (not a brain)"

    if _is_brain_health(payload):
        marker = payload.get("status") or payload.get("brain_id") or "ok"
        return True, f"brain health ok (status={marker})"
    return False, f"{API_PATH} responded but not a brain health body"


def probe(base: str, timeout: float) -> dict:
    """Probe the base URL by invoking the brain `health` action. Returns verdict.

    Never raises: every URLError / timeout / socket error / unexpected exception
    collapses into available:false with a short reason.
    """
    try:
        available, reason = _probe_health(base, timeout)
    except urllib.error.URLError as exc:
        # Connection refused, DNS failure, timeout surfacing as URLError, etc.
        reason = exc.reason
        if isinstance(reason, socket.timeout) or isinstance(exc, socket.timeout):
            return {"available": False, "url": base,
                    "reason": f"timed out after {_fmt_timeout(timeout)}s"}
        if isinstance(reason, socket.gaierror):
            return {"available": False, "url": base,
                    "reason": "DNS resolution failed"}
        text = str(reason) if reason else str(exc)
        low = text.lower()
        if "refused" in low:
            return {"available": False, "url": base, "reason": "connection refused"}
        if "timed out" in low or "timeout" in low:
            return {"available": False, "url": base,
                    "reason": f"timed out after {_fmt_timeout(timeout)}s"}
        # Other transport-level failure (e.g. unknown host, unsupported proto).
        return {"available": False, "url": base, "reason": text or "connection failed"}
    except socket.timeout:
        return {"available": False, "url": base,
                "reason": f"timed out after {_fmt_timeout(timeout)}s"}
    except (ValueError, OSError) as exc:
        # Malformed URL (no host), socket-level OSError, etc.
        return {"available": False, "url": base,
                "reason": str(exc) or "invalid url"}
    except Exception as exc:  # noqa: BLE001 — a probe must never raise.
        return {"available": False, "url": base,
                "reason": str(exc) or "probe failed"}

    return {"available": bool(available), "url": base, "reason": reason}


def _fmt_timeout(timeout: float) -> str:
    """Render the timeout without a trailing .0 for whole-second values."""
    if float(timeout).is_integer():
        return str(int(timeout))
    return str(timeout)


def resolve_url(cli_url) -> str:
    """--url wins, then env WICKED_BRAIN_URL, then the built-in default."""
    if cli_url:
        return cli_url
    env_url = os.environ.get("WICKED_BRAIN_URL")
    if env_url:
        return env_url
    return DEFAULT_URL


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe whether a wicked-brain server is reachable (prints JSON, always exits 0)."
    )
    parser.add_argument(
        "--url", default=None,
        help="Brain base URL. Default: env WICKED_BRAIN_URL, else " + DEFAULT_URL,
    )
    parser.add_argument(
        "--timeout", type=float, default=2.0,
        help="Per-request timeout in seconds (default: 2).",
    )
    args = parser.parse_args(argv)

    base = resolve_url(args.url)

    try:
        verdict = probe(base, args.timeout)
    except Exception as exc:  # noqa: BLE001 — final backstop; a probe never crashes.
        verdict = {"available": False, "url": base, "reason": str(exc) or "probe failed"}

    sys.stdout.write(json.dumps(verdict) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
