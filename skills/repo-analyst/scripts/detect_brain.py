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
    {"available": true,  "url": "http://localhost:4242", "reason": "reachable at /api/health (200)"}
    {"available": false, "url": "http://localhost:4242", "reason": "connection refused"}
    {"available": false, "url": "http://localhost:4242", "reason": "timed out after 2s"}

"Available" means a probe path returned an HTTP response with status < 500 (the
server is up and serving). 5xx, connection refused, timeout, DNS failure, malformed
URL, or all-paths-failed → available:false. Exit code is always 0.
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

# Probe these paths in order until one yields an HTTP response (status < 500).
PROBE_PATHS = ["/api/health", "/health", "/api", "/"]


def _probe_path(base: str, path: str, timeout: float):
    """Probe one path. Returns (available, reason) or (None, reason).

    (True, reason)  -> got an HTTP response with status < 500 (server is serving).
    (None, reason)  -> a 5xx (server up but erroring) or a 404/etc that doesn't
                       prove serving on THIS path; caller keeps trying other paths.
    Raises only the urllib/socket errors the caller translates into a hard
    available:false (connection refused, timeout, DNS) — never anything else.
    """
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
    except urllib.error.HTTPError as exc:
        # The server responded — that alone proves it is up and serving.
        # < 500 counts as available; 5xx means up-but-erroring, keep probing.
        status = exc.code
        if status < 500:
            return True, f"reachable at {path} ({status})"
        return None, f"{path} returned {status}"
    else:
        if status is not None and status < 500:
            return True, f"reachable at {path} ({status})"
        return None, f"{path} returned {status}"


def probe(base: str, timeout: float) -> dict:
    """Probe the base URL across PROBE_PATHS. Returns the verdict dict.

    Never raises: every URLError / timeout / socket error / unexpected exception
    collapses into available:false with a short reason.
    """
    last_reason = "all probe paths failed"
    for path in PROBE_PATHS:
        try:
            available, reason = _probe_path(base, path, timeout)
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
            # Malformed URL (no host), socket-level OSError, etc. Don't keep probing
            # a structurally broken base — report once.
            return {"available": False, "url": base,
                    "reason": str(exc) or "invalid url"}
        except Exception as exc:  # noqa: BLE001 — a probe must never raise.
            return {"available": False, "url": base,
                    "reason": str(exc) or "probe failed"}

        if available:
            return {"available": True, "url": base, "reason": reason}
        last_reason = reason  # 5xx / non-serving status — try the next path.

    return {"available": False, "url": base, "reason": last_reason}


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
