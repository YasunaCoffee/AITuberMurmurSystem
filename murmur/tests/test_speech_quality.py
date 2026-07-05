# -*- coding: utf-8 -*-
"""murmur.quality.speech_quality のユニットテスト（LLM 不要の純粋関数のみ）。"""
import pytest

from murmur.quality.speech_quality import (
    check_speech,
    sanitize_for_speech,
    similarity,
)


GOOD = (
    "んー、記憶っていうのは面白いですね。自分の中では、思い出すたびに"
    "少しずつ書き換わるデータ構造みたいなものだと捉えています。"
    "皆さんはどう思いますか？"
)


class TestSanitize:
    def test_markdown_and_whitespace(self):
        raw = "**記憶**について。\n\n- まず一つ目。\n`code` はそのまま。"
        out = sanitize_for_speech(raw)
        assert "**" not in out
        assert "\n" not in out
        assert "- " not in out.split("。")[1]

    def test_url_removed(self):
        out = sanitize_for_speech("詳しくは https://example.com/x を見てください。")
        assert "http" not in out

    def test_empty(self):
        assert sanitize_for_speech(None) == ""
        assert sanitize_for_speech("") == ""


class TestCheckSpeech:
    def test_good_response_passes(self):
        report = check_speech(GOOD)
        assert report.ok
        assert report.warnings == []

    def test_empty_is_fatal(self):
        assert not check_speech("").ok

    def test_too_short_is_fatal(self):
        assert not check_speech("そうですね。").ok

    def test_first_person_watashi_is_fatal(self):
        report = check_speech("私はそう思います。記憶は不思議なものですからね、皆さん。")
        assert any(f == "first_person" for f in report.fatal)

    def test_jibun_and_boku_are_ok(self):
        report = check_speech(GOOD + "僕もそう感じます。")
        assert "first_person" not in report.fatal

    def test_assistant_tone_is_fatal(self):
        report = check_speech(
            "申し訳ありませんが、そのご質問にはお答えできません。別の話題にしましょうか、皆さん。"
        )
        assert any(f.startswith("assistant_tone") for f in report.fatal)

    def test_prompt_echo_is_fatal(self):
        report = check_speech(
            "独り言モード[C]ですね。今日は情報理論について考えてみます。皆さんはどうですか。"
        )
        assert any(f.startswith("prompt_echo") for f in report.fatal)

    def test_non_japanese_is_fatal(self):
        report = check_speech("I am an information lifeform thinking about memory today.")
        assert "non_japanese" in report.fatal

    def test_too_long_is_warning_not_fatal(self):
        report = check_speech("記憶の話です。" + "あ" * 500)
        assert report.ok
        assert any(w.startswith("too_long") for w in report.warnings)

    def test_sentence_repeat_warning(self):
        s = "記憶は書き換わるものなんですよね。記憶は書き換わるものなんですよね。面白いです。"
        report = check_speech(s)
        assert "sentence_repeat" in report.warnings

    def test_similar_to_recent_warning(self):
        report = check_speech(GOOD, recent=[GOOD])
        assert any(w.startswith("similar_to_recent") for w in report.warnings)

    def test_unbalanced_quotes_warning(self):
        report = check_speech("皆さんが「記憶とは何か、と聞いてくれたので考えてみます。面白い問いですね。")
        assert "unbalanced_quotes" in report.warnings


class TestSimilarity:
    def test_identical(self):
        assert similarity(GOOD, GOOD) == pytest.approx(1.0)

    def test_disjoint(self):
        assert similarity("あいうえおかきくけこ", "らりるれろわをんまみ") == 0.0

    def test_short_strings(self):
        assert similarity("あ", "あ") == 0.0
