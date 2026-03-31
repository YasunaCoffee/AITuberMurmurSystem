"""
AITuber コマンドライン（サブコマンド）。

使用例:
  poetry run aituber run
  poetry run aituber run --detach
  poetry run aituber run --character characters/hayate.yaml
  poetry run aituber stop
  poetry run aituber stop --force
  poetry run aituber status
  poetry run aituber shutdown
  poetry run aituber character info
  poetry run aituber character validate characters/hayate.yaml
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """このリポジトリのルート（aituber/ の親）。"""
    return Path(__file__).resolve().parent.parent


def _ensure_project_root_on_path() -> None:
    """リポジトリルートを sys.path に入れる（main / murmur / config を import する前に必要）。"""
    r = str(_repo_root())
    if r not in sys.path:
        sys.path.insert(0, r)


def _cmd_run(args: argparse.Namespace) -> None:
    argv: list[str] = []
    if args.theme:
        argv.extend(["--theme", args.theme])
    if args.character:
        argv.extend(["--character", args.character])

    if args.detach:
        repo = _repo_root()
        log_path = repo / (args.log_file or "monologue.log")
        cmd = [sys.executable, "-m", "aituber", "run"] + argv
        logf = open(log_path, "ab")
        popen_kw: dict = {
            "args": cmd,
            "cwd": str(repo),
            "stdout": logf,
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kw["start_new_session"] = True
        subprocess.Popen(**popen_kw)
        print(f"バックグラウンドで起動しました。ログ: {log_path}")
        return

    from main import main as app_main

    app_main(argv=argv)


def _cmd_stop(args: argparse.Namespace) -> None:
    from aituber.ops import (
        find_app_processes,
        kill_process,
        signal_interrupt,
        write_shutdown_request_file,
        describe_process,
    )

    repo = _repo_root()
    procs = find_app_processes()
    if not procs:
        print("実行中の AITuber 本体プロセスは見つかりませんでした。")
        return

    path = write_shutdown_request_file(repo)
    print(f"終了リクエストを書き込みました: {path}")
    for p in procs:
        print(f"  {describe_process(p)}")

    if args.force:
        pids = [p.pid for p in procs]
        for pid in pids:
            kill_process(pid)
        print("強制終了（kill）を実行しました。")
        return

    n = 0
    for p in procs:
        if signal_interrupt(p.pid):
            n += 1
    if sys.platform != "win32" and n:
        print(f"SIGINT を {n} 件送信しました（終了処理はアプリ側に委ねます）。")
    elif sys.platform == "win32":
        print("Windows では終了ファイルとアプリのポーリングに依存します（従来の stop_monologue.ps1 と同様）。")


def _cmd_shutdown(_args: argparse.Namespace) -> None:
    """互換用: stop と同じ（強制なし）。"""
    _cmd_stop(argparse.Namespace(force=False))


def _cmd_status(_args: argparse.Namespace) -> None:
    from aituber.ops import find_app_processes, describe_process

    repo = _repo_root()
    procs = find_app_processes()
    if not procs:
        print("ステータス: 停止中（本体プロセスなし）")
    else:
        print(f"ステータス: 実行中（{len(procs)} プロセス）")
        for p in procs:
            print(f"  {describe_process(p)}")

    log_path = repo / "monologue.log"
    print("")
    if log_path.is_file():
        size = log_path.stat().st_size
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            n = len(lines)
        except OSError:
            n = -1
            lines = []
        print(f"ログ: {log_path}（約 {size} bytes, {n if n >= 0 else '?'} 行）")
        if lines:
            print("--- 末尾 5 行 ---")
            for line in lines[-5:]:
                print(line)
    else:
        print(f"ログ: {log_path} はまだありません")


def _cmd_character_info(args: argparse.Namespace) -> None:
    from murmur.runtime.character_runtime import (
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
    from murmur.models.character import load_character

    path = args.path
    if not os.path.isabs(path):
        path = os.path.normpath(str(_repo_root() / path))
    c = load_character(path)
    print(f"OK: {c.name} ({path})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aituber",
        description="AITuber ぶつぶつシステムの CLI",
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
    p_run.add_argument(
        "--detach",
        action="store_true",
        help="バックグラウンド起動（ログは --log-file、既定 monologue.log）",
    )
    p_run.add_argument(
        "--log-file",
        type=str,
        default="monologue.log",
        metavar="PATH",
        help="--detach 時のログ相対パス（プロジェクトルート基準）",
    )
    p_run.set_defaults(func=_cmd_run)

    p_stop = sub.add_parser(
        "stop",
        help="終了: shutdown_request.txt を作成し、可能なら SIGINT。--force で強制 kill",
    )
    p_stop.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="本体プロセスを強制終了（kill）",
    )
    p_stop.set_defaults(func=_cmd_stop)

    p_sd = sub.add_parser(
        "shutdown",
        help="(互換) stop と同じ（終了ファイルのみ・強制なし）",
    )
    p_sd.set_defaults(func=_cmd_shutdown)

    p_st = sub.add_parser("status", help="本体プロセスと monologue.log の要約")
    p_st.set_defaults(func=_cmd_status)

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
