"""
Characterデータモデル

キャラクター（ペルソナ）の全情報を1つの構造に集約し、
システムから分離して動的に切り替え可能にする。
"""
from dataclasses import dataclass
from typing import Optional

import yaml


@dataclass(frozen=True)
class CharacterIdentity:
    """キャラクターの基本情報"""
    name: str
    description: str
    hashtag: str = ""

    def __post_init__(self):
        if not self.name:
            raise ValueError("name は空にできません")


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
    """YAMLファイルからCharacterを読み込む"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Character(
        identity=CharacterIdentity(**data["identity"]),
        voice=VoiceConfig(**data["voice"]),
        prompts=CharacterPrompts(**data["prompts"]),
        memory=CharacterMemory(**data["memory"]),
    )
