"""
Characterデータモデル

キャラクター（ペルソナ）の全情報を1つの構造に集約し、
システムから分離して動的に切り替え可能にする。

YAML は将来の拡張のため未知のトップレベルキー・各セクション内の未知フィールドを
無視できる（dataclass に存在するフィールドのみ採用）。
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Optional, Type

import yaml


def _subset_for_dataclass(cls: Type[Any], data: dict[str, Any], *, section: str) -> dict[str, Any]:
    """YAML の dict から dataclass が受け取れるキーのみ抽出する。"""
    if not isinstance(data, dict):
        raise TypeError(f"{section}: オブジェクトである必要があります（実際は {type(data).__name__}）")
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


@dataclass(frozen=True)
class CharacterIdentity:
    """キャラクターの基本情報"""

    name: str
    description: str
    hashtag: str = ""
    # 会話ログ・サマリー等で「AI側の発言」として扱う別名（例: 短縮名）
    display_aliases: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.name:
            raise ValueError("name は空にできません")
        da = self.display_aliases
        if da is None:
            object.__setattr__(self, "display_aliases", ())
        elif isinstance(da, list):
            object.__setattr__(self, "display_aliases", tuple(str(x) for x in da))
        elif isinstance(da, tuple):
            pass
        else:
            raise TypeError("display_aliases は文字列のリストまたはタプルである必要があります")


@dataclass(frozen=True)
class VoiceConfig:
    """音声合成の設定"""

    speaker_id: int
    speaker_uuid: str
    speaker_name: str
    style_id: int
    style_name: str
    style_type: str
    speed_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    volume_scale: float = 1.0
    pre_phoneme_length: float = 0.1
    post_phoneme_length: float = 0.1
    tempo_dynamics_scale: float = 1.0


@dataclass(frozen=True)
class CharacterPrompts:
    """キャラクター固有のプロンプト設定"""

    persona_prompt: str
    master_prompt: str
    monologue_prompt: Optional[str] = None
    greeting_prompt: Optional[str] = None
    ending_prompt: Optional[str] = None


@dataclass(frozen=True)
class CharacterMemory:
    """キャラクターの記憶設定"""

    memory_file: str
    history_file: Optional[str] = None


@dataclass(frozen=True)
class Character:
    """キャラクター全体のデータモデル"""

    identity: CharacterIdentity
    voice: VoiceConfig
    prompts: CharacterPrompts
    memory: CharacterMemory

    @property
    def name(self) -> str:
        return self.identity.name


def load_character(path: str) -> Character:
    """
    YAMLファイルから Character を読み込む。

    Raises:
        FileNotFoundError: ファイルが存在しない
        ValueError: 必須セクション欠落・型不正
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Character YAML が空です: {path}")
    if not isinstance(raw, dict):
        raise ValueError(f"Character YAML のルートはマップである必要があります: {path}")

    required_sections = ("identity", "voice", "prompts", "memory")
    for key in required_sections:
        if key not in raw:
            raise ValueError(f"Character YAML '{path}': 必須セクション '{key}' がありません")

    identity_data = _subset_for_dataclass(CharacterIdentity, raw["identity"], section="identity")
    voice_data = _subset_for_dataclass(VoiceConfig, raw["voice"], section="voice")
    prompts_data = _subset_for_dataclass(CharacterPrompts, raw["prompts"], section="prompts")
    memory_data = _subset_for_dataclass(CharacterMemory, raw["memory"], section="memory")

    return Character(
        identity=CharacterIdentity(**identity_data),
        voice=VoiceConfig(**voice_data),
        prompts=CharacterPrompts(**prompts_data),
        memory=CharacterMemory(**memory_data),
    )
