"""
AITuber コマンドライン（サブコマンド）。

使用例:
  poetry run aituber run
  poetry run aituber run --character characters/hayate.yaml
  poetry run aituber shutdown
  poetry run aituber character info
  poetry run aituber character validate characters/hayate.yaml
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    """このリポジトリのルート（aituber/ の親）。"""
    return Path(__file__).resolve().parent.parent


def _ensure_project_root_on_path() -> None:
    """リポジトリルートを sys.path に入れる（main / v2 / config を import する前に必要）。"""
    r = str(_repo_root())
    if r not in sys.path:
        sys.path.insert(0, r)


def _cmd_run(args: argparse.Namespace) -> None:
    argv: list[str] = []
    if args.theme:
        argv.extend(["--theme", args.theme])
    if args.character:
        argv.extend(["--character", args.character])
    from main import main as app_main

    app_main(argv=argv)


def _cmd_shutdown(_args: argparse.Namespace) -> None:
    path = str(_repo_root() / "shutdown_request.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("shutdown requested by aituber CLI\n")
    print(f"終了リクエストを書き込みました: {path}")


def _cmd_character_info(args: argparse.Namespace) -> None:
    from v2.runtime.character_runtime import (
        get_character,
        get_loaded_character_yaml_path,
        init_character,
        reset_character_runtime,
    )

    reset_character_runtime()
    init_character(args.yaml)
    c = get_character()
    yp = get_loaded_character_yaml_path()
    print(f"YAML: {yp}")
    print(f"name: {c.name}")
    print(f"description: {c.identity.description}")
    print(f"hashtag: {c.identity.hashtag}")
    print(f"speaker_id: {c.voice.speaker_id}")
    print(f"speaker_name: {c.voice.speaker_name}")
    if c.identity.display_aliases:
        print(f"display_aliases: {', '.join(c.identity.display_aliases)}")


def _cmd_character_validate(args: argparse.Namespace) -> None:
    from v2.models.character import load_character

    path = args.path
    if not os.path.isabs(path):
        path = os.path.normpath(str(_repo_root() / path))
    c = load_character(path)
    print(f"OK: {c.name} ({path})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aituber",
        description="AITuber ぶつぶつシステム v2 の CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="アプリを起動（従来の python main.py と同等）")
    p_run.add_argument("--theme", type=str, help="テーマファイル (例: prompts/my_theme.txt)")
    p_run.add_argument(
        "--character",
        type=str,
        metavar="YAML",
        help="キャラクター定義 YAML（省略時は config.yaml の character.yaml_path）",
    )
    p_run.set_defaults(func=_cmd_run)

    p_sd = sub.add_parser(
        "shutdown",
        help="グレースフル終了のリクエスト（shutdown_request.txt をプロジェクトルートに作成）",
    )
    p_sd.set_defaults(func=_cmd_shutdown)

    p_char = sub.add_parser("character", help="キャラクター定義の確認・検証")
    char_sub = p_char.add_subparsers(dest="char_cmd", required=True)

    p_ci = char_sub.add_parser("info", help="読み込んだキャラの要約を表示")
    p_ci.add_argument(
        "--yaml",
        type=str,
        default=None,
        metavar="YAML",
        help="YAML パス（省略時は config の character.yaml_path）",
    )
    p_ci.set_defaults(func=_cmd_character_info)

    p_cv = char_sub.add_parser("validate", help="YAML が load_character できるか検証")
    p_cv.add_argument(
        "path",
        type=str,
        help="プロジェクトルートからの相対パス（例: characters/hayate.yaml）",
    )
    p_cv.set_defaults(func=_cmd_character_validate)

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI エントリ（poetry script `aituber` からも呼ばれる）。"""
    _ensure_project_root_on_path()
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
