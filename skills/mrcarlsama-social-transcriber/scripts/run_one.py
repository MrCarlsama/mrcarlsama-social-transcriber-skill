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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from asr import transcribe_audio
from media import extract_audio
from providers import douyin_provider, xhs_provider, yt_dlp_provider
from report import print_report, write_report
from verify import verify_output


URL_RE = re.compile(r"https?://\S+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_filename(value: str, fallback: str = "视频", max_length: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", value.strip())
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value[:max_length].strip(" .") or fallback)


def format_date(dt: datetime) -> str:
    return f"{dt.year}-{dt.month}-{dt.day}"


def date_from_provider(raw: dict) -> str:
    upload_date = str(raw.get("upload_date") or "")
    if re.fullmatch(r"\d{8}", upload_date):
        dt = datetime.strptime(upload_date, "%Y%m%d")
        return format_date(dt)

    timestamp = raw.get("timestamp") or raw.get("release_timestamp") or raw.get("modified_timestamp")
    if timestamp:
        try:
            return format_date(datetime.fromtimestamp(float(timestamp), timezone.utc).astimezone())
        except (TypeError, ValueError, OSError):
            pass

    return format_date(datetime.now().astimezone())


def first_present(raw: dict, *keys: str):
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def count_from_raw(raw: dict, *keys: str) -> int | None:
    value = first_present(raw, *keys)
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else None
    return None


def content_metadata(raw: dict, info) -> dict:
    return {
        "title": info.title,
        "body": first_present(raw, "description", "caption", "full_description", "content"),
        "uploader": info.uploader,
        "upload_date": first_present(raw, "upload_date"),
        "timestamp": first_present(raw, "timestamp", "release_timestamp", "modified_timestamp"),
        "stats": {
            "like_count": count_from_raw(raw, "like_count", "likes"),
            "comment_count": count_from_raw(raw, "comment_count", "comments"),
            "favorite_count": count_from_raw(raw, "favorite_count", "collect_count", "bookmark_count"),
            "share_count": count_from_raw(raw, "repost_count", "share_count", "forward_count"),
            "view_count": count_from_raw(raw, "view_count", "play_count", "view_count_text"),
        },
    }


def write_body_file(output_dir: Path, title: str, metadata: dict, url: str) -> Path | None:
    body = str(metadata.get("body") or "").strip()
    if not body:
        return None
    stats = metadata.get("stats") or {}
    lines = [
        f"# {title}正文",
        "",
        f"- 来源：{url}",
        f"- 作者：{metadata.get('uploader') or ''}",
        f"- 点赞数：{stats.get('like_count')}",
        f"- 评论数：{stats.get('comment_count')}",
        f"- 收藏数：{stats.get('favorite_count')}",
        f"- 分享数：{stats.get('share_count')}",
        f"- 播放数：{stats.get('view_count')}",
        "",
        "## 正文",
        "",
        body,
        "",
    ]
    path = output_dir / f"{title}正文.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot allocate unique path for {path}")


def is_nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def find_existing_source(output_dir: Path, title: str) -> Path | None:
    candidates = sorted(output_dir.glob(f"{title}原视频.*"))
    return next((path for path in candidates if is_nonempty_file(path)), None)


def expected_asr_files(title: str) -> dict:
    return {
        "raw_transcript_md": f"{title}原始逐字稿.md",
        "raw_transcript_txt": f"{title}原始逐字稿.txt",
        "subtitle_srt": f"{title}字幕.srt",
        "words_json": "words.json",
    }


def existing_asr_result(output_dir: Path, meta_dir: Path, title: str) -> dict | None:
    files = expected_asr_files(title)
    raw_md = output_dir / files["raw_transcript_md"]
    raw_txt = output_dir / files["raw_transcript_txt"]
    subtitle = output_dir / files["subtitle_srt"]
    words_path = meta_dir / files["words_json"]
    required = [raw_md, raw_txt, subtitle, words_path]
    if not all(is_nonempty_file(path) for path in required):
        return None

    transcript_chars = len(raw_txt.read_text(encoding="utf-8").strip())
    if transcript_chars == 0:
        return None

    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    prior_manifest = {}
    manifest_path = meta_dir / "manifest.json"
    if manifest_path.exists():
        try:
            prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior_manifest = {}

    return {
        "model": prior_manifest.get("model") or "existing-asr",
        "language": prior_manifest.get("language") or "zh",
        "language_probability": prior_manifest.get("language_probability"),
        "segments": len(words_data.get("segments") or []),
        "words": len(words_data.get("words") or []),
        "files": files,
        "asr_attempts": [{"step": "resume", "ok": True, "reason": "existing transcript files"}],
    }


def asr_model_sequence(model_name: str) -> list[str]:
    order = ["large-v3", "medium", "small", "base", "tiny"]
    if model_name not in order:
        return [model_name]
    start = order.index(model_name)
    return order[start:]


def transcribe_with_fallback(audio: Path, output_dir: Path, meta_dir: Path, title: str, model_name: str) -> dict:
    attempts = []
    for candidate in asr_model_sequence(model_name):
        try:
            result = transcribe_audio(audio, output_dir, meta_dir, title, model_name=candidate)
            raw_txt = output_dir / result["files"]["raw_transcript_txt"]
            transcript_chars = len(raw_txt.read_text(encoding="utf-8").strip()) if raw_txt.exists() else 0
            if transcript_chars > 0:
                attempts.append({"model": candidate, "ok": True, "transcript_chars": transcript_chars})
                return result | {"asr_attempts": attempts}
            attempts.append({"model": candidate, "ok": False, "error": "ASR 输出为空"})
        except Exception as exc:
            attempts.append({"model": candidate, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    raise RuntimeError(f"ASR failed after model fallback attempts: {json.dumps(attempts, ensure_ascii=False)}")


def extract_url(raw: str) -> str:
    match = URL_RE.search(raw)
    if not match:
        raise ValueError("no URL found")
    return match.group(0).rstrip("。.,，)")


def pick_provider(url: str):
    lower = url.lower()
    if "xiaohongshu.com" in lower or "xhslink.com" in lower:
        return xhs_provider
    if "douyin.com" in lower or "v.douyin.com" in lower:
        return douyin_provider
    return yt_dlp_provider


def platform_from_url(url: str | None) -> str:
    lower = (url or "").lower()
    if "xiaohongshu.com" in lower or "xhslink.com" in lower:
        return "xiaohongshu"
    if "douyin.com" in lower or "v.douyin.com" in lower:
        return "douyin"
    return "unknown"


def classify_error(error: str) -> str:
    lower = error.lower()
    if "fresh cookies" in lower or "cookie" in lower:
        return "需要新鲜 Cookie"
    if "unsupported" in lower:
        return "平台不支持"
    if "not found" in lower or "unavailable" in lower:
        return "内容不可用"
    if "ffmpeg" in lower or "audio" in lower:
        return "音频抽取失败"
    if "faster" in lower or "whisper" in lower or "asr" in lower:
        return "本地 ASR 不可用"
    return "未知错误"


def write_failure_report(output_root: Path, raw_input: str, exc: Exception) -> dict:
    url = None
    try:
        url = extract_url(raw_input)
    except ValueError:
        pass

    platform = platform_from_url(url)
    error_text = str(exc)
    reason = classify_error(str(exc))
    public_visitor_retry_attempted = "public visitor cookie retry failed" in error_text
    failed_dir = output_root / "_failed" / clean_filename(
        f"{format_date(datetime.now().astimezone())}[{platform}][{reason}]",
        fallback="failed",
        max_length=120,
    )
    meta_dir = failed_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": False,
        "status": "failed",
        "reason": reason,
        "url": url,
        "raw_input": raw_input,
        "error_type": type(exc).__name__,
        "error": error_text,
        "public_visitor_cookie_retry_attempted": public_visitor_retry_attempted,
        "output_dir": str(failed_dir.resolve()),
        "report": str((meta_dir / "report.json").resolve()),
        "hint": (
            "已尝试公开访客态 cookie，但平台仍拒绝访问。下一步只能由用户显式提供 --cookie-file，"
            "或者手动下载内容后提供本地文件。不要自动读取浏览器 Cookie。"
            if public_visitor_retry_attempted
            else "如果 provider 要求 fresh cookies，会先尝试公开访客态 cookie；仍失败时只接受用户显式提供的 --cookie-file。不要自动读取浏览器 Cookie。"
        ),
        "created_at": now_iso(),
    }
    write_report(meta_dir, payload)
    return payload


def write_manifest(meta_dir: Path, manifest: dict) -> Path:
    path = meta_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run(url: str, output_root: Path, model_name: str, cookie_file: Path | None) -> dict:
    provider = pick_provider(url)
    visitor_cookie_dir = output_root / "_runtime" / "visitor-cookies"
    generated_cookie_file: Path | None = None
    try:
        info = provider.probe(url, cookie_file, visitor_cookie_dir)
        effective_cookie_file = cookie_file or info.cookie_file
        generated_cookie_file = info.cookie_file if info.cookie_file and not cookie_file else None
        title = clean_filename(info.title or info.video_id)
        output_dir_name = f"{date_from_provider(info.raw)}[{info.platform}][{title}]"
        output_dir = output_root / clean_filename(
            output_dir_name,
            fallback=f"{info.platform}-{info.video_id}",
            max_length=160,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        resume_steps: list[str] = []

        meta_dir = output_dir / "_meta"
        meta_dir.mkdir(exist_ok=True)

        raw_info_path = meta_dir / "provider-info.json"
        raw_info_path.write_text(json.dumps(info.raw, ensure_ascii=False, indent=2), encoding="utf-8")

        metadata = content_metadata(info.raw, info)
        body_file = write_body_file(output_dir, title, metadata, url)

        source = find_existing_source(output_dir, title)
        if source:
            resume_steps.append("download")
        else:
            source = provider.download(url, output_dir, effective_cookie_file, visitor_cookie_dir)
            source_suffix = source.suffix if source.suffix else ".mp4"
            source_target = unique_path(output_dir / f"{title}原视频{source_suffix}")
            if source != source_target:
                source.replace(source_target)
                source = source_target

        audio = output_dir / f"{title}原音频.wav"
        if is_nonempty_file(audio):
            resume_steps.append("audio")
        else:
            audio = extract_audio(source, audio)

        asr_result = existing_asr_result(output_dir, meta_dir, title)
        if asr_result:
            resume_steps.append("asr")
        else:
            asr_result = transcribe_with_fallback(audio, output_dir, meta_dir, title, model_name=model_name)

        files = {
            "原视频": source.name,
            "原音频": audio.name,
            "原始逐字稿_md": asr_result["files"]["raw_transcript_md"],
            "原始逐字稿_txt": asr_result["files"]["raw_transcript_txt"],
            "字幕_srt": asr_result["files"]["subtitle_srt"],
            "最终润色稿_待生成": f"{title}逐字稿.md",
            "词级时间戳_json": f"_meta/{asr_result['files']['words_json']}",
            "任务清单_json": "_meta/manifest.json",
            "运行报告_json": "_meta/report.json",
            "下载器原始信息_json": "_meta/provider-info.json",
        }
        if body_file:
            files["正文_md"] = body_file.name

        manifest = {
            "platform": info.platform,
            "id": info.video_id,
            "url": url,
            "webpage_url": info.webpage_url,
            "title": info.title,
            "uploader": info.uploader,
            "duration": info.duration,
            "content": metadata,
            "access": {
                "method": info.access_method,
                "user_cookie_file": str(cookie_file) if cookie_file else None,
                "generated_public_visitor_cookie_used": bool(info.cookie_file and not cookie_file),
                "browser_profile_read": False,
            },
            "resume_steps": resume_steps,
            "output_dir_name": output_dir.name,
            "files": files,
            "status": "done",
            "created_at": now_iso(),
        } | {key: value for key, value in asr_result.items() if key != "files"}
        write_manifest(meta_dir, manifest)

        verification = verify_output(output_dir, files)
        report = {
            "ok": verification["ok"],
            "output_dir": str(output_dir.resolve()),
            "manifest": str((meta_dir / "manifest.json").resolve()),
            "raw_transcript": str((output_dir / files["原始逐字稿_md"]).resolve()),
            "raw_transcript_txt": str((output_dir / files["原始逐字稿_txt"]).resolve()),
            "srt": str((output_dir / files["字幕_srt"]).resolve()),
            "words": str((output_dir / files["词级时间戳_json"]).resolve()),
            "polished_transcript": str((output_dir / files["最终润色稿_待生成"]).resolve()),
            "needs_model_polish": True,
            "resume_steps": resume_steps,
            "verification": verification,
            "manifest_payload": manifest,
        }
        write_report(meta_dir, report)
        return report
    finally:
        if generated_cookie_file:
            generated_cookie_file.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one Douyin or Xiaohongshu link.")
    parser.add_argument("url_or_text", help="One Douyin or Xiaohongshu URL, or text containing one URL.")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--cookie-file", default=None)
    args = parser.parse_args()

    try:
        url = extract_url(args.url_or_text)
        cookie_file = Path(args.cookie_file).expanduser() if args.cookie_file else None
        if cookie_file and not cookie_file.exists():
            raise FileNotFoundError(f"cookie file does not exist: {cookie_file}")
        report = run(url, Path(args.output_root), args.model, cookie_file)
        print_report(report)
        return 0 if report["ok"] else 2
    except Exception as exc:
        payload = write_failure_report(Path(args.output_root), args.url_or_text, exc)
        print_report(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
