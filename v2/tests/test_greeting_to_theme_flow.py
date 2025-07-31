"""
挨拶後のテーマ読み上げフローをテストする
"""
import unittest
import threading
import time
from unittest.mock import Mock, patch
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted, InitialGreetingRequested, InitialGreetingReady, 
    PlaySpeech, SpeechPlaybackCompleted
)
from v2.controllers.main_controller import MainController
from v2.handlers.mode_manager import ModeManager
from v2.state.state_manager import StateManager, SystemState

class TestGreetingToThemeFlow(unittest.TestCase):
    """挨拶からテーマ読み上げへの流れをテストする"""
    
    def setUp(self):
        """テスト環境をセットアップ"""
        self.event_queue = EventQueue()
        self.state_manager = StateManager()
        self.mode_manager = ModeManager()
        self.audio_manager = Mock()
        
        # MainControllerを初期化（正しいパラメータで）
        self.controller = MainController(
            event_queue=self.event_queue,
            state_manager=self.state_manager,
            mode_manager=self.mode_manager,
            audio_manager=self.audio_manager
        )
        
    def test_mode_manager_theme_loading(self):
        """ModeManagerのテーマ読み込み機能をテストする"""
        print("\n=== ModeManagerテーマ読み込みテスト ===")
        
        # テーマが正しく読み込まれることを確認
        theme_loaded = self.mode_manager.ensure_theme_loaded()
        print(f"[TEST] Theme loaded result: {theme_loaded}")
        
        # テーマ内容を取得
        theme_content = self.mode_manager.get_theme_content()
        print(f"[TEST] Theme content: {theme_content[:100] if theme_content else 'None'}...")
        
        # テーマファイルパスを確認
        theme_path = self.mode_manager.get_current_theme_file_path()
        print(f"[TEST] Theme file path: {theme_path}")
        
        # ファイルの存在を確認
        import os
        file_exists = os.path.exists(theme_path)
        print(f"[TEST] Theme file exists: {file_exists}")
        
        if not file_exists:
            print(f"[TEST] Looking for files in prompts directory...")
            prompts_dir = "prompts"
            if os.path.exists(prompts_dir):
                files = os.listdir(prompts_dir)
                print(f"[TEST] Files in prompts/: {files}")
            else:
                print(f"[TEST] prompts directory does not exist")
        
        return theme_loaded, theme_content
    
    def test_speech_completion_handler(self):
        """SpeechPlaybackCompleted処理をテストする"""
        print("\n=== SpeechPlaybackCompleted処理テスト ===")
        
        # 初期挨拶タスクを設定
        self.state_manager.set_state(SystemState.SPEAKING, "test_greeting_task", "initial_greeting")
        
        # SpeechPlaybackCompletedイベントを作成
        speech_completed = SpeechPlaybackCompleted(task_id="test_greeting_task")
        
        print(f"[TEST] Current state before: {self.state_manager.current_state}")
        print(f"[TEST] Current task type: {self.state_manager.current_task_type}")
        
        # イベントを処理
        try:
            self.controller.handle_speech_playback_completed(speech_completed)
            print("[TEST] ✅ SpeechPlaybackCompleted handled successfully")
        except Exception as e:
            print(f"[TEST] ❌ Error handling SpeechPlaybackCompleted: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[TEST] Current state after: {self.state_manager.current_state}")
        
        # イベントキューに何が追加されたかチェック
        events_in_queue = []
        try:
            while True:
                event = self.event_queue.get(timeout=0.1)
                events_in_queue.append(event)
                print(f"[TEST] Event in queue: {type(event).__name__}")
        except:
            pass
        
        print(f"[TEST] Total events generated: {len(events_in_queue)}")
        
        # テーマ読み上げ用のPlaySpeechイベントが生成されたかチェック
        play_speech_events = [e for e in events_in_queue if isinstance(e, PlaySpeech)]
        if play_speech_events:
            print(f"[TEST] ✅ PlaySpeech event found for theme reading")
            for event in play_speech_events:
                print(f"[TEST] PlaySpeech task_id: {event.task_id}, sentences: {len(event.sentences)}")
        else:
            print(f"[TEST] ❌ No PlaySpeech event found for theme reading")

if __name__ == '__main__':
    unittest.main() 