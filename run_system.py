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
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).parent
DASHBOARD_DIR = ROOT / "dashboard"
PYTHON = sys.executable
FRONTEND_URL = "http://localhost:3000"
FRAME_SERVER_HEALTH_URL = "http://localhost:5000/health"


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
    proc = subprocess.Popen(command, cwd=str(cwd), shell=False, env=os.environ.copy())
    print(f"      OK {label} starting (PID {proc.pid})")
    return proc


def wait_for_http(label, url, timeout_s=20):
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    print(f"      OK {label} ready ({url})")
                    return True
        except URLError as error:
            last_error = error
        except OSError as error:
            last_error = error
        time.sleep(0.5)

    print(f"      WARNING {label} did not respond at {url}: {last_error}")
    return False


def get_vite_command():
    vite_script = DASHBOARD_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if vite_script.exists():
        node = shutil.which("node.exe") or shutil.which("node")
        if node:
            return [node, str(vite_script), "--host", "127.0.0.1", "--port", "3000"]

    npm_cmd = "npm.cmd" if sys.platform.startswith("win") else "npm"
    return [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000"]


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
        wait_for_http("frame server", FRAME_SERVER_HEALTH_URL, timeout_s=30)

        print("[3/3] Starting dashboard dev server...")
        frontend = start_process("dashboard", get_vite_command(), DASHBOARD_DIR)
        processes.append(("Dashboard", frontend))
        wait_for_http("dashboard", FRONTEND_URL, timeout_s=30)

        print()
        print("=" * 62)
        print("  System running")
        print(f"  Open: {FRONTEND_URL}")
        print("=" * 62)
        print()

        if not args.no_browser:
            webbrowser.open(FRONTEND_URL)

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
