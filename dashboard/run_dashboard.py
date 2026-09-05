"""
Launcher script for Abuse-Ring Sentinel Dashboard.
"""

import os
import sys

# Ensure root dir is on path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import uvicorn
from src.api.server import app

if __name__ == "__main__":
    print("=" * 75)
    print("  ABUSE-RING SENTINEL - RISK OPERATIONS CENTER DASHBOARD")
    print("  Status: Operational (Synthetic Benchmark 10,000 Accounts)")
    print("  Access URL: http://127.0.0.1:8000")
    print("=" * 75)
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=False)
