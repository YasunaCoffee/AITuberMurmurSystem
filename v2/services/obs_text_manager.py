import os
import time
import threading
from v2.core.event_queue import EventQueue
from v2.core.events import PlaySpeech, SpeechPlaybackCompleted
from v2.obs_adaper import OBSAdapter

class OBSTextManager:
    """
    OBSのテキストソースに字幕を表示するサービス。
    音声出力と連動して字幕の表示/非表示を制御する。
    """
    def __init__(self, event_queue: EventQueue, audio_manager=None):
        self.event_queue = event_queue
        self.audio_manager = audio_manager
        
        # 設定を読み込み
        self._load_subtitle_config()
        
        # OBS Adapterの初期化
        try:
            self.obs = OBSAdapter()
            if self.obs.test_connection():
                print("[OBSTextManager] Successfully connected to OBS")
            else:
                print("[OBSTextManager] Failed to connect to OBS")
                self.obs = None
        except Exception as e:
            print(f"[OBSTextManager] Failed to initialize OBS Adapter: {e}")
            self.obs = None

        # 現在表示中のタスクID
        self.current_task_id = None

    def _load_subtitle_config(self):
        """設定ファイルから字幕設定を読み込む"""
        try:
            from config import config
            subtitle_config = config.obs_subtitles
            
            self.subtitles_enabled = subtitle_config.get('enabled', True)
            
            print(f"[OBSTextManager] Subtitle config loaded: enabled={self.subtitles_enabled}")
            
        except Exception as e:
            print(f"[OBSTextManager] Failed to load subtitle config: {e}")
            # デフォルト値を設定
            self.subtitles_enabled = True

    def _format_subtitle_text(self, text: str) -> str:
        """
        字幕用にテキストを整形する（改行なし）。
        """
        if not self.subtitles_enabled:
            return ""
            
        # 既存の改行文字を削除してスペースに置換
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        return text

    def _find_best_break_position(self, text: str) -> int:
        """
        (このメソッドは使用されなくなりました)
        """
        return 0

    def handle_play_speech(self, command: PlaySpeech, duration: float = None):
        """
        PlaySpeechコマンドを処理する。
        音声出力されるテキストをOBSに表示する。

        Args:
            command (PlaySpeech): 音声再生コマンド
            duration (float): 音声の再生時間（秒）
        """
        if not self.obs:
            print("[OBSTextManager] OBS not connected")
            return

        if not self.subtitles_enabled:
            print("[OBSTextManager] Subtitles disabled")
            return

        # 現在のタスクIDを更新
        self.current_task_id = command.task_id

        for sentence in command.sentences:
            try:
                # 字幕用にテキストを整形
                formatted_text = self._format_subtitle_text(sentence)
                
                if formatted_text:  # 空でない場合のみ表示
                    # 字幕を即座に表示
                    self.obs.set_answer(formatted_text)
                    
                    # ログ出力
                    print(f"[OBSTextManager] Displaying subtitle for task {self.current_task_id} ({duration:.2f}s): {formatted_text[:80]}...")
                
            except Exception as e:
                print(f"[OBSTextManager] Failed to display subtitle: {e}")

    def handle_speech_completed(self, event: SpeechPlaybackCompleted):
        """
        SpeechPlaybackCompletedイベントを処理する。
        字幕を非表示にする。
        """
        # タスクIDが一致する場合のみクリア
        if event.task_id == self.current_task_id:
            self._clear_subtitle()
            self.current_task_id = None

    def _clear_subtitle(self):
        """字幕をクリアする"""
        if not self.obs:
            return

        try:
            self.obs.set_answer("")
            print(f"[OBSTextManager] Cleared subtitle for task {self.current_task_id}")
        except Exception as e:
            print(f"[OBSTextManager] Failed to clear subtitle: {e}")

    def set_subtitle_config(self, enabled: bool = None):
        """
        字幕表示の設定を変更する。
        
        Args:
            enabled (bool): 字幕表示の有効/無効
        """
        if enabled is not None:
            self.subtitles_enabled = enabled
            
        print(f"[OBSTextManager] Subtitle config updated: enabled={self.subtitles_enabled}")

    def __del__(self):
        """デストラクタ：OBS接続を閉じる"""
        if hasattr(self, 'obs') and self.obs:
            try:
                self.obs.disconnect()
            except:
                pass 