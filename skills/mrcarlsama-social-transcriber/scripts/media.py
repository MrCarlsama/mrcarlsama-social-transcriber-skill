from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        raise RuntimeError("ffmpeg is unavailable; install imageio-ffmpeg or system ffmpeg")


def extract_audio(source: Path, target: Path) -> Path:
    if not source.exists() or source.stat().st_size == 0:
        raise RuntimeError(f"source media is missing or empty: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path(),
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(target),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "ffmpeg failed").strip())
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg finished but audio output is missing or empty: {target}")
    return target
