"""ランタイム初期化（キャラクター読み込みなど）。"""

from .character_runtime import (
    get_ai_speaker_labels,
    get_character,
    get_history_log_path,
    get_monologue_basename,
    init_character,
    reset_character_runtime,
    resolve_character_path,
)

__all__ = [
    "get_ai_speaker_labels",
    "get_character",
    "get_history_log_path",
    "get_monologue_basename",
    "init_character",
    "reset_character_runtime",
    "resolve_character_path",
]
