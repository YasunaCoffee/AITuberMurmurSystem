"""
AITuber 本体プロセスの検出・終了（start/stop/status スクリプト相当）。

対象: コマンドラインに main.py を含むもの、または `python -m aituber run`。
"""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import List

import psutil


def _cmdline_str(cmdline: List[str] | None) -> str:
    if not cmdline:
        return ""
    return " ".join(cmdline)


def is_app_process(cmdline: List[str] | None) -> bool:
    """起動中の AITuber 本体（main / aituber run）かどうか。"""
    if not cmdline:
        return False
    parts = cmdline
    joined = _cmdline_str(parts)
    if "main.py" in joined:
        return True
    if "-m" in parts:
        try:
            i = parts.index("-m")
            if i + 2 < len(parts) and parts[i + 1] == "aituber" and parts[i + 2] == "run":
                return True
        except (ValueError, IndexError):
            pass
    return False


def find_app_processes():
    """本体プロセスの psutil.Process 一覧（現在の CLI プロセスは除外）。"""
    me = os.getpid()
    out = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == me:
                continue
            cmd = proc.info.get("cmdline")
            if cmd and is_app_process(list(cmd)):
                out.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return out


def find_app_pids() -> List[int]:
    return [p.pid for p in find_app_processes()]


def write_shutdown_request_file(repo_root: Path) -> Path:
    path = repo_root / "shutdown_request.txt"
    path.write_text("shutdown requested by aituber CLI\n", encoding="utf-8")
    return path


def signal_interrupt(pid: int) -> bool:
    """Unix: SIGINT。Windows: 未対応（False を返す）。"""
    if sys.platform == "win32":
        return False
    try:
        os.kill(pid, signal.SIGINT)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def kill_process(pid: int) -> bool:
    try:
        p = psutil.Process(pid)
        p.kill()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def describe_process(proc: psutil.Process) -> str:
    try:
        cmd = _cmdline_str(proc.cmdline())
        return f"PID {proc.pid}: {cmd[:200]}{'...' if len(cmd) > 200 else ''}"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return f"PID {proc.pid}: (参照不可)"
