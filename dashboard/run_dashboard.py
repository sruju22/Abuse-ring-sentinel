"""
Launcher script for Abuse-Ring Sentinel Dashboard.
"""

import os
import sys

# Ensure root dir is on path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Automatic Virtual Environment Switcher
# If user ran `python3 dashboard/run_dashboard.py` with system Python,
# automatically switch to the project's virtual environment where CatBoost is installed.
venv_dir = os.path.join(root_dir, ".venv")
venv_python = os.path.join(venv_dir, "bin", "python")
if os.path.exists(venv_python) and sys.prefix != venv_dir:
    print(f"[*] Detected project virtual environment: {venv_python}")
    print("[*] Automatically re-executing under virtual environment...")
    os.execv(venv_python, [venv_python] + sys.argv)

import uvicorn
from src.api.server import app

if __name__ == "__main__":
    print("=" * 75)
    print("  ABUSE-RING SENTINEL - RISK OPERATIONS CENTER DASHBOARD")
    print("  Status: Operational (Synthetic Benchmark 10,000 Accounts)")
    print(f"  Python: {sys.executable}")
    print("  Access URL: http://127.0.0.1:8000")
    print("=" * 75)
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=False)
