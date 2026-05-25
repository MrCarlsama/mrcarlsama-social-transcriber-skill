from __future__ import annotations

import json
from pathlib import Path


def md_timestamp(seconds: float) -> str:
    total = int(max(0.0, seconds))
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def srt_timestamp(seconds: float) -> str:
    ms_total = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    sec, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{sec:02d},{ms:03d}"


def transcribe_audio(audio: Path, output_dir: Path, meta_dir: Path, title: str, model_name: str = "small") -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(
        str(audio),
        language="zh",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    raw_md_name = f"{title}原始逐字稿.md"
    raw_txt_name = f"{title}原始逐字稿.txt"
    subtitle_name = f"{title}字幕.srt"
    words_name = "words.json"

    md_lines = [f"# {title}原始逐字稿", ""]
    txt_lines: list[str] = []
    srt_lines: list[str] = []
    segment_rows: list[dict] = []
    word_rows: list[dict] = []
    srt_index = 1

    for segment in segments_iter:
        text = segment.text.strip()
        if not text:
            continue
        md_lines.append(f"[{md_timestamp(segment.start)}] {text}")
        txt_lines.append(text)
        srt_lines.extend(
            [
                str(srt_index),
                f"{srt_timestamp(segment.start)} --> {srt_timestamp(segment.end)}",
                text,
                "",
            ]
        )
        srt_index += 1
        segment_rows.append({"start": segment.start, "end": segment.end, "text": text})
        for word in segment.words or []:
            word_text = (word.word or "").strip()
            if word_text:
                word_rows.append(
                    {
                        "start": word.start,
                        "end": word.end,
                        "word": word_text,
                        "probability": word.probability,
                    }
                )

    output_dir.joinpath(raw_md_name).write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    output_dir.joinpath(raw_txt_name).write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    output_dir.joinpath(subtitle_name).write_text("\n".join(srt_lines), encoding="utf-8")
    meta_dir.joinpath(words_name).write_text(
        json.dumps({"segments": segment_rows, "words": word_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "model": f"faster-whisper-{model_name}",
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": len(segment_rows),
        "words": len(word_rows),
        "files": {
            "raw_transcript_md": raw_md_name,
            "raw_transcript_txt": raw_txt_name,
            "subtitle_srt": subtitle_name,
            "words_json": words_name,
        },
    }
