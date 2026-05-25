from __future__ import annotations

import json
from pathlib import Path


def write_report(output_dir: Path, payload: dict) -> Path:
    path = output_dir / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def print_report(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)

