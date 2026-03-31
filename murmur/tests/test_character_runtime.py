"""
TDD: character_runtime の仕様

init_character / resolve_character_path / get_history_log_path / get_monologue_basename
の振る舞いをテストで固定する。グローバル状態は reset_character_runtime で隔離する。
"""
import os
import tempfile

import pytest

from config import config
from murmur.runtime.character_runtime import (
    get_ai_speaker_labels,
    get_character,
    get_history_log_path,
    get_monologue_basename,
    init_character,
    reset_character_runtime,
    resolve_character_path,
)


MINIMAL_YAML = """\
identity:
  name: "TDDテストキャラ"
  description: "TDD用"
  hashtag: "#tdd"
  display_aliases:
    - "TDD略"

voice:
  speaker_id: 42
  speaker_uuid: "00000000-0000-0000-0000-000000000042"
  speaker_name: "TDDテストキャラ"
  style_id: 100
  style_name: "ノーマル"
  style_type: "talk"

prompts:
  persona_prompt: "prompts/persona_prompt.txt"
  master_prompt: "prompts/master_prompt.txt"
  monologue_prompt: "prompts/custom_monologue.txt"

memory:
  memory_file: "txt/kioku_tdd.txt"
  history_file: "txt/history_tdd.txt"
"""

YAML_NO_MONO = MINIMAL_YAML.replace(
    "  monologue_prompt: \"prompts/custom_monologue.txt\"\n", ""
)


@pytest.fixture
def restore_default_character():
    """テストで reset したあと、既定のキャラに戻す。"""
    yield
    reset_character_runtime()
    init_character()


def _write_utf8_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return f.name


class TestResolveCharacterPath:
    def test_joins_project_root(self):
        p = resolve_character_path("prompts/foo.txt")
        assert p == os.path.normpath(os.path.join(config.BASE_DIR, "prompts", "foo.txt"))

    def test_strips_leading_slash(self):
        p = resolve_character_path("/txt/bar.txt")
        assert p == os.path.normpath(os.path.join(config.BASE_DIR, "txt", "bar.txt"))

    def test_normalizes_backslashes_in_input(self):
        p = resolve_character_path(r"txt\baz.txt")
        assert p == os.path.normpath(os.path.join(config.BASE_DIR, "txt", "baz.txt"))


class TestInitCharacter:
    def test_loads_from_absolute_path(self, restore_default_character):
        path = _write_utf8_yaml(MINIMAL_YAML)
        try:
            reset_character_runtime()
            c = init_character(path)
            assert c.name == "TDDテストキャラ"
            assert c.voice.speaker_id == 42
        finally:
            os.unlink(path)

    def test_loads_from_project_relative_path(self, restore_default_character):
        path = _write_utf8_yaml(MINIMAL_YAML)
        rel = os.path.relpath(path, config.BASE_DIR)
        try:
            reset_character_runtime()
            c = init_character(rel)
            assert c.name == "TDDテストキャラ"
        finally:
            os.unlink(path)

    def test_raises_when_file_missing(self, restore_default_character):
        reset_character_runtime()
        with pytest.raises(FileNotFoundError, match="Character YAML not found"):
            init_character(os.path.join(config.BASE_DIR, "characters", "__does_not_exist__.yaml"))


class TestGetCharacterLazyInit:
    def test_get_character_calls_init_when_unset(self, restore_default_character):
        reset_character_runtime()
        c = get_character()
        assert c.name
        assert c.voice.speaker_id is not None


class TestGetHistoryLogPath:
    def test_uses_memory_history_file(self, restore_default_character):
        path = _write_utf8_yaml(MINIMAL_YAML)
        try:
            reset_character_runtime()
            init_character(path)
            expected = resolve_character_path("txt/history_tdd.txt")
            assert get_history_log_path() == expected
        finally:
            os.unlink(path)

    def test_defaults_when_history_file_none(self, restore_default_character):
        yaml_no_hist = MINIMAL_YAML.replace(
            "  history_file: \"txt/history_tdd.txt\"\n", ""
        )
        path = _write_utf8_yaml(yaml_no_hist)
        try:
            reset_character_runtime()
            init_character(path)
            expected = resolve_character_path("txt/output_text_history.txt")
            assert get_history_log_path() == expected
        finally:
            os.unlink(path)


class TestGetMonologueBasename:
    def test_returns_basename_of_monologue_prompt(self, restore_default_character):
        path = _write_utf8_yaml(MINIMAL_YAML)
        try:
            reset_character_runtime()
            init_character(path)
            assert get_monologue_basename() == "custom_monologue.txt"
        finally:
            os.unlink(path)

    def test_returns_default_when_monologue_omitted(self, restore_default_character):
        path = _write_utf8_yaml(YAML_NO_MONO)
        try:
            reset_character_runtime()
            init_character(path)
            assert get_monologue_basename() == "normal_monologue.txt"
        finally:
            os.unlink(path)


class TestGetAiSpeakerLabels:
    def test_includes_name_voice_aliases_and_ai(self, restore_default_character):
        reset_character_runtime()
        init_character()
        lab = get_ai_speaker_labels()
        assert "AI" in lab
        assert "蒼月ハヤテ" in lab
        assert "ハヤテ" in lab

    def test_includes_yaml_display_aliases(self, restore_default_character):
        path = _write_utf8_yaml(MINIMAL_YAML)
        try:
            reset_character_runtime()
            init_character(path)
            lab = get_ai_speaker_labels()
            assert "TDD略" in lab
            assert "TDDテストキャラ" in lab
        finally:
            os.unlink(path)


class TestAivisVoiceConfigToDict:
    """Aivis 用 dict 変換が VoiceConfig と整合する（音声ランタイムの契約）。"""

    def test_maps_all_voice_fields_used_by_aivis(self, restore_default_character):
        from murmur.models.character import VoiceConfig
        from app.aivis_speech_adapter import voice_config_to_dict

        vc = VoiceConfig(
            speaker_id=1,
            speaker_uuid="u",
            speaker_name="名前",
            style_id=593129376,
            style_name="ノーマル",
            style_type="talk",
            speed_scale=0.96,
            pitch_scale=0.0,
            intonation_scale=1.0,
            volume_scale=1.0,
            pre_phoneme_length=0.1,
            post_phoneme_length=0.1,
            tempo_dynamics_scale=1.8,
        )
        d = voice_config_to_dict(vc)
        assert d["speaker_id"] == 1
        assert d["speaker_uuid"] == "u"
        assert d["speaker_name"] == "名前"
        assert d["style_id"] == 593129376
        assert d["speed_scale"] == 0.96
        assert d["tempo_dynamics_scale"] == 1.8
        assert d["output_sampling_rate"] == config.audio.synthesis.output_sampling_rate
        assert d["output_stereo"] == config.audio.synthesis.output_stereo
