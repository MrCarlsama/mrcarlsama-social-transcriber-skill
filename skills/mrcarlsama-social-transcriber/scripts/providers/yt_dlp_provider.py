from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from providers.visitor_cookies import (
    PUBLIC_USER_AGENT,
    generate_public_visitor_cookies,
    is_fresh_cookie_error,
)


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    platform: str
    video_id: str
    title: str
    url: str
    webpage_url: str
    duration: float | None
    uploader: str | None
    raw: dict
    cookie_file: Path | None = None
    access_method: str = "direct"


def _run_json(command: list[str]) -> dict:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise ProviderError((result.stderr or result.stdout or "yt-dlp failed").strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"yt-dlp returned invalid JSON: {exc}") from exc


def _base_command(cookie_file: Path | None = None) -> list[str]:
    command = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--user-agent", PUBLIC_USER_AGENT]
    if cookie_file:
        command.extend(["--cookies", str(cookie_file)])
    return command


def probe(
    url: str,
    cookie_file: Path | None = None,
    visitor_cookie_dir: Path | None = None,
) -> VideoInfo:
    try:
        return _probe(url, cookie_file, "explicit-cookie" if cookie_file else "direct")
    except ProviderError as exc:
        if cookie_file or not visitor_cookie_dir or not is_fresh_cookie_error(exc):
            raise
        visitor_cookie = generate_public_visitor_cookies(url, visitor_cookie_dir)
        try:
            return _probe(url, visitor_cookie, "public-visitor-cookie")
        except ProviderError as retry_exc:
            visitor_cookie.unlink(missing_ok=True)
            raise ProviderError(
                f"{retry_exc}\npublic visitor cookie retry failed after generating: {visitor_cookie}"
            ) from retry_exc


def _probe(url: str, cookie_file: Path | None, access_method: str) -> VideoInfo:
    data = _run_json(_base_command(cookie_file) + ["--dump-single-json", url])
    extractor = str(data.get("extractor_key") or data.get("extractor") or "").lower()
    webpage_url = str(data.get("webpage_url") or url)
    if "xiaohongshu" in extractor or "xiaohongshu" in webpage_url or "xhslink" in url:
        platform = "xiaohongshu"
    elif "douyin" in extractor or "douyin" in webpage_url or "douyin" in url:
        platform = "douyin"
    else:
        platform = "unknown"

    video_id = str(data.get("id") or data.get("display_id") or "unknown")
    title = str(data.get("title") or data.get("fulltitle") or video_id)
    return VideoInfo(
        platform=platform,
        video_id=video_id,
        title=title,
        url=url,
        webpage_url=webpage_url,
        duration=data.get("duration"),
        uploader=data.get("uploader") or data.get("uploader_id"),
        raw=data,
        cookie_file=cookie_file,
        access_method=access_method,
    )


def download(
    url: str,
    output_dir: Path,
    cookie_file: Path | None = None,
    visitor_cookie_dir: Path | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _download(url, output_dir, cookie_file)
    except ProviderError as exc:
        if cookie_file or not visitor_cookie_dir or not is_fresh_cookie_error(exc):
            raise
        visitor_cookie = generate_public_visitor_cookies(url, visitor_cookie_dir)
        try:
            return _download(url, output_dir, visitor_cookie)
        except ProviderError as retry_exc:
            visitor_cookie.unlink(missing_ok=True)
            raise ProviderError(
                f"{retry_exc}\npublic visitor cookie retry failed after generating: {visitor_cookie}"
            ) from retry_exc
        finally:
            visitor_cookie.unlink(missing_ok=True)


def _download(url: str, output_dir: Path, cookie_file: Path | None) -> Path:
    template = str(output_dir / "_download.%(ext)s")
    command = _base_command(cookie_file) + [
        "--no-playlist",
        "--no-mtime",
        "--merge-output-format",
        "mp4",
        "-o",
        template,
        url,
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise ProviderError((result.stderr or result.stdout or "yt-dlp download failed").strip())

    candidates = sorted(output_dir.glob("_download.*"))
    media = next((path for path in candidates if path.suffix.lower() in {".mp4", ".m4v", ".mov", ".webm"}), None)
    if not media or media.stat().st_size == 0:
        raise ProviderError("download finished but no non-empty source media file was found")

    if media.name != "_download.mp4" and media.suffix.lower() == ".mp4":
        target = output_dir / "_download.mp4"
        media.replace(target)
        return target
    return media
