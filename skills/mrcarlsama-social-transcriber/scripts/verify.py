from __future__ import annotations

import json
from pathlib import Path


REQUIRED_FILE_KEYS = [
    "原视频",
    "原音频",
    "原始逐字稿_md",
    "原始逐字稿_txt",
    "字幕_srt",
    "词级时间戳_json",
    "任务清单_json",
]


def verify_output(output_dir: Path, files: dict[str, str]) -> dict:
    missing = []
    empty = []
    for key in REQUIRED_FILE_KEYS:
        name = files[key]
        path = output_dir / name
        if not path.exists():
            missing.append(name)
        elif path.stat().st_size == 0:
            empty.append(name)

    transcript = output_dir / files["原始逐字稿_txt"]
    transcript_chars = len(transcript.read_text(encoding="utf-8").strip()) if transcript.exists() else 0
    if transcript.exists() and transcript_chars == 0:
        empty.append(files["原始逐字稿_txt"])

    words_path = output_dir / files["词级时间戳_json"]
    word_count = 0
    if words_path.exists() and words_path.stat().st_size > 0:
        data = json.loads(words_path.read_text(encoding="utf-8"))
        word_count = len(data.get("words") or [])

    ok = not missing and not empty and transcript_chars > 0
    return {
        "ok": ok,
        "missing": missing,
        "empty": sorted(set(empty)),
        "transcript_chars": transcript_chars,
        "word_count": word_count,
    }
