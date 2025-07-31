import unittest
import uuid
from unittest.mock import MagicMock, call

from v2.controllers.main_controller import MainController
from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted, InitialGreetingReady, SpeechPlaybackCompleted, NewCommentReceived,
    CommentResponseReady, PlaySpeech, PrepareInitialGreeting, PrepareCommentResponse
)
from v2.state.state_manager import StateManager, SystemState

class TestGreetingFlowIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_event_queue = MagicMock(spec=EventQueue)
        self.mock_state_manager = MagicMock(spec=StateManager)
        self.mock_audio_manager = MagicMock()
        self.mock_mode_manager = MagicMock()
        
        # StateManagerのモックに、実際の属性を持たせる
        self.mock_state_manager.current_state = SystemState.IDLE
        self.mock_state_manager.current_task_id = None
        self.mock_state_manager.current_task_type = None

        self.controller = MainController(
            event_queue=self.mock_event_queue,
            state_manager=self.mock_state_manager,
            audio_manager=self.mock_audio_manager,
            mode_manager=self.mock_mode_manager,
        )
        # 実際のメソッドを呼び出したいので、 setUpではモック化しない

    def test_full_greeting_to_theme_reading_flow(self):
        """
        挨拶 -> コメントx2 -> 朗読 の完全なフローをテストし、無限ループしないことを保証する
        """
        # --- ステップ1: 挨拶フロー ---
        greeting_task_id = "greeting_task_001"
        self.controller.handle_initial_greeting_ready(InitialGreetingReady(task_id=greeting_task_id, sentences=["Hello"]))
        
        # --- ステップ2: 1回目のコメント処理 ---
        # 挨拶の再生が完了
        self.mock_state_manager.current_task_id = greeting_task_id
        self.mock_state_manager.current_task_type = "initial_greeting"
        
        # 保留中のコメントがあるように見せかける
        self.mock_state_manager.has_pending_comments.return_value = True
        self.mock_state_manager.get_pending_comments.return_value = [{'username': 'user1', 'message': 'comment1'}]
        
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=greeting_task_id))
        
        # 1回目のコメント応答準備完了
        first_comment_task_id = "comment_task_001"
        self.controller.handle_comment_response_ready(CommentResponseReady(task_id=first_comment_task_id, sentences=["Response 1"], original_comments=[]))

        # --- ステップ3: 2回目のコメント処理 ---
        # 1回目のコメント応答の再生が完了
        self.mock_state_manager.current_task_id = first_comment_task_id
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=first_comment_task_id))

        # 2回目のコメント応答準備完了
        second_comment_task_id = "comment_task_002"
        self.controller.handle_comment_response_ready(CommentResponseReady(task_id=second_comment_task_id, sentences=["Response 2"], original_comments=[]))

        # --- ステップ4: 朗読フェーズへの移行 ---
        # 2回目のコメント応答の再生が完了
        self.mock_state_manager.current_task_id = second_comment_task_id
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        
        # _start_theme_reading が呼ばれることを確認するためにモック化
        self.controller._start_theme_reading = MagicMock()
        
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=second_comment_task_id))

        # --- 検証 ---
        # 最終的に _start_theme_reading が呼ばれることを確認
        self.controller._start_theme_reading.assert_called_once()
        
        # 3回目のコメント処理が始まっていないことを確認
        # set_stateの呼び出し履歴を分析
        set_state_calls = self.mock_state_manager.set_state.call_args_list
        comment_response_tasks = [
            c for c in set_state_calls 
            if c.args[2] in ("post_greeting_comment_response", "comment_response")
        ]
        
        self.assertEqual(len(comment_response_tasks), 2, "コメント応答タスクは2回だけのはず")

if __name__ == '__main__':
    unittest.main() 