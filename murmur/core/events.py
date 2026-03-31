from dataclasses import dataclass, field
from typing import List, Any, Optional, Callable, Dict
import queue


# --- Base Classes ---

@dataclass(frozen=True)
class Event:
    """システムのどこかで何かが発生したことを示すベースイベントクラス。"""
    pass


@dataclass(frozen=True)
class Command:
    """システムに何かを実行するよう指示するベースコマンドクラス。"""
    task_id: str


# --- System & Lifecycle Events ---

@dataclass(frozen=True)
class AppStarted(Event):
    """アプリケーションが起動したことを示すイベント。"""
    pass


@dataclass(frozen=True)
class AppClosing(Event):
    """アプリケーションが終了処理を開始したことを示すイベント。"""
    pass


@dataclass(frozen=True)
class StreamEnded(Event):
    """配信が終了したことを示すイベント（サマリー生成のトリガー）。"""
    stream_duration_minutes: int = 0
    ending_reason: str = "normal"  # "normal", "timeout", "manual", "error"


@dataclass(frozen=True)
class MonologueFromThemeRequested(Event):
    """特定のテーマファイルからモノローグを開始するリクエスト"""
    theme_file: str


@dataclass(frozen=True)
class InitialGreetingRequested(Event):
    """起動時の挨拶を要求するイベント。"""
    pass


@dataclass(frozen=True)
class EndingGreetingRequested(Event):
    """終了時の挨拶が要求されたことを示すイベント。"""
    bridge_text: str = ""
    stream_summary: str = ""


# --- Service Events (External Inputs) ---

@dataclass(frozen=True)
class SpeechPlaybackCompleted(Event):
    """音声の再生が完了したことを示すイベント。"""
    task_id: str


@dataclass(frozen=True)
class NewCommentReceived(Event):
    """新しいコメントを受信したことを示すイベント。"""
    comments: List[Any]  # YouTubeのコメントオブジェクトなどを想定


@dataclass(frozen=True)
class ServiceErrorOccurred(Event):
    """外部サービスでエラーが発生したことを示すイベント。"""
    source: str  # e.g., "AudioManager", "OpenAI"
    error: Exception


# --- Handler Events (Internal Results) ---

@dataclass(frozen=True)
class MonologueReady(Event):
    """独り言の文章生成が完了したことを示すイベント。"""
    task_id: str
    sentences: List[str]


@dataclass(frozen=True)
class CommentResponseReady(Event):
    """コメントへの応答文の準備が完了したことを示すイベント。"""
    task_id: str
    sentences: List[str]
    original_comments: List[Dict[str, Any]]


@dataclass(frozen=True)
class InitialGreetingReady(Event):
    """開始時の挨拶生成が完了したことを示すイベント。"""
    task_id: str
    sentences: List[str]


@dataclass(frozen=True)
class EndingGreetingReady(Event):
    """終了時の挨拶生成が完了したことを示すイベント。"""
    task_id: str
    sentences: List[str]


@dataclass(frozen=True)
class DailySummaryReady(Event):
    """日次要約の準備が完了したことを示すイベント"""
    task_id: str
    summary_text: str
    success: bool
    file_path: Optional[str] = None


# --- Commands ---

@dataclass(frozen=True)
class PrepareMonologue(Command):
    """独り言の準備を要求するコマンド。"""
    task_id: str
    theme_file: Optional[str] = None
    theme_content: Optional[str] = None # テーマの内容を直接渡す


@dataclass(frozen=True)
class PrepareCommentResponse(Command):
    """コメントへの返答生成を指示するコマンド。"""
    task_id: str
    comments: List[Any]


@dataclass(frozen=True)
class PrepareInitialGreeting(Command):
    """開始時の挨拶を準備するコマンド。"""
    task_id: str


@dataclass(frozen=True)
class PrepareEndingGreeting(Command):
    """終了時の挨拶を準備するコマンド。"""
    task_id: str
    bridge_text: str = ""
    stream_summary: str = ""


@dataclass(frozen=True)
class PrepareDailySummary(Command):
    """日次要約の生成を指示するコマンド。"""
    task_id: str


@dataclass(frozen=True)
class PlaySpeech(Command):
    """生成された文章の音声再生を指示するコマンド。"""
    task_id: str
    sentences: List[str]
    sync_queue: Optional[queue.Queue] = None


@dataclass(frozen=True)
class FetchComments(Command):
    """コメントの取得を指示するコマンド。"""
    pass


@dataclass(frozen=True)
class Shutdown(Command):
    """システム全体のシャットダウンを指示するコマンド。"""
    pass 