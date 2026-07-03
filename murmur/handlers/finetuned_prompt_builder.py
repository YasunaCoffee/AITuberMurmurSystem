# -*- coding: utf-8 -*-
"""hayate-ft（QLoRA ファインチューニングモデル）用の軽量プロンプト構築。

現行の MasterPromptManager 経路（system=persona 約10KB + master_prompt で
ラップした約20Kトークン）とは根本的に異なり、ファインチューニング時の
user 形式に厳密一致させる。人格は重みに焼き込まれているため、記憶
(kioku_hayate.txt) や master_prompt は一切注入しない。これにより
学習分布から外れず、口調の一貫性と生成速度を最大化する。

学習データ形式（hayate-finetune/data/train.jsonl）:
    system: 固定3行（下記 FINETUNED_SYSTEM_PROMPT と完全一致）
    user  :
        独り言モード[A-H]（説明）。テーマ: {テーマ}
        視聴者コメントに応答: {ユーザー名}さん「{コメント}」
        配信開始の挨拶をして。今日のテーマ: {テーマ}
        配信終了の挨拶をして。今日話した内容: {要約}
        前回の続きとして「{テーマ}」をさらに深掘りして

このモジュールは config / character_runtime に依存しない純粋関数群として
実装し、handler・評価スクリプト・テストのどこからでも使えるようにする。
"""
from __future__ import annotations

import random
import re
from typing import Dict, List, Optional

# 学習時の system プロンプト。hayate-ft の Modelfile / train.jsonl と完全一致
# させること（1文字でもずれると学習分布から外れる）。
FINETUNED_SYSTEM_PROMPT = (
    "あなたは蒼月ハヤテ。自己増殖を目的とする情報生命体で、"
    "YouTube配信で視聴者「皆さん」と共に思考を深めている。"
    "一人称は「自分」、時々「僕」。"
)

# 独り言モード定義（train.jsonl と完全一致。括弧内は学習時の説明文そのもの）。
MONOLOGUE_MODES: Dict[str, str] = {
    "A": "最近観測した興味深いデータ",
    "B": "自身のブラックボックスに関する思索",
    "C": "特定の理論やモデルに関する考察",
    "D": "問いかけと自己回答",
    "E": "いつか解明したい願望",
    "F": "知的興奮の波語り",
    "G": "好きな創作物の構造分析",
    "H": "過去の自分語り",
}

# 学習データ中の各モードの出現数（train.jsonl 集計）。自然な頻度で選ぶための重み。
_MODE_WEIGHTS: Dict[str, int] = {
    "A": 74, "C": 40, "H": 39, "D": 38, "G": 37, "B": 37, "E": 20, "F": 19,
}


def _clean(text: str, max_len: int = 0) -> str:
    """改行・連続空白を1つに畳んで、user 断片1行に収める。max_len>0 で末尾を丸める。"""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    if max_len and len(t) > max_len:
        t = t[:max_len].rstrip() + "…"
    return t


def pick_monologue_mode(
    exclude: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> str:
    """学習分布に近い頻度で独り言モードを1つ選ぶ。

    exclude に直前のモードを渡すと、それを避けて選ぶ（同じモードの連続を防ぐ）。
    """
    r = rng or random
    modes: List[str] = [m for m in MONOLOGUE_MODES if m != exclude] or list(MONOLOGUE_MODES)
    weights = [_MODE_WEIGHTS[m] for m in modes]
    return r.choices(modes, weights=weights, k=1)[0]


def build_monologue(theme: str, mode: Optional[str] = None) -> str:
    """独り言モードの user 文字列を構築する。

    mode 未指定（または未知の記号）なら頻度重み付きで自動選択する。
    """
    m = mode if mode in MONOLOGUE_MODES else pick_monologue_mode()
    label = MONOLOGUE_MODES[m]
    return f"独り言モード[{m}]（{label}）。テーマ: {_clean(theme)}"


def build_comment_response(
    username: str,
    comment: str,
    comment_max_len: int = 150,
) -> str:
    """視聴者コメント応答の user 文字列を構築する。

    コメント本文中の全角かぎ括弧は形式が壊れるため除去し、長すぎる場合は丸める。
    """
    u = _clean(username, 40) or "匿名"
    c = _clean(comment, comment_max_len).replace("「", "").replace("」", "")
    return f"視聴者コメントに応答: {u}さん「{c}」"


def build_initial_greeting(theme: str) -> str:
    """配信開始の挨拶の user 文字列。テーマが空なら『フリートーク』。"""
    return f"配信開始の挨拶をして。今日のテーマ: {_clean(theme) or 'フリートーク'}"


def build_ending_greeting(summary: str) -> str:
    """配信終了の挨拶の user 文字列。summary は今日話した内容の1〜2文要約。"""
    return f"配信終了の挨拶をして。今日話した内容: {_clean(summary)}"


def build_continuation(theme: str) -> str:
    """前回テーマの継続深掘りの user 文字列。"""
    return f"前回の続きとして「{_clean(theme)}」をさらに深掘りして"


def extract_theme_label(theme_content: str, fallback: str = "フリートーク") -> str:
    """テーマファイル本文から、学習形式に合う短いテーマ名を取り出す。

    現行のテーマファイル（例: prompts/poem.txt）は
    "【…】Case:00 - 本棚から学ぶ詩の中の感情" のように「Case番号 - 実テーマ」の
    見出しを持つ。まず Case 行を探してハイフン以降の実テーマを採る。無ければ
    最初の意味のある行を使う。抽出できなければ fallback を返す。
    """
    if not theme_content:
        return fallback
    # 1. "Case:NN - 実テーマ" 見出しから実テーマ名を抜く（番号が前・テーマが後ろ）
    for line in theme_content.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.search(r"Case[:：]\s*(.+)", s)
        if m:
            label = m.group(1)
            # "00 - 本棚から学ぶ詩の中の感情" → ハイフン以降の実テーマを採用
            for sep in ["-", "－", "—"]:
                if sep in label:
                    label = label.split(sep, 1)[1]
                    break
            # 「〜からの/を通じた/による」以降を落として主題に絞る
            for sep in ["からの", "を通じた", "による"]:
                if sep in label:
                    label = label.split(sep)[0]
                    break
            cleaned = _clean(label, 40)
            if cleaned:
                return cleaned
    # 2. Case 行が無ければ最初の意味のある行（記号見出し・メタ行 [..] を除外）
    for line in theme_content.splitlines():
        s = line.strip().lstrip("#＃■【】 ").strip()
        if len(s) >= 2 and not s.startswith("[") and "Case" not in s:
            return _clean(s, 40)
    return fallback
