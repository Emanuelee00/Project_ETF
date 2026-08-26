#!/usr/bin/env python3
"""Startup script: activates venv, installs deps, runs pipeline, exports Excel."""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PIP = PROJECT_ROOT / "venv" / "bin" / "pip"
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"

def run_cmd(cmd, env=None, stream=False):
    """Run a shell command. Use stream=True to see output in real-time."""
    if stream:
        result = subprocess.run(cmd, shell=True, env=env)
    else:
        result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
    if result.returncode != 0:
        if not stream and result.stderr:
            print(f"ERROR: {result.stderr}")
        sys.exit(1)
    return ""

def main():
    print("=" * 60)
    print("ETF PORTFOLIO ANALYSIS - AUTOMATED PIPELINE")
    print("=" * 60)

    print("\n[1/4] Checking virtual environment...")
    if not VENV_PIP.exists():
        print("Creating virtual environment...")
        run_cmd(f"python3 -m venv {PROJECT_ROOT / 'venv'}")
    
    print("\n[2/4] Installing dependencies...")
    run_cmd(f"{VENV_PIP} install --upgrade pip")
    run_cmd(f"{VENV_PIP} install -r {PROJECT_ROOT / 'requirements.txt'}")

    print("\n[3/4] Running portfolio analysis...")
    run_cmd(f"{VENV_PYTHON} {PROJECT_ROOT / 'src' / 'main.py'}", stream=True)

    print("\n[4/4] Pipeline completed!")
    print("=" * 60)
    print(f"Output: {PROJECT_ROOT / 'output' / 'portfolio_analysis.xlsx'}")
    print("=" * 60)

if __name__ == "__main__":
    main()