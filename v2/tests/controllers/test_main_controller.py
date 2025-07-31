import unittest
from unittest.mock import MagicMock, ANY, call

# プロジェクトルートのパスを取得
# grandparent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# sys.path.insert(0, grandparent_dir)

from v2.controllers.main_controller import MainController
from v2.state.state_manager import StateManager
from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted, SpeechPlaybackCompleted,
    InitialGreetingRequested, PrepareMonologue, PrepareCommentResponse,
    MonologueFromThemeRequested, CommentResponseReady, PlaySpeech
)
from v2.state.state_manager import SystemState
import queue
from unittest.mock import ANY
from unittest.mock import patch
from v2.services.integrated_comment_manager import IntegratedCommentManager
from v2.handlers.monologue_handler import MonologueHandler
from v2.handlers.comment_handler import CommentHandler
from v2.handlers.mode_manager import ModeManager
from v2.core.events import (SpeechPlaybackCompleted, PrepareMonologue, 
                            NewCommentReceived, PrepareCommentResponse, 
                            CommentResponseReady, AppStarted, InitialGreetingReady)
from v2.services.audio_manager import AudioManager


class TestMainController(unittest.TestCase):

    def setUp(self):
        # 共通のモックオブジェクトを作成
        self.mock_event_queue = MagicMock(spec=EventQueue)
        self.mock_state_manager = MagicMock(spec=StateManager)
        self.mock_audio_manager = MagicMock(spec=AudioManager)
        self.mock_mode_manager = MagicMock(spec=ModeManager)
        
        # MainControllerのインスタンスを作成し、モックを注入
        self.controller = MainController(
            event_queue=self.mock_event_queue,
            state_manager=self.mock_state_manager,
            audio_manager=self.mock_audio_manager,
            mode_manager=self.mock_mode_manager
        )
        
        # テストのために、他のハンドラやマネージャを直接コントローラに設定
        self.mock_monologue_handler = MagicMock(spec=MonologueHandler)
        self.mock_comment_handler = MagicMock(spec=CommentHandler)
        self.mock_comment_manager = MagicMock(spec=IntegratedCommentManager)
        # prefetched_monologues をモックに置き換え
        self.controller.prefetched_monologues = MagicMock(spec=queue.Queue)

        self.controller.monologue_handler = self.mock_monologue_handler
        self.controller.comment_handler = self.mock_comment_handler
        self.controller.comment_manager = self.mock_comment_manager


        # エラー 'Mock object has no attribute 'current_state'' を解消するため、
        # モックに初期状態を設定する
        self.mock_state_manager.current_state = SystemState.IDLE
        

    def tearDown(self):
        # OBS接続を閉じるなど、クリーンアップ処理
        pass

    def test_app_started_triggers_initial_greeting(self):
        """
        AppStartedイベントがInitialGreetingRequestedイベントを発行することを確認
        """
        app_started_event = AppStarted()
        self.controller.process_item(app_started_event)

        # InitialGreetingRequestedがキューに追加されたかを確認
        self.mock_event_queue.put.assert_called_once()
        put_event = self.mock_event_queue.put.call_args[0][0]
        self.assertIsInstance(put_event, InitialGreetingRequested)

    def test_greeting_completion_with_comments_triggers_comment_response(self):
        """挨拶完了時にコメントがあれば、コメント応答が開始されることを確認"""
        # セットアップ
        task_id = "greeting_task"
        self.controller.state_manager.current_task_type = "initial_greeting"
        self.controller.state_manager.current_task_id = task_id
        self.controller.state_manager.has_pending_comments.return_value = True
        self.controller.state_manager.get_pending_comments.return_value = [{'message': 'test comment'}]
        speech_completed_event = SpeechPlaybackCompleted(task_id=task_id)

        # 実行
        self.controller.process_item(speech_completed_event)

        # 検証
        self.mock_event_queue.put.assert_called_once()
        self.assertIsInstance(self.mock_event_queue.put.call_args[0][0], PrepareCommentResponse)

    def test_greeting_completion_without_comments_triggers_reading(self):
        """挨拶完了時にコメントがなければ、朗読が開始されることを確認"""
        # セットアップ
        task_id = "greeting_task"
        self.mock_state_manager.current_task_type = "initial_greeting"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.has_pending_comments.return_value = False
        speech_completed_event = SpeechPlaybackCompleted(task_id=task_id)

        # このテストケース内でのみモック化
        self.controller._start_theme_reading = MagicMock()

        # 実行
        self.controller.handle_speech_playback_completed(speech_completed_event)

        # 検証
        self.controller._start_theme_reading.assert_called_once()

    def test_monologue_from_theme_requested_triggers_prepare_monologue(self):
        """MonologueFromThemeRequestedがPrepareMonologueコマンドを発行するのを確認"""
        # セットアップ
        self.mock_state_manager.current_task_type = "idle"
        theme_file_path = "prompts/test_theme.txt"
        themed_request_event = MonologueFromThemeRequested(theme_file=theme_file_path)

        # 実行
        self.controller.process_item(themed_request_event)

        # 検証
        self.mock_state_manager.set_state.assert_called_with(SystemState.THINKING, ANY, "monologue_from_theme")
        self.mock_event_queue.put.assert_called_once()
        
        # 発行されたコマンドを検証
        put_command = self.mock_event_queue.put.call_args[0][0]
        self.assertIsInstance(put_command, PrepareMonologue)
        self.assertEqual(put_command.theme_file, theme_file_path)

    def test_schedule_next_action_uses_theme_content_after_reading(self):
        """テーマ朗読完了後、次の独り言がテーマ内容を元に生成されることを確認"""
        # セットアップ
        self.controller.theme_reading_completed = True
        self.controller.prefetched_monologues.empty = MagicMock(return_value=True)
        
        # ModeManagerが返すテーマ内容をモック
        mock_theme_content = "これがテスト用のテーマです。"
        self.controller.mode_manager.get_theme_content.return_value = mock_theme_content

        # 実行
        self.controller._schedule_next_action()

        # 検証
        self.controller.event_queue.put.assert_called_once()
        put_command = self.controller.event_queue.put.call_args[0][0]
        
        self.assertIsInstance(put_command, PrepareMonologue)
        self.assertEqual(put_command.theme_content, mock_theme_content)
        self.assertIsNone(put_command.theme_file) # theme_contentが使われるべき

    def test_ignores_mismatched_task_id_on_speech_completion(self):
        """タスクIDが不一致のSpeechPlaybackCompletedイベントを無視することを確認"""
        # セットアップ
        current_task_id = "greeting_task_123"
        self.controller.state_manager.current_task_id = current_task_id
        self.controller.state_manager.current_task_type = "initial_greeting"

        # 不一致なIDを持つイベント
        mismatched_event = SpeechPlaybackCompleted(task_id="some_other_task_456")

        # このテストケース内でのみモック化
        self.controller._start_theme_reading = MagicMock()

        # 実行
        self.controller.handle_speech_playback_completed(mismatched_event)

        # 検証：後続処理が呼ばれていないことを確認
        self.mock_state_manager.finish_task.assert_not_called()
        self.controller._start_theme_reading.assert_not_called()

    def test_speech_completion_without_follow_up_triggers_monologue(self):
        """音声再生完了後、後続タスクがなければプリフェッチが開始されることを確認"""
        # セットアップ
        task_id = "comment_task_123"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.current_task_type = "comment_response"
        self.controller.prefetched_monologues.empty.return_value = True
        self.controller.theme_reading_completed = True
        
        # モックの設定
        self.controller._process_queued_comments = MagicMock(return_value=False) # コメントキューは空
        self.controller.start_prefetch_if_needed = MagicMock()

        # イベント作成と処理
        event = SpeechPlaybackCompleted(task_id=task_id)
        self.controller.handle_speech_playback_completed(event)

        # 検証
        self.controller._process_queued_comments.assert_called_once()
        self.controller.start_prefetch_if_needed.assert_called_once()
        self.mock_state_manager.finish_task.assert_called_once()

    def test_handle_comment_response_ready_preserves_task_type(self):
        """
        handle_comment_response_readyが、ステートマネージャに既に設定されている
        タスクタイプ（例: post_greeting_comment_response）を上書きしないことを確認する。
        """
        # 1. 挨拶後のコメント処理中という状態をセットアップ
        task_id = "test_task_123"
        original_task_type = "post_greeting_comment_response"
        self.mock_state_manager.current_state = SystemState.THINKING
        self.mock_state_manager.current_task_type = original_task_type # これが重要

        # 2. CommentResponseReadyイベントを作成して処理
        event = CommentResponseReady(task_id=task_id, sentences=["Response"], original_comments=[])
        self.controller.handle_comment_response_ready(event)

        # 3. 検証: set_stateが呼ばれる際に、元のタスクタイプが保持されていることを確認
        self.mock_state_manager.set_state.assert_called_once_with(
            SystemState.SPEAKING,
            task_id,
            original_task_type  # "comment_response" に上書きされていないはず
        )

    def test_limits_post_greeting_responses_to_two_then_starts_theme_reading(self):
        """挨拶後のコメント返信が2回に制限され、その後テーマ朗読が始まることを確認"""
        # 1. 挨拶完了直後の状態と、複数コメントが存在する状況をセットアップ
        greeting_task_id = "greeting_task_123"
        self.mock_state_manager.current_task_id = greeting_task_id
        self.mock_state_manager.current_task_type = "initial_greeting"

        # _process_queued_commentsが最初の2回はTrue（コメントあり）、3回目はFalseを返すように設定
        self.controller._process_queued_comments = MagicMock(side_effect=[True, True, False])
        self.controller._start_theme_reading = MagicMock() # テーマ朗読の呼び出しを監視

        # 2. 挨拶完了イベントを処理 -> 1回目のコメント処理が開始されるはず
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=greeting_task_id))

        # self.controller.post_greeting_response_count はまだ0のはず
        self.controller._start_theme_reading.assert_not_called()

        # 3. 1回目のコメント返信の再生が完了したと仮定
        first_comment_task_id = "comment_task_1"
        self.mock_state_manager.current_task_id = first_comment_task_id
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=first_comment_task_id))

        # -> 2回目のコメント処理が開始されるはず
        # self.controller.post_greeting_response_count は 1 のはず
        self.controller._start_theme_reading.assert_not_called()

        # 4. 2回目のコメント返信の再生が完了したと仮定
        second_comment_task_id = "comment_task_2"
        self.mock_state_manager.current_task_id = second_comment_task_id
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        self.controller.handle_speech_playback_completed(SpeechPlaybackCompleted(task_id=second_comment_task_id))

        # -> 2回の上限に達したので、今度こそテーマ朗読が開始されるはず
        # self.controller.post_greeting_response_count は 2 のはず
        self.controller._start_theme_reading.assert_called_once()

    def test_start_theme_reading_uses_consistent_task_id(self):
        """
        _start_theme_readingが呼ばれた際に、StateManagerとAudioManagerに
        渡されるタスクIDが一致することを確認
        """
        # セットアップ
        self.mock_mode_manager.get_theme_intro.return_value = ["This is the theme intro."]
        self.mock_mode_manager.ensure_theme_loaded.return_value = None

        # 実行: _start_theme_readingの実際のメソッドを呼び出す
        self.controller._start_theme_reading()

        # 検証
        self.mock_state_manager.set_state.assert_called_once()
        self.mock_audio_manager.handle_play_speech.assert_called_once()
        
        # 'set_state' と 'handle_play_speech' の呼び出し引数を取得
        state_call_args = self.mock_state_manager.set_state.call_args[0]
        audio_call_args = self.mock_audio_manager.handle_play_speech.call_args[0]
        
        # task_idが一致することを確認
        state_task_id = state_call_args[1]  # set_state(state, task_id, type)
        audio_task_id = audio_call_args[0].task_id # handle_play_speech(PlaySpeech(task_id=...))
        
        self.assertEqual(state_task_id, audio_task_id)
        # タスクIDが期待されるフォーマットであることも確認
        self.assertTrue(state_task_id.startswith("theme_intro_"))


    def test_greeting_comment_limit_flow(self):
        """
        挨拶 -> コメント1 -> コメント2 -> 朗読 の流れでコメントカウントが正しく機能するかをテスト
        """
        # --- 準備 ---
        self.controller._start_theme_reading = MagicMock()
        self.controller._process_queued_comments = MagicMock(return_value=True)

        # --- 1. 挨拶完了 → 最初のコメント処理を開始 ---
        initial_greeting_event = SpeechPlaybackCompleted(task_id="greeting_task")
        self.mock_state_manager.current_task_id = "greeting_task"
        self.mock_state_manager.current_task_type = "initial_greeting"

        self.controller.handle_speech_playback_completed(initial_greeting_event)

        # 検証1: 最初のコメント処理が開始され、朗読はまだ始まらない
        self.controller._process_queued_comments.assert_called_once_with(task_type="post_greeting_comment_response")
        self.controller._start_theme_reading.assert_not_called()
        self.assertEqual(self.controller.post_greeting_response_count, 0)

        # --- 2. 1回目のコメント返信完了 → 2回目のコメント処理を開始 ---
        first_comment_event = SpeechPlaybackCompleted(task_id="comment_task_1")
        self.mock_state_manager.current_task_id = "comment_task_1"
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        self.controller._process_queued_comments.reset_mock() # 呼び出し回数をリセット
        self.controller._process_queued_comments.return_value = True

        self.controller.handle_speech_playback_completed(first_comment_event)
        
        # 検証2: カウンタが1になり、2回目のコメント処理が開始され、朗読はまだ
        self.assertEqual(self.controller.post_greeting_response_count, 1)
        self.controller._process_queued_comments.assert_called_once_with(task_type="post_greeting_comment_response")
        self.controller._start_theme_reading.assert_not_called()

        # --- 3. 2回目のコメント返信完了 → 朗読を開始 ---
        second_comment_event = SpeechPlaybackCompleted(task_id="comment_task_2")
        self.mock_state_manager.current_task_id = "comment_task_2"
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        self.controller._process_queued_comments.reset_mock() # 呼び出し回数をリセット

        self.controller.handle_speech_playback_completed(second_comment_event)

        # 検証3: カウンタが2になり、朗読が開始され、それ以上のコメント処理は行われない
        self.assertEqual(self.controller.post_greeting_response_count, 2)
        self.controller._start_theme_reading.assert_called_once()
        self.controller._process_queued_comments.assert_not_called()


    def test_queued_comment_response_preserves_task_type(self):
        """並行処理でキューイングされたコメント応答が正しいタスクタイプを保持し、再生されることをテスト"""
        # 1. 発話中にコメント応答準備完了イベントを受信するシナリオ
        speaking_task_id = "speaking_task_1"
        self.mock_state_manager.current_state = SystemState.SPEAKING
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        
        ready_event = CommentResponseReady(
            task_id="queued_task_1", 
            sentences=["Queued response."], 
            original_comments=[{"username": "test", "message": "test"}]
        )
        self.controller.handle_comment_response_ready(ready_event)
        
        # 検証1: 応答がキューに追加され、タスクタイプが保持されていること
        self.assertEqual(len(self.controller.queued_comment_responses), 1)
        queued_item = self.controller.queued_comment_responses[0]
        self.assertEqual(queued_item['task_id'], "queued_task_1")
        self.assertEqual(queued_item['task_type'], "post_greeting_comment_response")

        # 2. 発話完了後、キューイングされた応答が再生されるシナリオ
        completion_event = SpeechPlaybackCompleted(task_id=speaking_task_id)
        # current_task_id を発話中のタスクに設定
        self.mock_state_manager.current_task_id = speaking_task_id
        
        self.controller.handle_speech_playback_completed(completion_event)
        
        # 検証2: キューから取り出され、正しいタスクタイプで再生が開始されること
        self.mock_state_manager.set_state.assert_called_with(
            SystemState.SPEAKING, 
            "queued_task_1", 
            "post_greeting_comment_response"
        )
        self.mock_event_queue.put.assert_called_once()
        put_command = self.mock_event_queue.put.call_args[0][0]
        self.assertIsInstance(put_command, PlaySpeech)
        self.assertEqual(put_command.task_id, "queued_task_1")


    def test_theme_reading_completion_with_pending_comments_triggers_comment_response(self):
        """テーマ朗読完了時に保留コメントがあれば、コメント応答が開始されることを確認"""
        # 1. セットアップ: テーマ朗読が完了した直後の状態
        task_id = "theme_intro_task_123"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.current_task_type = "theme_intro_reading"
        
        # 保留中のコメントが存在する状態をシミュレート
        self.controller._process_queued_comments = MagicMock(return_value=True)
        self.controller._schedule_next_action = MagicMock()

        # 2. 実行: テーマ朗読の完了イベントを処理
        event = SpeechPlaybackCompleted(task_id=task_id)
        self.controller.handle_speech_playback_completed(event)

        # 3. 検証: 
        # コメント処理が開始され(_process_queued_comments が呼ばれ)、
        # 通常の「次のアクション」(_schedule_next_action) は呼ばれないことを確認
        self.controller._process_queued_comments.assert_called_once()
        self.controller._schedule_next_action.assert_not_called()

    def test_post_theme_reading_comment_processing_uses_correct_task_type(self):
        """テーマ朗読後のコメント処理が、汎用の 'comment_response' タスクタイプを使用することを確認"""
        # 1. セットアップ: テーマ朗読が完了した直後の状態
        task_id = "theme_intro_task_123"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.current_task_type = "theme_intro_reading"
        
        # 保留中のコメントが存在する状態をシミュレート
        self.mock_state_manager.has_pending_comments.return_value = True
        self.mock_state_manager.get_pending_comments.return_value = [{'username': 'test', 'message': 'hello'}]

        # 2. 実行: テーマ朗読の完了イベントを処理
        event = SpeechPlaybackCompleted(task_id=task_id)
        # 実際の `_process_queued_comments` を呼び出すため、ここではモック化しない
        self.controller.handle_speech_playback_completed(event)

        # 3. 検証: 
        # THINKING状態に遷移する際、タスクタイプが 'comment_response' であることを確認
        self.mock_state_manager.set_state.assert_called_once()
        args, kwargs = self.mock_state_manager.set_state.call_args
        # args[0] is state (SystemState.THINKING)
        # args[1] is the new task_id
        # args[2] is the task_type
        self.assertEqual(args[2], "comment_response")

    def test_plays_queued_comment_response_after_monologue_completion(self):
        """独り言の完了後、キューイングされたコメント応答が再生されることを確認"""
        # 1. セットアップ
        # キューに待機中のコメント応答を追加
        queued_response = {
            'task_id': 'queued_comment_task_1',
            'sentences': ['This is a queued response.']
        }
        self.controller.queued_comment_responses.append(queued_response)
        
        # 独り言のタスクが完了したと仮定
        monologue_task_id = "monologue_task_123"
        self.mock_state_manager.current_task_id = monologue_task_id
        self.mock_state_manager.current_task_type = "monologue"

        self.controller._schedule_next_action = MagicMock()

        # 2. 実行
        event = SpeechPlaybackCompleted(task_id=monologue_task_id)
        self.controller.handle_speech_playback_completed(event)

        # 3. 検証
        # PlaySpeechコマンドが、キューイングされた応答の内容で発行される
        self.mock_event_queue.put.assert_called_once()
        put_command = self.mock_event_queue.put.call_args[0][0]
        self.assertIsInstance(put_command, PlaySpeech)
        self.assertEqual(put_command.task_id, queued_response['task_id'])
        self.assertEqual(put_command.sentences, queued_response['sentences'])
        
        # 新しい独り言のスケジュールはされない
        self.controller._schedule_next_action.assert_not_called()

    def test_post_greeting_response_loop_preserves_task_type(self):
        """挨拶後のコメント返信ループが、2回目以降も正しいタスクタイプを引き継ぐことを確認"""
        # 1. セットアップ: 1回目の挨拶後コメント返信が完了した直後の状態
        task_id = "post_greeting_comment_1"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.current_task_type = "post_greeting_comment_response"
        self.controller.post_greeting_response_count = 0 # 1回目の処理に入るところからシミュレート

        # _process_queued_comments が呼び出されることを監視
        self.controller._process_queued_comments = MagicMock(return_value=True)

        # 2. 実行: 1回目の返信完了イベントを処理
        event = SpeechPlaybackCompleted(task_id=task_id)
        self.controller.handle_speech_playback_completed(event)

        # 3. 検証:
        # _process_queued_comments が呼び出される際、task_typeが正しく
        # 'post_greeting_comment_response' に設定されていることを確認
        self.controller._process_queued_comments.assert_called_once_with(
            task_type="post_greeting_comment_response"
        )

    def test_initial_greeting_completion_without_comments_triggers_theme_reading(self):
        """挨拶完了後、コメントがない場合にテーマ朗読が開始されることをテストする"""
        # セットアップ
        task_id = "test_initial_greeting"
        self.mock_state_manager.current_task_id = task_id
        self.mock_state_manager.current_task_type = "initial_greeting"
        self.mock_state_manager.has_pending_comments.return_value = False # 修正
        self.controller._process_queued_comments = MagicMock(return_value=False)
        self.controller._start_theme_reading = MagicMock()

        # イベント作成と処理
        event = SpeechPlaybackCompleted(task_id=task_id)
        self.controller.handle_speech_playback_completed(event)

        # 検証
        self.controller._process_queued_comments.assert_called_once_with(task_type="post_greeting_comment_response")
        self.controller._start_theme_reading.assert_called_once()


if __name__ == '__main__':
    unittest.main() 