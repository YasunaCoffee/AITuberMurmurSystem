"""pytest 共通: キャラクターYAMLを先に読み込む（get_character 利用箇所向け）。"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def _load_default_character():
    from v2.runtime.character_runtime import init_character
    init_character()
