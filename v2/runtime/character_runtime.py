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
_loaded_yaml_path: Optional[str] = None


def reset_character_runtime() -> None:
    """テスト用: 読み込み済みキャラをクリアする（次の get_character で再 init）。"""
    global _character, _loaded_yaml_path
    _character = None
    _loaded_yaml_path = None


def get_loaded_character_yaml_path() -> Optional[str]:
    """最後に init_character で読み込んだ YAML の絶対パス。未初期化なら None。"""
    return _loaded_yaml_path


def resolve_character_path(relative: str) -> str:
    """Character YAML 内のパス（プロジェクトルート相対）を絶対パスにする。"""
    rel = relative.replace("\\", "/").lstrip("/")
    return os.path.normpath(os.path.join(config.BASE_DIR, rel))


def init_character(yaml_path: Optional[str] = None):
    """
    キャラクター定義を読み込み、以降の get_character() に使う。
    yaml_path が None のときは config.character.yaml_path（config.BASE_DIR 相対）を使う。
    """
    global _character, _loaded_yaml_path
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

    _loaded_yaml_path = path
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


def get_ai_speaker_labels() -> frozenset[str]:
    """
    会話ログ上で「AI側の発言」として扱う話者ラベル集合。
    identity.name / voice.speaker_name / 固定の AI に加え、identity.display_aliases を含む。
    """
    c = get_character()
    labels = {c.name, c.voice.speaker_name, "AI"}
    labels.update(c.identity.display_aliases)
    if "ハヤテ" in c.name:
        labels.add("ハヤテ")
    return frozenset(labels)
