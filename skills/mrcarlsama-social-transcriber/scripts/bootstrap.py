# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "faster-whisper>=1.1.0",
#   "imageio-ffmpeg>=0.6.0",
#   "playwright>=1.52.0",
#   "yt-dlp>=2026.3.17",
# ]
# ///

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from preflight import run_check


def install_playwright_chromium() -> dict:
    command = [sys.executable, "-m", "playwright", "install", "chromium"]
    result = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure local runtime for this Skill.")
    parser.add_argument("--ensure", action="store_true", help="Install missing local browser runtime.")
    args = parser.parse_args()

    before = run_check()
    install_result = None

    if args.ensure and not before["checks"]["public_visitor_browser"]:
        install_result = install_playwright_chromium()

    after = run_check()
    payload = {
        "ok": after["ok"],
        "status": "ready" if after["ok"] else "not_ready",
        "before": before,
        "after": after,
        "installed": {
            "playwright_chromium": bool(install_result and install_result["ok"]),
        },
        "install_result": install_result,
        "hint": None
        if after["ok"]
        else (
            "uv 会自动安装 Python 依赖，包括 yt-dlp。若 public_visitor_browser 仍为 false，"
            "手动运行：uv run <skill_dir>/scripts/bootstrap.py --ensure"
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0 if after["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
