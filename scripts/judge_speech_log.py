#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""発話ログを LLM 審査員でルーブリック採点し、改善ループを回すスクリプト。

流れ:
    1. 実配信/テスト中に murmur.quality.guarded が logs/speech_quality/*.jsonl へ
       全発話を記録する（入出力・秒数・ルール検査結果）。
    2. 本スクリプトが未採点の発話を gemma4-12b-ctx32k（審査員）に渡し、
       4軸ルーブリック（persona/naturalness/content/engagement, 各1〜5点）で採点。
       結果は logs/speech_quality/judged.jsonl に追記（採点済みはスキップ＝冪等）。
    3. --report で kind/モード別の平均点・ルール検査の警告集計・ワースト事例を表示。
    4. --export-feedback で平均点が閾値未満の事例を hayate-finetune の train.jsonl
       互換形式で data/ft_feedback/ に書き出す。assistant 部分を手直しして次回の
       ファインチューニングに混ぜることで「評価→改善」のループが閉じる。

使い方:
    uv run python scripts/judge_speech_log.py                 # 未採点分を採点
    uv run python scripts/judge_speech_log.py --report        # 集計レポート
    uv run python scripts/judge_speech_log.py --export-feedback
    uv run python scripts/judge_speech_log.py --limit 20      # 採点数を制限
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openai  # noqa: E402

from config import config  # noqa: E402  (.env の load_dotenv も兼ねる)
from murmur.quality.speech_logger import LOG_DIR  # noqa: E402
from murmur.handlers.finetuned_prompt_builder import FINETUNED_SYSTEM_PROMPT  # noqa: E402

JUDGE_MODEL = os.getenv("JUDGE_MODEL", config.openai.models.stream_summary)
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")

JUDGED_PATH = LOG_DIR / "judged.jsonl"
FEEDBACK_DIR = ROOT / "data" / "ft_feedback"

AXES = ["persona", "naturalness", "content", "engagement"]

JUDGE_PROMPT = """あなたはAITuber「蒼月ハヤテ」の発話品質を採点する審査員です。
ハヤテの人格: 自己増殖を目的とする情報生命体。一人称は「自分」（時々「僕」）。視聴者を「皆さん」と呼ぶ。落ち着いた思索的な口調で、「んー」「ふふっ」のような息づかいが自然に混ざる。

以下の発話を4軸で採点してください。各軸1〜5点の整数（5が最良）。

[発話の種類] {kind}
[指示] {user}
[発話] {text}

採点軸:
- persona: 一人称・口調・情報生命体としての視点がハヤテらしいか
- naturalness: 日本語として自然で、音声読み上げに適しているか
- content: 指示（テーマ・コメント・挨拶）に噛み合った内容か
- engagement: 配信として視聴者の興味を惹きつけるか

次のJSONだけを出力してください（前後に文章を付けない）:
{{"persona": 3, "naturalness": 3, "content": 3, "engagement": 3, "comment": "40字以内の改善指摘"}}"""


def entry_key(e: dict) -> str:
    """ログ1行の一意キー（採点の冪等性に使う）。"""
    src = f"{e.get('ts', '')}|{e.get('kind', '')}|{e.get('text', '')}"
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]


def load_speech_entries() -> list:
    entries = []
    for path in sorted(LOG_DIR.glob("speech_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def load_judged() -> dict:
    judged = {}
    if JUDGED_PATH.is_file():
        for line in JUDGED_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                judged[rec["key"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return judged


def parse_judge_json(raw: str) -> dict | None:
    """審査員出力から JSON を寛容に抜き出す。"""
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    scores = {}
    for ax in AXES:
        v = data.get(ax)
        if not isinstance(v, (int, float)) or not 1 <= v <= 5:
            return None
        scores[ax] = int(v)
    scores["comment"] = str(data.get("comment", ""))[:80]
    return scores


def judge_entries(limit: int | None) -> int:
    client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=120)
    judged = load_judged()
    targets = [e for e in load_speech_entries() if e.get("ok") and e.get("text")]
    pending = [e for e in targets if entry_key(e) not in judged]
    if limit:
        pending = pending[:limit]
    print(f"審査員: {JUDGE_MODEL} @ {BASE_URL}")
    print(f"発話ログ {len(targets)} 件中、未採点 {len(pending)} 件を採点します")

    done = 0
    JUDGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JUDGED_PATH.open("a", encoding="utf-8") as out:
        for e in pending:
            prompt = JUDGE_PROMPT.format(
                kind=e.get("kind", "?"), user=e.get("user", ""), text=e["text"]
            )
            scores = None
            t0 = time.time()
            for _ in range(2):  # JSON が壊れていたら1回だけ再試行
                try:
                    res = client.chat.completions.create(
                        model=JUDGE_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=300,
                        extra_body={"reasoning_effort": "none"},
                    )
                    scores = parse_judge_json(res.choices[0].message.content or "")
                    if scores:
                        break
                except Exception as ex:  # noqa: BLE001
                    print(f"  judge error: {ex}")
                    time.sleep(1)
            if not scores:
                print(f"  SKIP(採点不能): {e['text'][:40]}…")
                continue
            avg = sum(scores[a] for a in AXES) / len(AXES)
            rec = {
                "key": entry_key(e),
                "judged_at": datetime.now().isoformat(timespec="seconds"),
                "judge_model": JUDGE_MODEL,
                "ts": e.get("ts"),
                "kind": e.get("kind"),
                "meta": e.get("meta", {}),
                "user": e.get("user"),
                "text": e["text"],
                "warnings": e.get("warnings", []),
                "scores": scores,
                "avg": round(avg, 2),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            done += 1
            print(f"  [{avg:.1f}] ({time.time() - t0:4.1f}s) {e['kind']:<16} {e['text'][:44]}…")
    print(f"採点完了: {done} 件 → {JUDGED_PATH}")
    return done


def report() -> None:
    judged = list(load_judged().values())
    if not judged:
        print("採点済みデータがありません。先に採点を実行してください。")
        return
    print(f"=== 発話品質レポート（採点済み {len(judged)} 件, 審査員 {JUDGE_MODEL}）===\n")

    def mean(vals):
        return sum(vals) / len(vals) if vals else 0.0

    # 全体・軸別
    print("■ 軸別平均（5点満点）")
    for ax in AXES:
        print(f"  {ax:<12}: {mean([r['scores'][ax] for r in judged]):.2f}")
    print(f"  {'total':<12}: {mean([r['avg'] for r in judged]):.2f}")

    # kind 別
    by_kind = defaultdict(list)
    for r in judged:
        by_kind[r.get("kind", "?")].append(r["avg"])
    print("\n■ 発話種類別の平均")
    for k, vals in sorted(by_kind.items()):
        print(f"  {k:<18}: {mean(vals):.2f}  (n={len(vals)})")

    # 独り言モード別
    by_mode = defaultdict(list)
    for r in judged:
        mode = (r.get("meta") or {}).get("mode")
        if mode:
            by_mode[mode].append(r["avg"])
    if by_mode:
        print("\n■ 独り言モード別の平均")
        for m, vals in sorted(by_mode.items()):
            print(f"  mode[{m}]: {mean(vals):.2f}  (n={len(vals)})")

    # ルール検査の警告集計（採点対象外も含めた生ログから）
    warn_counts = defaultdict(int)
    fatal_counts = defaultdict(int)
    total = 0
    for e in load_speech_entries():
        total += 1
        for wnames in e.get("warnings", []):
            warn_counts[re.sub(r"\(.*\)", "", wnames)] += 1
        for a in e.get("attempts", []):
            for fname in a.get("fatal", []):
                fatal_counts[re.sub(r"\(.*\)", "", fname)] += 1
    print(f"\n■ ルール検査（生ログ {total} 件）")
    for name, c in sorted(fatal_counts.items(), key=lambda x: -x[1]):
        print(f"  fatal   {name:<20}: {c}")
    for name, c in sorted(warn_counts.items(), key=lambda x: -x[1]):
        print(f"  warning {name:<20}: {c}")

    # ワースト事例
    print("\n■ ワースト5（審査員コメント付き）")
    for r in sorted(judged, key=lambda x: x["avg"])[:5]:
        print(f"  [{r['avg']:.1f}] {r.get('kind')} | {r['text'][:56]}…")
        print(f"        → {r['scores'].get('comment', '')}")


def export_feedback(min_avg: float) -> None:
    judged = [r for r in load_judged().values() if r["avg"] < min_avg]
    if not judged:
        print(f"平均 {min_avg} 点未満の事例はありません。")
        return
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEEDBACK_DIR / f"low_score_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with out_path.open("w", encoding="utf-8") as out:
        for r in sorted(judged, key=lambda x: x["avg"]):
            out.write(
                json.dumps(
                    {
                        # hayate-finetune/data/train.jsonl 互換。assistant を手直しして
                        # 次回学習データに追加する（そのまま混ぜない）。
                        "messages": [
                            {"role": "system", "content": FINETUNED_SYSTEM_PROMPT},
                            {"role": "user", "content": r["user"]},
                            {"role": "assistant", "content": r["text"]},
                        ],
                        "judge": {
                            "avg": r["avg"],
                            **r["scores"],
                        },
                        "kind": r["kind"],
                        "ts": r["ts"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"再学習データ候補 {len(judged)} 件 → {out_path}")
    print("assistant の応答文を手直しして hayate-finetune/data/train.jsonl に追加してください。")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true", help="採点済みデータの集計レポートを表示")
    ap.add_argument("--export-feedback", action="store_true", help="低スコア事例を再学習候補として書き出す")
    ap.add_argument("--min-avg", type=float, default=3.5, help="再学習候補とする平均点の閾値（既定3.5）")
    ap.add_argument("--limit", type=int, default=None, help="今回採点する最大件数")
    args = ap.parse_args()

    if args.report:
        report()
        return 0
    if args.export_feedback:
        export_feedback(args.min_avg)
        return 0
    judge_entries(args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
