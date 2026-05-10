"""
Run System - single command to start demo services.

Usage:
    python run_system.py

Starts:
  1. Tracking server   (ws://localhost:8765)
  2. Frame server      (http://localhost:5000)
  3. Dashboard (Vite)  (http://localhost:3000)
"""

import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
DASHBOARD_DIR = ROOT / "dashboard"
PYTHON = sys.executable


def banner():
    print()
    print("=" * 62)
    print("  MOMT - Multi-Object Multi-Camera Tracking System")
    print("=" * 62)
    print()
    print("  Backend  : ws://localhost:8765  (tracking server)")
    print("  Frames   : http://localhost:5000 (video/frame server)")
    print("  Frontend : http://localhost:3000 (dashboard)")
    print()
    print("  Press Ctrl+C to stop everything")
    print("=" * 62)
    print()


def start_process(label, command, cwd):
    proc = subprocess.Popen(command, cwd=str(cwd), shell=False)
    print(f"      OK {label} starting (PID {proc.pid})")
    return proc


def main():
    parser = argparse.ArgumentParser(description="Start MOMT demo services")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser automatically",
    )
    args = parser.parse_args()

    banner()
    processes = []

    try:
        print("[1/3] Starting tracking server...")
        backend = start_process("tracking server", [PYTHON, str(ROOT / "tracking_server.py")], ROOT)
        processes.append(("Tracking server", backend))
        time.sleep(2)

        print("[2/3] Starting frame server...")
        frame = start_process("frame server", [PYTHON, str(ROOT / "tools" / "frame_server.py")], ROOT)
        processes.append(("Frame server", frame))
        time.sleep(2)

        print("[3/3] Starting dashboard dev server...")
        frontend = subprocess.Popen(
            ["npx", "vite", "--port", "3000"],
            cwd=str(DASHBOARD_DIR),
            shell=True,
        )
        print(f"      OK dashboard starting (PID {frontend.pid})")
        processes.append(("Dashboard", frontend))
        time.sleep(2)

        print()
        print("=" * 62)
        print("  System running")
        print("  Open: http://localhost:3000")
        print("=" * 62)
        print()

        if not args.no_browser:
            webbrowser.open("http://localhost:3000")

        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n  WARNING: {name} exited (code {ret})")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for name, proc in processes:
            if proc.poll() is not None:
                continue
            print(f"  Stopping {name} (PID {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print(f"  OK {name} stopped")
        print("\nGoodbye.\n")


if __name__ == "__main__":
    main()
