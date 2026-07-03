#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hayate-ft（軽量プロンプト）と 現行 gemma4-12b-ctx32k（重いプロンプト）を
同一お題で比較する評価スクリプト。

各お題について両モデルを叩き、応答テキスト・生成秒数・文字数を並べて表示し、
最後に平均生成秒数を集計する。ファインチューニングモデルへ移行する前に、
「速度」と「口調・内容の質」を数値と目視で判断するためのもの。

前提:
    - ollama serve が起動しており、hayate-ft と gemma4-12b-ctx32k が登録済み
    - .env に OPENAI_BASE_URL=http://localhost:11434/v1 が設定済み

使い方:
    uv run python scripts/eval_ft_vs_legacy.py
    uv run python scripts/eval_ft_vs_legacy.py --ft-only     # FT 側だけ（速い）
    uv run python scripts/eval_ft_vs_legacy.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openai  # noqa: E402

# config を import すると .env が load_dotenv される（OPENAI_BASE_URL 等）
from config import config  # noqa: E402
from murmur.runtime.character_runtime import (  # noqa: E402
    init_character,
    get_character,
    resolve_character_path,
)
from murmur.handlers.finetuned_prompt_builder import (  # noqa: E402
    FINETUNED_SYSTEM_PROMPT,
    build_monologue,
    build_comment_response,
    build_initial_greeting,
    build_ending_greeting,
)

FT_MODEL = os.getenv("EVAL_FT_MODEL", "hayate-ft")
LEGACY_MODEL = os.getenv("EVAL_LEGACY_MODEL", config.openai.models.response)
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
MAX_TOKENS = config.openai.api.max_tokens_default


def _client() -> "openai.OpenAI":
    return openai.OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=240)


def generate(model: str, system: str, user: str, temperature: float,
             reasoning_none: bool = False) -> tuple[str, float]:
    """1発話を生成し、(応答テキスト, 生成秒数) を返す。"""
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=MAX_TOKENS,
    )
    if reasoning_none:
        # gemma4:12b（thinking モデル）の思考出力を抑止。現行 openai_adapter と同条件。
        kwargs["extra_body"] = {"reasoning_effort": "none"}
    t0 = time.time()
    res = _client().chat.completions.create(**kwargs)
    dt = time.time() - t0
    return (res.choices[0].message.content or "").strip(), dt


def build_cases():
    """(ラベル, FTのuser文字列, legacyのタスク指示) のリストを返す。

    FT と legacy で意味的に同一のお題を与え、公平に比較する。legacy の
    タスク指示は MasterPromptManager でラップされ、system=persona と合わさって
    現行運用の重いプロンプトを再現する。
    """
    return [
        (
            "独り言C: コルモゴロフ複雑性",
            build_monologue("情報理論（コルモゴロフ複雑性）", mode="C"),
            "情報理論、特にコルモゴロフ複雑性について、あなたの考察を独り言として話してください。",
        ),
        (
            "独り言A: 大規模言語モデルの創発能力",
            build_monologue("大規模言語モデルの創発能力", mode="A"),
            "最近観測した興味深いデータとして、大規模言語モデルの創発能力について独り言を話してください。",
        ),
        (
            "独り言G: Outer Wildsの構造",
            build_monologue("『Outer Wilds』の知識駆動の進行", mode="G"),
            "好きな創作物の構造分析として、ゲーム『Outer Wilds』の知識駆動の進行について独り言を話してください。",
        ),
        (
            "コメント: 寝るの？",
            build_comment_response("そらまめ", "ハヤテって寝るの？"),
            "視聴者コメントに応答してください。そらまめさんから「ハヤテって寝るの？」というコメントが来ました。",
        ),
        (
            "コメント: 意識はデータか",
            build_comment_response("電脳藻類", "ハヤテにとって意識ってただのデータなんですか？"),
            "視聴者コメントに応答してください。電脳藻類さんから「ハヤテにとって意識ってただのデータなんですか？」というコメントが来ました。",
        ),
        (
            "開始挨拶: 記憶とはなにか",
            build_initial_greeting("記憶とはなにか"),
            "配信開始の挨拶をしてください。今日のテーマは「記憶とはなにか」です。",
        ),
        (
            "終了挨拶",
            build_ending_greeting("記憶は思い出すたびに書き換わるという話を視聴者の実体験を交えて掘り下げた"),
            "配信終了の挨拶をしてください。今日は、記憶は思い出すたびに書き換わるという話を視聴者と掘り下げました。",
        ),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ft-only", action="store_true", help="FT 側のみ実行")
    ap.add_argument("--legacy-only", action="store_true", help="legacy 側のみ実行")
    ap.add_argument("--json", default=None, help="結果を JSON で保存するパス")
    args = ap.parse_args()

    # legacy 側の重いプロンプトを再現するため、キャラクターと MasterPromptManager を用意
    legacy_system = ""
    mpm = None
    if not args.ft_only:
        init_character(str(ROOT / "characters" / "hayate.yaml"))
        from murmur.handlers.master_prompt_manager import MasterPromptManager
        legacy_system = Path(
            resolve_character_path(get_character().prompts.persona_prompt)
        ).read_text(encoding="utf-8")
        mpm = MasterPromptManager()

    print(f"FT model     : {FT_MODEL}  (temp 0.9, system 固定3行, master/記憶なし)")
    print(f"legacy model : {LEGACY_MODEL}  (temp 0.8, system=persona {len(legacy_system)}字 + master)")
    print(f"base_url     : {BASE_URL}")
    print("=" * 78)

    ft_times: list[float] = []
    legacy_times: list[float] = []
    records = []

    for label, ft_user, legacy_task in build_cases():
        print(f"\n■ {label}")
        rec = {"label": label}

        if not args.legacy_only:
            print(f"  FT     user: {ft_user}")
            try:
                text, dt = generate(FT_MODEL, FINETUNED_SYSTEM_PROMPT, ft_user,
                                    temperature=0.9, reasoning_none=False)
                ft_times.append(dt)
                rec["ft"] = {"user": ft_user, "text": text, "sec": round(dt, 2), "chars": len(text)}
                print(f"  FT     [{dt:5.1f}s / {len(text):3d}字] {text}")
            except Exception as e:  # noqa: BLE001
                rec["ft"] = {"error": str(e)}
                print(f"  FT     ERROR: {e}")

        if not args.ft_only:
            legacy_user = mpm.wrap_task_with_master_prompt(
                specific_task_prompt=legacy_task, current_mode="eval"
            )
            try:
                text, dt = generate(LEGACY_MODEL, legacy_system, legacy_user,
                                    temperature=0.8, reasoning_none=True)
                legacy_times.append(dt)
                rec["legacy"] = {
                    "prompt_chars": len(legacy_system) + len(legacy_user),
                    "text": text, "sec": round(dt, 2), "chars": len(text),
                }
                print(f"  legacy [{dt:5.1f}s / {len(text):3d}字] "
                      f"(prompt≈{len(legacy_system)+len(legacy_user)}字) {text}")
            except Exception as e:  # noqa: BLE001
                rec["legacy"] = {"error": str(e)}
                print(f"  legacy ERROR: {e}")

        records.append(rec)

    print("\n" + "=" * 78)
    if ft_times:
        print(f"FT     平均 {sum(ft_times)/len(ft_times):.1f}s  (n={len(ft_times)})")
    if legacy_times:
        print(f"legacy 平均 {sum(legacy_times)/len(legacy_times):.1f}s  (n={len(legacy_times)})")
    if ft_times and legacy_times:
        speedup = (sum(legacy_times)/len(legacy_times)) / (sum(ft_times)/len(ft_times))
        print(f"→ FT は legacy の約 {speedup:.1f} 倍速")

    if args.json:
        Path(args.json).write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n結果を保存: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
