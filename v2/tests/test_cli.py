"""CLI (aituber) のスモークテスト"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_cli_help_exits_zero():
    r = subprocess.run(
        [sys.executable, "-m", "aituber", "-h"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    assert "aituber" in out or "usage" in out.lower()


def test_cli_status_and_stop_help():
    for sub in ("status", "stop", "shutdown"):
        r = subprocess.run(
            [sys.executable, "-m", "aituber", sub, "-h"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, (sub, r.stderr)


def test_cli_character_validate_hayate():
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "aituber",
            "character",
            "validate",
            "characters/hayate.yaml",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK:" in r.stdout
    assert "蒼月ハヤテ" in r.stdout


def test_cli_character_info_smoke():
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "aituber",
            "character",
            "info",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "name:" in r.stdout
    assert "YAML:" in r.stdout


def test_legacy_cli_py_delegates():
    r = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "cli.py"), "character", "validate", "characters/hayate.yaml"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK:" in r.stdout
