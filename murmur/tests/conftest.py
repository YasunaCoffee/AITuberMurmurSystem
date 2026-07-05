"""pytest 共通: キャラクターYAMLを先に読み込む（get_character 利用箇所向け）。"""
import os

import pytest

# テスト実行が発話品質ログ(logs/speech_quality/)を汚さないように無効化
os.environ.setdefault("DISABLE_SPEECH_LOG", "1")


@pytest.fixture(scope="session", autouse=True)
def _load_default_character():
    from murmur.runtime.character_runtime import init_character
    init_character()
