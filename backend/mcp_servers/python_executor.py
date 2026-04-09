"""
QuantAgents — Python Code Executor MCP Server
Safely runs financial analysis Python snippets in a sandboxed subprocess.
Used by the Technical Analyst for custom indicator calculations and by
the Backtest Engine for running vectorbt strategy scripts.
"""
from __future__ import annotations

import ast
import logging
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("python-executor")

TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 8000

# Allowed top-level imports (blocklist-based sandbox)
BLOCKED_IMPORTS = frozenset([
    "os", "subprocess", "sys", "shutil", "pathlib", "socket",
    "requests", "urllib", "http", "ftplib", "smtplib",
    "importlib", "ctypes", "multiprocessing", "threading",
    "__builtins__", "eval", "exec", "compile",
])


def _check_safe(code: str) -> tuple[bool, str]:
    """
    Static AST check — blocks dangerous imports, exec/eval, and file I/O.
    Returns (is_safe, rejection_reason).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Syntax error: {exc}"

    for node in ast.walk(tree):
        # Block dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {alias.name}"

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0]
                if top_level in BLOCKED_IMPORTS:
                    return False, f"Blocked import from: {node.module}"

        # Block open(), exec(), eval() calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("open", "exec", "eval", "compile"):
                return False, f"Blocked built-in call: {node.func.id}()"

    return True, ""


@mcp.tool()
def run_python(code: str, packages: str = "") -> dict[str, Any]:
    """
    Execute a Python code snippet for financial analysis.
    Available libraries: pandas, numpy, scipy, matplotlib (no display), statsmodels.

    Args:
        code: Python code to execute (no I/O, no network calls, no shell commands)
        packages: Comma-separated additional packages to import (e.g., "scipy,statsmodels")

    Returns:
        Dict with stdout, stderr, success flag, and any printed output

    Examples:
        - Computing custom technical indicators
        - Running statistical tests on price data
        - Computing correlation matrices
        - Performing descriptive statistics on returns
    """
    is_safe, reason = _check_safe(code)
    if not is_safe:
        return {"success": False, "error": f"Code rejected by safety check: {reason}", "stdout": "", "stderr": ""}

    # Prepend standard financial analysis imports
    preamble = textwrap.dedent("""
        import math
        import statistics
        import json
        from datetime import datetime, timedelta

        import numpy as np
        import pandas as pd

        try:
            import scipy.stats as stats
        except ImportError:
            pass
        try:
            import statsmodels.api as sm
        except ImportError:
            pass
    """)

    # Add any extra requested packages (filtered)
    extra_safe = [p.strip() for p in packages.split(",") if p.strip() and p.strip() not in BLOCKED_IMPORTS]
    for pkg in extra_safe:
        preamble += f"\ntry:\n    import {pkg}\nexcept ImportError:\n    pass\n"

    full_code = preamble + "\n" + code

    # Write to temp file and execute in subprocess for isolation
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        stdout = result.stdout[:MAX_OUTPUT_CHARS]
        stderr = result.stderr[:2000]
        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Code timed out after {TIMEOUT_SECONDS}s", "stdout": "", "stderr": ""}
    except Exception as exc:
        return {"success": False, "error": str(exc), "stdout": "", "stderr": ""}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@mcp.tool()
def validate_code(code: str) -> dict[str, Any]:
    """
    Validate Python code syntax and safety without running it.

    Args:
        code: Python code to validate

    Returns:
        Dict with is_valid, is_safe, syntax_errors, safety_issues
    """
    try:
        ast.parse(code)
        syntax_ok = True
        syntax_error = None
    except SyntaxError as exc:
        syntax_ok = False
        syntax_error = str(exc)

    is_safe, safety_reason = _check_safe(code)

    return {
        "is_valid": syntax_ok and is_safe,
        "syntax_ok": syntax_ok,
        "syntax_error": syntax_error,
        "is_safe": is_safe,
        "safety_issue": safety_reason if not is_safe else None,
    }


if __name__ == "__main__":
    mcp.run()
