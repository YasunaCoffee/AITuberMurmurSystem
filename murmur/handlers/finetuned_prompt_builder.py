# -*- coding: utf-8 -*-
"""hayate-ft（QLoRA ファインチューニングモデル）用の軽量プロンプト構築。

現行の MasterPromptManager 経路（system=persona 約10KB + master_prompt で
ラップした約20Kトークン）とは根本的に異なり、ファインチューニング時の
user 形式に厳密一致させる。人格は重みに焼き込まれているため、記憶
(kioku_hayate.txt) や master_prompt は一切注入しない。これにより
学習分布から外れず、口調の一貫性と生成速度を最大化する。

学習データ形式（hayate-finetune/data/raw_v3 世代 = v2 形式）:
    system: 固定3行（下記 FINETUNED_SYSTEM_PROMPT と完全一致）
    user  :
        独り言（{mode}）。テーマ: {テーマ}。直前の発言:「{前断片 or （配信開始直後）}」
        視聴者コメントに応答: {名前}さん「{コメント}」。話題: {話題}。直前の発言:「{...}」
        視聴者相談に応答: {名前}さん「{相談}」。直前の発言:「{...}」
        配信開始の挨拶をして。今日のテーマ: {テーマ}
        配信終了の挨拶をして。今日のハイライト: {1〜2個の要約}

    {mode} は ConversationMode の値と同じ文字列
    (normal_monologue / themed_monologue / chill_chat / episode_deep_dive)。
    「直前の発言」に前の発話断片を渡すことで思考のチェーン構造を再現する。

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

# 「直前の発言」が無い時（配信開始直後）に学習データで使われるマーカー。
STREAM_START_MARKER = "（配信開始直後）"

# 学習データに登場する独り言モード名と出現数（train.jsonl v3 集計）。
# 値は ConversationMode.*.value と同じ文字列。
MONOLOGUE_MODES: Dict[str, int] = {
    "normal_monologue": 172,
    "themed_monologue": 44,
    "chill_chat": 44,
    "episode_deep_dive": 4,  # 仕様上は有効だがデータでは希少
}

# 「直前の発言」として渡す前断片の最大長（学習時の断片は 50〜250字）
_PREV_MAX = 250


def _clean(text: str, max_len: int = 0) -> str:
    """改行・連続空白を1つに畳んで、user 断片1行に収める。max_len>0 で末尾を丸める。"""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    if max_len and len(t) > max_len:
        t = t[:max_len].rstrip() + "…"
    return t


def _prev(last_utterance: Optional[str]) -> str:
    """「直前の発言」フィールド値。無ければ配信開始直後マーカー。"""
    return _clean(last_utterance, _PREV_MAX) or STREAM_START_MARKER


def pick_monologue_mode(
    exclude: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> str:
    """学習分布に近い頻度で独り言モードを1つ選ぶ（mode 不明時のフォールバック）。

    通常は ModeManager.current_mode.value をそのまま使うこと。
    exclude に直前のモードを渡すと、それを避けて選ぶ。
    """
    r = rng or random
    modes: List[str] = [m for m in MONOLOGUE_MODES if m != exclude] or list(MONOLOGUE_MODES)
    weights = [MONOLOGUE_MODES[m] for m in modes]
    return r.choices(modes, weights=weights, k=1)[0]


def build_monologue(
    theme: str,
    mode: Optional[str] = None,
    last_utterance: Optional[str] = None,
) -> str:
    """独り言の user 文字列（v2 チェーン形式）を構築する。

    mode は ConversationMode の値。未知/未指定なら頻度重み付きで選ぶ。
    last_utterance に直前の発話を渡すと思考が連続する（チェーン構造）。
    """
    m = mode if mode in MONOLOGUE_MODES else pick_monologue_mode()
    return f"独り言（{m}）。テーマ: {_clean(theme)}。直前の発言:「{_prev(last_utterance)}」"


def build_comment_response(
    username: str,
    comment: str,
    topic: Optional[str] = None,
    last_utterance: Optional[str] = None,
    comment_max_len: int = 150,
) -> str:
    """視聴者コメント応答の user 文字列（v2 形式）を構築する。

    topic はいまの配信の話題（テーマラベル）。コメント本文中の全角かぎ括弧は
    形式が壊れるため除去し、長すぎる場合は丸める。
    """
    u = _clean(username, 40) or "匿名"
    c = _clean(comment, comment_max_len).replace("「", "").replace("」", "")
    t = _clean(topic, 60) or "フリートーク"
    return (
        f"視聴者コメントに応答: {u}さん「{c}」。"
        f"話題: {t}。直前の発言:「{_prev(last_utterance)}」"
    )


def build_consultation(
    username: str,
    consultation: str,
    last_utterance: Optional[str] = None,
    max_len: int = 200,
) -> str:
    """視聴者相談応答の user 文字列（v2 形式）。悩み系コメント向け。"""
    u = _clean(username, 40) or "匿名"
    c = _clean(consultation, max_len).replace("「", "").replace("」", "")
    return f"視聴者相談に応答: {u}さん「{c}」。直前の発言:「{_prev(last_utterance)}」"


def build_initial_greeting(theme: str) -> str:
    """配信開始の挨拶の user 文字列。テーマが空なら『フリートーク』。"""
    return f"配信開始の挨拶をして。今日のテーマ: {_clean(theme) or 'フリートーク'}"


def build_ending_greeting(summary: str) -> str:
    """配信終了の挨拶の user 文字列。summary は今日のハイライト1〜2個の要約。"""
    return f"配信終了の挨拶をして。今日のハイライト: {_clean(summary)}"


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
