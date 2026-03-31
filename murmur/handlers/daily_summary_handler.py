import threading
import os
import schedule
import time
from datetime import datetime
from typing import Optional

from murmur.core.event_queue import EventQueue
from murmur.core.events import DailySummaryReady, PrepareDailySummary, StreamEnded
from app.memory_manager import MemoryManager
from config import config


class DailySummaryHandler:
    """日次要約の生成と保存を担当するハンドラー（配信終了後に自動実行）。"""

    def __init__(
        self,
        event_queue: EventQueue,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.event_queue = event_queue
        self.memory_manager = memory_manager
        self.summary_dir = (
            config.paths.summary
            if hasattr(config.paths, "summary")
            else "summary"
        )
        self.scheduler_thread = None
        self.running = False
        
        # 配信終了後の要約生成フラグ
        self.post_stream_summary_enabled = True
        self.last_summary_date = None

        # スケジューラーを初期化（毎日23:55にバックアップ実行）
        schedule.clear()
        schedule.every().day.at("23:55").do(self._schedule_backup_summary)

        print(
            "[DailySummaryHandler] Initialized with summary directory: "
            f"{self.summary_dir}"
        )
        print("[DailySummaryHandler] Post-stream summary generation: ENABLED")
        print("[DailySummaryHandler] Backup summary schedule: 23:55 daily")

    def start_scheduler(self):
        """日次要約のスケジューラーを開始する"""
        if self.running:
            print("[DailySummaryHandler] Scheduler is already running")
            return

        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler, daemon=True
        )
        self.scheduler_thread.start()
        print(
            "[DailySummaryHandler] Daily summary scheduler started (23:55 daily)"
        )

    def stop_scheduler(self):
        """日次要約のスケジューラーを停止する"""
        self.running = False
        schedule.clear()
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
        print("[DailySummaryHandler] Daily summary scheduler stopped")

    def _run_scheduler(self):
        """スケジューラーのメインループ"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにチェック
            except Exception as e:
                print(f"[DailySummaryHandler] Scheduler error: {e}")
                time.sleep(60)

    def _schedule_backup_summary(self):
        """スケジュールされたバックアップ日次要約の実行"""
        print("[DailySummaryHandler] Backup daily summary triggered (23:55)")
        
        # 今日既にサマリーが生成されているかチェック
        if self.is_today_summary_exists():
            print("[DailySummaryHandler] Today's summary already exists, skipping backup")
            return
            
        print("[DailySummaryHandler] No summary found for today, generating backup summary")
        self.trigger_daily_summary(reason="backup_schedule")

    def trigger_daily_summary(self, reason: str = "manual"):
        """日次要約を手動でトリガーする"""
        
        # 重複実行防止：今日既にサマリーが存在し、理由がpost_streamでない場合はスキップ
        today_date = datetime.now().strftime('%Y%m%d')
        if reason != "post_stream" and self.is_today_summary_exists():
            print(f"[DailySummaryHandler] Summary for {today_date} already exists, skipping ({reason})")
            return
            
        task_id = f"daily_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{reason}"
        command = PrepareDailySummary(task_id=task_id)
        self.event_queue.put(command)
        
        print(f"[DailySummaryHandler] Daily summary triggered ({reason}) with task_id: {task_id}")
        self.last_summary_date = today_date

    def handle_stream_ended(self, event: StreamEnded):
        """配信終了イベントを受信した時の処理"""
        if not self.post_stream_summary_enabled:
            print("[DailySummaryHandler] Post-stream summary is disabled")
            return
            
        print(f"[DailySummaryHandler] 📺 Stream ended ({event.ending_reason}) after {event.stream_duration_minutes} minutes")
        print("[DailySummaryHandler] 🎯 Triggering post-stream daily summary...")
        
        # 配信終了後のサマリー生成
        self.trigger_daily_summary(reason="post_stream")

    def handle_prepare_daily_summary(self, command: PrepareDailySummary):
        """
        PrepareDailySummaryコマンドを処理する。
        バックグラウンドで日次要約を生成し、完了時にイベントを発行する。
        """
        print(f"[DailySummaryHandler] Received command: {command}")

        # バックグラウンドスレッドで重い処理を実行
        thread = threading.Thread(
            target=self._execute_in_background, args=(command,)
        )
        thread.start()

    def _execute_in_background(self, command: PrepareDailySummary):
        """バックグラウンドで日次要約を実行し、結果をイベントキューに入れる"""
        print(
            "[DailySummaryHandler] Processing daily summary for task: "
            f"{command.task_id}"
        )

        try:
            if not self.memory_manager:
                print(
                    "[DailySummaryHandler] Warning: MemoryManager not available"
                )
                summary_text = (
                    f"日次要約 - {datetime.now().strftime('%Y年%m月%d日')}\n\n"
                    "MemoryManagerが利用できないため、"
                    "詳細な要約を生成できませんでした。"
                )
                event = DailySummaryReady(
                    task_id=command.task_id,
                    summary_text=summary_text,
                    success=False,
                    file_path=None
                )
                self.event_queue.put(event)

            else:
                # MemoryManagerに日次要約の生成を依頼
                # MemoryManagerが完了後にDailySummaryReadyイベントを発行する
                print(
                    "[DailySummaryHandler] "
                    "Requesting daily summary from MemoryManager"
                )
                self.memory_manager.save_daily_summary(
                    self.summary_dir, command.task_id
                )

        except Exception as e:
            print(
                "[DailySummaryHandler] Error during daily summary trigger: "
                f"{e}"
            )
            summary_text = f"日次要約のトリガー中にエラーが発生しました: {str(e)}"
            event = DailySummaryReady(
                task_id=command.task_id,
                summary_text=summary_text,
                success=False,
                file_path=None
            )
            self.event_queue.put(event)

    def get_today_summary_path(self) -> str:
        """今日の要約ファイルのパスを取得"""
        today = datetime.now().strftime('%Y%m%d')
        return os.path.join(self.summary_dir, f"summary_{today}.txt")

    def is_today_summary_exists(self) -> bool:
        """今日の要約ファイルが既に存在するかチェック"""
        return os.path.exists(self.get_today_summary_path())
    
    def enable_post_stream_summary(self, enabled: bool = True):
        """配信終了後サマリー生成の有効/無効を設定"""
        self.post_stream_summary_enabled = enabled
        status = "ENABLED" if enabled else "DISABLED"
        print(f"[DailySummaryHandler] Post-stream summary generation: {status}")
    
    def get_summary_status(self) -> dict:
        """サマリー生成の状態を取得"""
        return {
            "post_stream_enabled": self.post_stream_summary_enabled,
            "today_summary_exists": self.is_today_summary_exists(),
            "last_summary_date": self.last_summary_date,
            "summary_directory": self.summary_dir
        }