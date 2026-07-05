# -*- coding: utf-8 -*-
"""発話生成の実行時ゲート: 生成 → サニタイズ → 検査 → 必要ならリトライ → ログ。

handler は openai_adapter.create_chat_for_response(prompt) の代わりに
generate_speech(adapter, prompt, kind=...) を呼ぶだけでよい。

    response, report = generate_speech(self.openai_adapter, prompt, kind="monologue")
    if response is None:
        # 全試行が fatal → handler 側の既存フォールバック文へ

hayate-ft は1〜6秒/発話なのでリトライのコストは小さい。fatal（一人称崩れ・
アシスタント口調・形式漏出など）だけがリトライ対象で、warning は記録のみ。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional, Tuple

from murmur.quality.speech_quality import (
    QualityReport,
    check_speech,
    sanitize_for_speech,
)
from murmur.quality.speech_logger import log_speech

# fatal 検出時の再生成回数を含む最大試行数
MAX_ATTEMPTS = 2

# 類似ループ検出用に kind ごとに直近発話を保持（プロセス内共有）
_RECENT_MAX = 8
_recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_RECENT_MAX))
_recent_lock = threading.Lock()


def _remember(kind: str, text: str) -> None:
    with _recent_lock:
        _recent[kind].append(text)


def _recent_texts(kind: str) -> list:
    with _recent_lock:
        return list(_recent[kind])


def generate_speech(
    adapter,
    prompt: str,
    kind: str,
    meta: Optional[Dict[str, Any]] = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> Tuple[Optional[str], QualityReport]:
    """検査付きで発話を1つ生成する。

    Returns:
        (text, report): text はサニタイズ済み発話。全試行 fatal なら None
        （handler の既存フォールバックに委ねる）。report は採用した試行の検査結果。
    """
    recent = _recent_texts(kind)
    attempts = []  # (report, elapsed_sec, raw)

    for i in range(max_attempts):
        t0 = time.time()
        try:
            raw = adapter.create_chat_for_response(prompt) or ""
        except Exception as e:  # noqa: BLE001
            print(f"[quality] LLM call failed (attempt {i + 1}): {e}")
            raw = ""
        elapsed = time.time() - t0

        report = check_speech(sanitize_for_speech(raw), kind=kind, recent=recent)
        attempts.append((report, elapsed, raw))

        if report.ok:
            break
        print(
            f"[quality] {kind} attempt {i + 1}/{max_attempts} rejected: "
            f"fatal={report.fatal} warnings={report.warnings}"
        )

    # fatal が最少 → warning が最少 の順で最良の試行を採用
    best_idx = min(
        range(len(attempts)),
        key=lambda i: (len(attempts[i][0].fatal), len(attempts[i][0].warnings)),
    )
    best, _, _ = attempts[best_idx]

    log_speech(
        {
            "kind": kind,
            "model": getattr(adapter, "model_response", None),
            "meta": meta or {},
            "user": prompt,
            "text": best.text,
            "ok": best.ok,
            "fatal": best.fatal,
            "warnings": best.warnings,
            "chosen": best_idx,
            "attempts": [
                {
                    "sec": round(sec, 2),
                    "chars": len(rep.text),
                    "fatal": rep.fatal,
                    "warnings": rep.warnings,
                }
                for rep, sec, _ in attempts
            ],
        }
    )

    if not best.ok:
        return None, best

    _remember(kind, best.text)
    return best.text, best
