"""
Shared test support — script-path resolution and a hermetic subprocess runner.

Stdlib only. Every test invokes the real script entry points as subprocesses
(`sys.executable script.py ...`) so we exercise argparse + main(), not internals.
The one exception: a single importlib helper to load `normalize_remote_url`
directly, used to assert URL-normalization consistency.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

# tests/ lives directly under the plugin root.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent

INIT_SCRIPT = PLUGIN_ROOT / "skills" / "repo-analyst" / "scripts" / "init_understanding.py"
FRESHNESS_SCRIPT = PLUGIN_ROOT / "skills" / "repo-analyst" / "scripts" / "check_freshness.py"
ASSEMBLE_SCRIPT = PLUGIN_ROOT / "skills" / "repo-wiki-planner" / "scripts" / "assemble_wiki_skill.py"
VIEWER_SCRIPT = PLUGIN_ROOT / "skills" / "repo-wiki-planner" / "scripts" / "generate_viewer.py"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def run_script(script_path, *args, env=None, cwd=None, timeout=60):
    """Run a plugin script as a subprocess and return the CompletedProcess.

    Captures text stdout/stderr. `env`, when provided, fully replaces the
    child environment (callers should start from os.environ.copy()).
    """
    cmd = [sys.executable, str(script_path), *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=None if cwd is None else str(cwd),
        timeout=timeout,
    )


def hermetic_home_env(home_dir):
    """Build an env dict whose HOME (and Windows USERPROFILE) point at home_dir.

    init_understanding.py computes its store root from `Path.home()`, so pinning
    HOME/USERPROFILE redirects all writes into a throwaway tempdir.
    """
    env = os.environ.copy()
    home_str = str(home_dir)
    env["HOME"] = home_str
    env["USERPROFILE"] = home_str  # Windows
    return env


def load_module(script_path, module_name):
    """Import a script file as a module via importlib (for direct unit access)."""
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
