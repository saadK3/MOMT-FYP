"""
Run System — Single command to start everything.

Usage:
    python run_system.py          # Start backend + frontend dev server
    python run_system.py --build  # Start backend + serve production build

Starts:
  1. Tracking server  (ws://localhost:8765)
  2. Dashboard server  (http://localhost:3000)

Press Ctrl+C to stop both.
"""

import subprocess
import sys
import os
import signal
import time
import webbrowser
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
DASHBOARD_DIR = ROOT / "dashboard"
PYTHON = sys.executable


def banner():
    print()
    print("=" * 62)
    print("  MOMT — Multi-Object Multi-Camera Tracking System")
    print("=" * 62)
    print()
    print("  Backend  :  ws://localhost:8765   (tracking server)")
    print("  Frontend :  http://localhost:3000  (dashboard)")
    print()
    print("  Press Ctrl+C to stop everything")
    print("=" * 62)
    print()


def main():
    parser = argparse.ArgumentParser(description="Start the MOMT system")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open the browser automatically")
    args = parser.parse_args()

    banner()

    processes = []

    try:
        # --- 1. Start tracking server ------------------------------------
        print("[1/2] Starting tracking server...")
        backend = subprocess.Popen(
            [PYTHON, str(ROOT / "tracking_server.py")],
            cwd=str(ROOT),
        )
        processes.append(("Backend", backend))
        print("      ✓ Tracking server starting (PID", backend.pid, ")")

        # Give the backend a moment to load data and start WS
        time.sleep(3)

        # --- 2. Start dashboard dev server --------------------------------
        print("[2/2] Starting dashboard dev server...")
        frontend = subprocess.Popen(
            ["npx", "vite", "--port", "3000"],
            cwd=str(DASHBOARD_DIR),
            shell=True,
        )
        processes.append(("Frontend", frontend))
        print("      ✓ Dashboard server starting (PID", frontend.pid, ")")

        # Give Vite a moment to spin up
        time.sleep(2)

        print()
        print("=" * 62)
        print("  ✅  System running!")
        print()
        print("  Open:  http://localhost:3000")
        print("=" * 62)
        print()

        # Open browser
        if not args.no_browser:
            webbrowser.open("http://localhost:3000")

        # Wait for either process to exit
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n  ⚠  {name} exited (code {ret})")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n  Shutting down...")

    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"  Stopping {name} (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                print(f"  ✓ {name} stopped")

        print()
        print("  Goodbye! 👋")
        print()


if __name__ == "__main__":
    main()
