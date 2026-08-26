#!/usr/bin/env python3
"""Start the ETF Portfolio Analyzer web server."""

import os
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON  = PROJECT_ROOT / "venv" / "bin" / "python"

if not VENV_PYTHON.exists():
    print("ERROR: venv not found — run run_all.py first to set it up.")
    sys.exit(1)

DEFAULT_PORTS = [int(os.environ.get("ETF_PORT", 8000)), 8001, 8002]

print("=" * 55)
print("  ETF Portfolio Analyzer — Web Server")
print("=" * 55)

selected_port = None
for port in DEFAULT_PORTS:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            selected_port = port
            break

if selected_port is None:
    print(f"ERROR: Nessuna porta disponibile tra {DEFAULT_PORTS}. Rilascia la porta o imposta ETF_PORT.")
    sys.exit(1)

print(f"  URL: http://localhost:{selected_port}")
print("  Stop: Ctrl+C")
print("=" * 55)

subprocess.run(
    [str(VENV_PYTHON), "-m", "uvicorn", "server:app",
     "--host", "0.0.0.0", "--port", str(selected_port), "--log-level", "warning"],
    cwd=str(PROJECT_ROOT / "src"),
)
