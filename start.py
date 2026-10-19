#!/usr/bin/env python3
"""One-command launcher for Windows, macOS and Linux.

    python start.py            # http://127.0.0.1:8000 (opens your browser)
    python start.py --port 9000 --host 0.0.0.0 --no-browser

First run: creates .venv, installs dependencies, writes .env with a random SECRET_KEY.
The app itself creates the database tables and loads demo data on first start.
"""
import argparse
import os
import secrets
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_env_file():
    env = ROOT / ".env"
    if env.exists():
        return
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    lines = [f"SECRET_KEY={secrets.token_hex(32)}" if l.startswith("SECRET_KEY=") else l for l in text.splitlines()]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Created .env with a random SECRET_KEY")


def ensure_venv():
    if sys.prefix != sys.base_prefix:  # already inside a virtual environment
        return sys.executable
    if not PY.exists():
        print("Creating virtual environment in .venv ...")
        venv.create(VENV, with_pip=True)
    marker = VENV / ".deps-installed"
    req = ROOT / "backend" / "requirements.txt"
    if not marker.exists() or marker.stat().st_mtime < req.stat().st_mtime:
        print("Installing dependencies (first run only) ...")
        subprocess.check_call([str(PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req)])
        marker.touch()
    return str(PY)


def main():
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is required. Download it from https://www.python.org/downloads/")
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    ensure_env_file()
    python = ensure_venv()
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    print(f"\n  JanSetu is starting at {url}\n  Demo password for every demo account: Demo@1234\n  Press Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(4), webbrowser.open(url)), daemon=True).start()
    cmd = [python, "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)]
    try:
        subprocess.call(cmd, cwd=ROOT / "backend")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
