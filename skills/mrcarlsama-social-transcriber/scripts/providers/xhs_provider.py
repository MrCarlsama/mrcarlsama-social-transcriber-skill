from __future__ import annotations

from pathlib import Path

from providers.yt_dlp_provider import VideoInfo, download as yt_download, probe as yt_probe


def probe(
    url: str,
    cookie_file: Path | None = None,
    visitor_cookie_dir: Path | None = None,
) -> VideoInfo:
    return yt_probe(url, cookie_file, visitor_cookie_dir)


def download(
    url: str,
    output_dir: Path,
    cookie_file: Path | None = None,
    visitor_cookie_dir: Path | None = None,
) -> Path:
    return yt_download(url, output_dir, cookie_file, visitor_cookie_dir)
