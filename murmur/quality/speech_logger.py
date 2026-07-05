# -*- coding: utf-8 -*-
"""発話の入出力と品質検査結果を JSONL に記録する。

1発話 = 1行。scripts/judge_speech_log.py がこのログを読んで LLM 審査員に
ルーブリック採点させ、低スコア事例を再学習データ候補として書き出す。
ログはローカル専用（.gitignore 対象）。
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# リポジトリルート/logs/speech_quality/speech_YYYYMMDD.jsonl
LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "speech_quality"

_lock = threading.Lock()


def log_path(now: datetime | None = None) -> Path:
    d = (now or datetime.now()).strftime("%Y%m%d")
    return LOG_DIR / f"speech_{d}.jsonl"


def log_speech(entry: Dict[str, Any]) -> None:
    """1発話分のレコードを追記する。失敗しても配信は止めない。

    DISABLE_SPEECH_LOG=1 で無効化（ユニットテストがログを汚さないように）。
    """
    if os.environ.get("DISABLE_SPEECH_LOG"):
        return
    try:
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **entry}
        path = log_path()
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                # default=str: Mock やパスなど非プリミティブが混ざっても記録を落とさない
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[speech_logger] Warning: failed to write log: {e}")
