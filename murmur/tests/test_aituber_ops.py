"""aituber.ops の単体テスト"""
import sys

from aituber.ops import is_app_process


def test_is_app_process_main_py():
    assert is_app_process(["python", "main.py"])
    assert is_app_process(["poetry", "run", "python", "main.py", "--theme", "x"])


def test_is_app_process_module_run():
    assert is_app_process([sys.executable, "-m", "aituber", "run"])
    assert is_app_process(["/usr/bin/python3", "-m", "aituber", "run", "--character", "c.yaml"])


def test_is_app_process_not_cli_validate():
    assert not is_app_process(["python", "-m", "aituber", "character", "validate", "x.yaml"])


def test_is_app_process_empty():
    assert not is_app_process([])
    assert not is_app_process(None)
