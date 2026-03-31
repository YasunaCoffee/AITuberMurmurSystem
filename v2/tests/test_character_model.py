"""
TDD: Characterデータモデルのテスト

キャラクター（ペルソナ）をシステムから分離し、
動的に切り替え可能にするためのデータモデル。
"""
import os
import pytest
import tempfile
from dataclasses import asdict


class TestCharacterIdentity:
    """キャラクターの基本情報"""

    def test_identity_has_required_fields(self):
        from v2.models.character import CharacterIdentity

        identity = CharacterIdentity(
            name="蒼月ハヤテ",
            description="文学好きの一人暮らしの女性ゆうこさんの心の中の水槽で飼われているなにか",
            hashtag="#Aotsuki_Hayate_Data",
        )
        assert identity.name == "蒼月ハヤテ"
        assert identity.description != ""
        assert identity.hashtag == "#Aotsuki_Hayate_Data"
        assert identity.display_aliases == ()

    def test_identity_display_aliases_normalized_from_list(self):
        from v2.models.character import CharacterIdentity

        identity = CharacterIdentity(
            name="X",
            description="d",
            display_aliases=["a", "b"],
        )
        assert identity.display_aliases == ("a", "b")

    def test_identity_name_cannot_be_empty(self):
        from v2.models.character import CharacterIdentity

        with pytest.raises(ValueError):
            CharacterIdentity(name="", description="test", hashtag="")


class TestVoiceConfig:
    """音声合成の設定"""

    def test_voice_config_has_speaker_params(self):
        from v2.models.character import VoiceConfig

        voice = VoiceConfig(
            speaker_id=1,
            speaker_uuid="a82fc628-f166-427f-b568-4c4f94921629",
            speaker_name="蒼月ハヤテ",
            style_id=593129376,
            style_name="ノーマル",
            style_type="talk",
        )
        assert voice.speaker_id == 1
        assert voice.speaker_uuid == "a82fc628-f166-427f-b568-4c4f94921629"
        assert voice.style_name == "ノーマル"

    def test_voice_config_has_audio_params_with_defaults(self):
        from v2.models.character import VoiceConfig

        voice = VoiceConfig(
            speaker_id=1,
            speaker_uuid="test-uuid",
            speaker_name="テスト",
            style_id=1,
            style_name="ノーマル",
            style_type="talk",
        )
        # デフォルト値が設定されていること
        assert voice.speed_scale == 1.0
        assert voice.pitch_scale == 0.0
        assert voice.intonation_scale == 1.0
        assert voice.volume_scale == 1.0
        assert voice.pre_phoneme_length == 0.1
        assert voice.post_phoneme_length == 0.1
        assert voice.tempo_dynamics_scale == 1.0

    def test_voice_config_custom_audio_params(self):
        from v2.models.character import VoiceConfig

        voice = VoiceConfig(
            speaker_id=1,
            speaker_uuid="test-uuid",
            speaker_name="テスト",
            style_id=1,
            style_name="ノーマル",
            style_type="talk",
            speed_scale=0.96,
            tempo_dynamics_scale=1.8,
        )
        assert voice.speed_scale == 0.96
        assert voice.tempo_dynamics_scale == 1.8


class TestCharacterPrompts:
    """キャラクター固有のプロンプト設定"""

    def test_prompts_has_persona_path(self):
        from v2.models.character import CharacterPrompts

        prompts = CharacterPrompts(
            persona_prompt="prompts/persona_prompt.txt",
            master_prompt="prompts/master_prompt.txt",
        )
        assert prompts.persona_prompt == "prompts/persona_prompt.txt"
        assert prompts.master_prompt == "prompts/master_prompt.txt"

    def test_prompts_has_optional_mode_prompts(self):
        from v2.models.character import CharacterPrompts

        prompts = CharacterPrompts(
            persona_prompt="prompts/persona_prompt.txt",
            master_prompt="prompts/master_prompt.txt",
            monologue_prompt="prompts/normal_monologue.txt",
            greeting_prompt="prompts/initial_greeting.txt",
            ending_prompt="prompts/ending_greeting.txt",
        )
        assert prompts.monologue_prompt == "prompts/normal_monologue.txt"
        assert prompts.greeting_prompt == "prompts/initial_greeting.txt"
        assert prompts.ending_prompt == "prompts/ending_greeting.txt"

    def test_prompts_optional_fields_default_to_none(self):
        from v2.models.character import CharacterPrompts

        prompts = CharacterPrompts(
            persona_prompt="prompts/persona_prompt.txt",
            master_prompt="prompts/master_prompt.txt",
        )
        assert prompts.monologue_prompt is None
        assert prompts.greeting_prompt is None
        assert prompts.ending_prompt is None


class TestCharacterMemory:
    """キャラクターの記憶設定"""

    def test_memory_config(self):
        from v2.models.character import CharacterMemory

        memory = CharacterMemory(
            memory_file="txt/kioku_hayate.txt",
            history_file="txt/output_text_history.txt",
        )
        assert memory.memory_file == "txt/kioku_hayate.txt"
        assert memory.history_file == "txt/output_text_history.txt"

    def test_memory_history_file_optional(self):
        from v2.models.character import CharacterMemory

        memory = CharacterMemory(memory_file="txt/kioku_test.txt")
        assert memory.history_file is None


class TestCharacter:
    """キャラクター全体のデータモデル"""

    def _make_character(self):
        from v2.models.character import (
            Character,
            CharacterIdentity,
            VoiceConfig,
            CharacterPrompts,
            CharacterMemory,
        )

        return Character(
            identity=CharacterIdentity(
                name="蒼月ハヤテ",
                description="文学好きの一人暮らしの女性ゆうこさんの心の中の水槽で飼われているなにか",
                hashtag="#Aotsuki_Hayate_Data",
            ),
            voice=VoiceConfig(
                speaker_id=1,
                speaker_uuid="a82fc628-f166-427f-b568-4c4f94921629",
                speaker_name="蒼月ハヤテ",
                style_id=593129376,
                style_name="ノーマル",
                style_type="talk",
                speed_scale=0.96,
                tempo_dynamics_scale=1.8,
            ),
            prompts=CharacterPrompts(
                persona_prompt="prompts/persona_prompt.txt",
                master_prompt="prompts/master_prompt.txt",
            ),
            memory=CharacterMemory(
                memory_file="txt/kioku_hayate.txt",
                history_file="txt/output_text_history.txt",
            ),
        )

    def test_character_has_all_components(self):
        from v2.models.character import (
            Character,
            CharacterIdentity,
            VoiceConfig,
            CharacterPrompts,
            CharacterMemory,
        )

        char = self._make_character()
        assert isinstance(char.identity, CharacterIdentity)
        assert isinstance(char.voice, VoiceConfig)
        assert isinstance(char.prompts, CharacterPrompts)
        assert isinstance(char.memory, CharacterMemory)

    def test_character_name_shortcut(self):
        """character.name で identity.name にアクセスできる"""
        char = self._make_character()
        assert char.name == "蒼月ハヤテ"

    def test_character_is_serializable(self):
        """dictに変換できる（YAML/JSON保存用）"""
        char = self._make_character()
        d = asdict(char)
        assert d["identity"]["name"] == "蒼月ハヤテ"
        assert d["voice"]["speaker_id"] == 1
        assert d["prompts"]["persona_prompt"] == "prompts/persona_prompt.txt"
        assert d["memory"]["memory_file"] == "txt/kioku_hayate.txt"


class TestCharacterLoader:
    """YAMLからキャラクターを読み込む"""

    SAMPLE_YAML = """\
identity:
  name: "テストキャラ"
  description: "テスト用のキャラクター"
  hashtag: "#test"

voice:
  speaker_id: 99
  speaker_uuid: "test-uuid-1234"
  speaker_name: "テストキャラ"
  style_id: 1
  style_name: "ノーマル"
  style_type: "talk"
  speed_scale: 0.85

prompts:
  persona_prompt: "prompts/test_persona.txt"
  master_prompt: "prompts/test_master.txt"

memory:
  memory_file: "txt/kioku_test.txt"
"""

    def _write_yaml(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        f.write(content)
        f.close()
        return f.name

    def test_load_character_from_yaml(self):
        from v2.models.character import Character, load_character

        path = self._write_yaml(self.SAMPLE_YAML)
        try:
            char = load_character(path)
            assert isinstance(char, Character)
            assert char.name == "テストキャラ"
            assert char.voice.speaker_id == 99
            assert char.voice.speed_scale == 0.85
            assert char.prompts.persona_prompt == "prompts/test_persona.txt"
            assert char.memory.memory_file == "txt/kioku_test.txt"
        finally:
            os.unlink(path)

    def test_load_character_defaults_applied(self):
        """YAMLに書かなかったオプション項目はデフォルト値になる"""
        from v2.models.character import load_character

        path = self._write_yaml(self.SAMPLE_YAML)
        try:
            char = load_character(path)
            # voice defaults
            assert char.voice.pitch_scale == 0.0
            assert char.voice.tempo_dynamics_scale == 1.0
            # prompts optional
            assert char.prompts.monologue_prompt is None
            # memory optional
            assert char.memory.history_file is None
        finally:
            os.unlink(path)

    def test_load_character_file_not_found(self):
        from v2.models.character import load_character

        with pytest.raises(FileNotFoundError):
            load_character("/nonexistent/path.yaml")

    def test_load_character_ignores_unknown_fields_in_sections(self):
        """将来のYAML拡張フィールドがあっても無視して読める"""
        from v2.models.character import Character, load_character

        y = self.SAMPLE_YAML.replace(
            "  style_type: \"talk\"\n",
            "  style_type: \"talk\"\n  experimental_future_key: 123\n",
        )
        y = y.replace(
            "  hashtag: \"#test\"\n",
            "  hashtag: \"#test\"\n  future_identity_note: \"ignore me\"\n",
        )
        path = self._write_yaml(y)
        try:
            char = load_character(path)
            assert isinstance(char, Character)
            assert char.voice.speaker_id == 99
        finally:
            os.unlink(path)

    def test_load_character_missing_section_raises(self):
        from v2.models.character import load_character

        bad = """\
identity:
  name: "a"
  description: "b"
voice:
  speaker_id: 1
  speaker_uuid: "u"
  speaker_name: "n"
  style_id: 1
  style_name: "ノーマル"
  style_type: "talk"
memory:
  memory_file: "txt/m.txt"
"""
        path = self._write_yaml(bad)
        try:
            with pytest.raises(ValueError, match="prompts"):
                load_character(path)
        finally:
            os.unlink(path)

    def test_load_hayate_sample(self):
        """実際のサンプルYAML（蒼月ハヤテ）が読み込めること"""
        from v2.models.character import load_character

        hayate_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "characters", "hayate.yaml"
        )
        char = load_character(hayate_path)
        assert char.name == "蒼月ハヤテ"
        assert char.voice.speaker_id == 1
        assert char.voice.speed_scale == 0.96
        assert char.voice.tempo_dynamics_scale == 1.8
        assert "ハヤテ" in char.identity.display_aliases
