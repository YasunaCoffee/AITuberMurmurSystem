# -*- coding: utf-8 -*-
"""発話品質の評価・改善ループ。

- speech_quality : ルールベースの検査とサニタイズ（純粋関数）
- speech_logger  : 全発話の JSONL ログ
- guarded        : 生成→検査→リトライ→ログを1関数にまとめた実行時ゲート

オフラインの LLM 審査は scripts/judge_speech_log.py を参照。
"""
