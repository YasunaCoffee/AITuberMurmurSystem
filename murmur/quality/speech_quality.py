# -*- coding: utf-8 -*-
"""hayate-ft の発話出力に対するルールベース品質検査。

LLM を使わない軽量な検査のみをここに置く（実行時に毎発話へ適用するため）。
LLM 審査員によるルーブリック採点はオフラインの scripts/judge_speech_log.py が担う。

検査は2段階:
    fatal   : 音声に載せてはいけない崩れ。リトライ対象（一人称崩れ・アシスタント
              口調・プロンプト形式の漏出・空/極端に短い・日本語でない）。
    warning : 載せられるが記録して改善材料にする（長すぎ・文の重複・直近発話との
              類似=思考ループ・出だしの固定化・括弧の不整合）。

finetuned_prompt_builder と同じく config / character_runtime に依存しない
純粋関数群として実装し、handler・スクリプト・テストのどこからでも使える。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

# 発話として許容する文字数（AivisSpeech で読み上げる1発話の目安）
MIN_CHARS = 15
MAX_CHARS = 400

# 直近発話との3-gram Jaccard 類似度がこの値以上なら「思考ループ」警告
SIMILARITY_THRESHOLD = 0.5
# 出だし何文字が一致したら「出だしの固定化」警告とするか
OPENING_LEN = 12

# ハヤテの一人称は「自分」（時々「僕」）。「私」で始まる語りは人格崩れ。
_FIRST_PERSON_RE = re.compile(r"(?:^|[^一-龠ぁ-んァ-ン])(私|わたし|ワタシ)(?:は|が|も|の|に|を|自身)")

# 素の instruct モデルに戻ってしまった兆候（ハヤテは情報生命体を公言しているので
# 「AI」「モデル」の語自体は許容し、アシスタント定型句のみを弾く）
_ASSISTANT_PHRASES = [
    "申し訳ありません",
    "申し訳ございません",
    "お手伝いでき",
    "お答えできません",
    "AIアシスタント",
    "アシスタントとして",
    "言語モデルとして",
    "ご質問ありがとうございます",
    "何かお手伝い",
]

# 学習時の user 形式がそのまま出力に漏れた兆候（v2 形式）
_PROMPT_ECHOES = [
    "独り言（",
    "視聴者コメントに応答",
    "視聴者相談に応答",
    "配信開始の挨拶をして",
    "配信終了の挨拶をして",
    "今日のハイライト:",
    "直前の発言:",
]

_JP_CHAR_RE = re.compile(r"[ぁ-んァ-ヶ一-龠ー]")

# コメントへの迎合（同意・称賛から入る応答）。ハヤテは自分の観測・仮説から
# 応じるキャラであり、相手を肯定してから話し始めるアシスタント的応答は
# 人格を薄める。冒頭付近に出た場合のみ警告する。
_SYCOPHANCY_RE = re.compile(
    r"(その通り|おっしゃる通り|仰る通り|さすが"
    r"|(?:いい|良い|鋭い|面白い|素晴らしい)(?:質問|問い|指摘|視点|コメント)"
    r"|(?:質問|問い|指摘|視点|コメント)[、,は]?\s*(?:面白い|鋭い|いい|良い|素晴らしい))"
)
# 冒頭何文字までに現れたら「出だしの迎合」とみなすか
_SYCOPHANCY_HEAD = 50


@dataclass
class QualityReport:
    """1回の生成テキストに対する検査結果。"""

    text: str
    fatal: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fatal


def sanitize_for_speech(text: str) -> str:
    """音声読み上げ前の機械的な清掃。

    Markdown 装飾・コードフェンス・URL・箇条書き記号など、TTS がそのまま
    読んでしまう表記を除去し、改行・連続空白を1つに畳む。
    """
    if not text:
        return ""
    t = str(text)
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)  # コードフェンス
    t = re.sub(r"https?://\S+", "", t)                   # URL
    t = re.sub(r"[*＊_#＃]{1,}", "", t)                  # 強調・見出し記号
    t = re.sub(r"^[\s]*[-・•●○]\s+", "", t, flags=re.MULTILINE)  # 箇条書き
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _ngrams(text: str, n: int = 3) -> set:
    return {text[i : i + n] for i in range(max(0, len(text) - n + 1))}


def similarity(a: str, b: str) -> float:
    """文字3-gramのJaccard類似度（0.0〜1.0）。思考ループ検出用。"""
    ga, gb = _ngrams(a), _ngrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def check_speech(
    text: str,
    kind: str = "monologue",
    recent: Optional[Iterable[str]] = None,
) -> QualityReport:
    """発話テキストを検査し QualityReport を返す。

    text   : sanitize_for_speech 済みのテキストを渡すこと。
    kind   : monologue / comment / initial_greeting / ending_greeting
    recent : 同じ kind の直近発話（新しい順でなくてよい）。類似ループ検出に使う。
    """
    report = QualityReport(text=text)
    f, w = report.fatal, report.warnings

    if not text:
        f.append("empty")
        return report
    if len(text) < MIN_CHARS:
        f.append(f"too_short({len(text)})")
    if len(text) > MAX_CHARS:
        w.append(f"too_long({len(text)})")

    # 日本語比率（英語や記号だけの応答を弾く）
    jp = len(_JP_CHAR_RE.findall(text))
    visible = len(re.sub(r"\s", "", text))
    if visible >= 20 and jp / visible < 0.3:
        f.append("non_japanese")

    if _FIRST_PERSON_RE.search(text):
        f.append("first_person")
    for p in _ASSISTANT_PHRASES:
        if p in text:
            f.append(f"assistant_tone({p})")
            break
    for p in _PROMPT_ECHOES:
        if p in text:
            f.append(f"prompt_echo({p})")
            break

    # コメント応答が同意・称賛から始まる＝迎合（人格が薄まる。改善ループで監視）
    if kind == "comment" and _SYCOPHANCY_RE.search(text[:_SYCOPHANCY_HEAD]):
        w.append("sycophancy_opener")

    # かぎ括弧の不整合（TTSは読めるが、字幕・ログで崩れる）
    if text.count("「") != text.count("」"):
        w.append("unbalanced_quotes")

    # 同一文の繰り返し（生成の詰まり）
    sentences = [s.strip() for s in re.split(r"[。！？]", text) if len(s.strip()) >= 8]
    if len(sentences) != len(set(sentences)):
        w.append("sentence_repeat")

    # 直近発話との類似（同じ話の反復＝思考ループ）と出だしの固定化
    for prev in recent or []:
        if not prev:
            continue
        sim = similarity(text, prev)
        if sim >= SIMILARITY_THRESHOLD:
            w.append(f"similar_to_recent({sim:.2f})")
            break
    for prev in recent or []:
        if prev and len(prev) >= OPENING_LEN and text[:OPENING_LEN] == prev[:OPENING_LEN]:
            w.append("opening_repeat")
            break

    return report
