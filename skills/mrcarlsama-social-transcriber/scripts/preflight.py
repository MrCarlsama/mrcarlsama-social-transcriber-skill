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
import importlib.util
import json
import shutil
import subprocess
import sys
from contextlib import suppress


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_ffmpeg() -> bool:
    if module_exists("imageio_ffmpeg"):
        return True
    return command_exists("ffmpeg")


def check_public_visitor_browser() -> dict:
    if not module_exists("playwright"):
        return {"ok": False, "method": None, "error": "playwright python package is missing"}

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"ok": False, "method": None, "error": f"{type(exc).__name__}: {exc}"}

    errors: list[str] = []
    with suppress(Exception):
        with sync_playwright() as playwright:
            for channel in ("chrome", "msedge"):
                try:
                    browser = playwright.chromium.launch(channel=channel, headless=True)
                    browser.close()
                    return {"ok": True, "method": channel, "error": None}
                except PlaywrightError as exc:
                    errors.append(f"{channel}: {exc}")
            try:
                browser = playwright.chromium.launch(headless=True)
                browser.close()
                return {"ok": True, "method": "playwright-chromium", "error": None}
            except PlaywrightError as exc:
                errors.append(f"playwright-chromium: {exc}")

    return {"ok": False, "method": None, "error": "\n".join(errors) or "browser launch failed"}


def run_check() -> dict:
    browser = check_public_visitor_browser()
    checks = {
        "python_3_12_or_newer": sys.version_info >= (3, 12),
        "uv": command_exists("uv"),
        "yt_dlp_python_module": module_exists("yt_dlp"),
        "faster_whisper": module_exists("faster_whisper"),
        "imageio_ffmpeg_or_ffmpeg": check_ffmpeg(),
        "playwright_python": module_exists("playwright"),
        "public_visitor_browser": bool(browser["ok"]),
    }
    optional = {
        "yt_dlp_command": command_exists("yt-dlp"),
        "system_ffmpeg": command_exists("ffmpeg"),
    }

    ffmpeg_version = None
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        result = subprocess.run([ffmpeg_bin, "-version"], text=True, capture_output=True)
        ffmpeg_version = (result.stdout.splitlines() or [""])[0]

    ok = all(checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "optional": optional,
        "python": sys.version.split()[0],
        "ffmpeg_version": ffmpeg_version,
        "sources": {
            "uv": "https://github.com/astral-sh/uv",
            "yt_dlp": "https://github.com/yt-dlp/yt-dlp#installation",
            "faster_whisper": "https://github.com/SYSTRAN/faster-whisper",
            "imageio_ffmpeg": "https://github.com/imageio/imageio-ffmpeg",
            "playwright_python": "https://github.com/microsoft/playwright-python",
        },
        "browser": browser,
        "hint": None
        if ok
        else (
            "先安装 uv，然后运行：uv run <skill_dir>/scripts/bootstrap.py --ensure。"
            "本 Skill 不要求全局安装 yt-dlp；yt-dlp 由 uv 按脚本依赖自动安装。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    payload = run_check()
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
