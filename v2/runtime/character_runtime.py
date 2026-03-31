"""
キャラクターYAMLの読み込みとプロジェクト相対パス解決。

起動時に init_character() を一度呼び出してから、各モジュールは get_character() を参照する。
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from config import config

if TYPE_CHECKING:
    from v2.models.character import Character

_character: Optional["Character"] = None


def resolve_character_path(relative: str) -> str:
    """Character YAML 内のパス（プロジェクトルート相対）を絶対パスにする。"""
    rel = relative.replace("\\", "/").lstrip("/")
    return os.path.normpath(os.path.join(config.BASE_DIR, rel))


def init_character(yaml_path: Optional[str] = None):
    """
    キャラクター定義を読み込み、以降の get_character() に使う。
    yaml_path が None のときは config.character.yaml_path（config.BASE_DIR 相対）を使う。
    """
    global _character
    from v2.models.character import load_character

    if yaml_path:
        path = (
            yaml_path
            if os.path.isabs(yaml_path)
            else os.path.join(config.BASE_DIR, yaml_path.replace("\\", "/").lstrip("/"))
        )
    else:
        rel = getattr(config, "character", None)
        if rel is None or not getattr(rel, "yaml_path", None):
            path = os.path.join(config.BASE_DIR, "characters", "hayate.yaml")
        else:
            path = os.path.join(config.BASE_DIR, rel.yaml_path.replace("\\", "/").lstrip("/"))

    path = os.path.normpath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Character YAML not found: {path}")

    _character = load_character(path)
    print(f"[Character] Loaded: {_character.name} ({path})")
    return _character


def get_character() -> "Character":
    if _character is None:
        return init_character()
    return _character


def get_history_log_path() -> str:
    """発言履歴テキストの絶対パス（memory.history_file）。"""
    c = get_character()
    rel = c.memory.history_file or "txt/output_text_history.txt"
    return resolve_character_path(rel)


def get_monologue_basename() -> str:
    """PromptManager 用の独り言プロンプトファイル名（先頭候補）。"""
    c = get_character()
    if c.prompts.monologue_prompt:
        return os.path.basename(c.prompts.monologue_prompt.replace("\\", "/"))
    return "normal_monologue.txt"
