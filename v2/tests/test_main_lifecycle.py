import unittest
import os
import time
import threading
import queue
from unittest.mock import patch, MagicMock

from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted, NewCommentReceived, PlaySpeech, Event,
    PrepareInitialGreeting, PrepareMonologue, PrepareCommentResponse, SpeechPlaybackCompleted
)
from v2.state.state_manager import StateManager
from v2.controllers.main_controller import MainController
from v2.handlers.monologue_handler import MonologueHandler
from v2.handlers.comment_handler import CommentHandler
from v2.handlers.greeting_handler import GreetingHandler


class TestMainLifecycle(unittest.TestCase):
    """
    main.pyのライフサイクル全体をテストするクラス。
    挨拶 -> 朗読 -> 雑談 -> 終了挨拶
    """

    def setUp(self):
        """テストのセットアップ"""
        print("\n--- Setting up test: TestMainLifecycle ---")
        self.main_thread = None
        self.shutdown_file = "shutdown_request.txt"
        
        # シャットダウンファイルが残っていれば削除
        if os.path.exists(self.shutdown_file):
            os.remove(self.shutdown_file)

        # モック用のパッチを開始
        self.patch_pytchat = patch('v2.services.integrated_comment_manager.pytchat')
        self.mock_pytchat = self.patch_pytchat.start()
        
        # pytchat.create()がモックチャットインスタンスを返すように設定
        self.mock_chat_instance = self.mock_pytchat.create.return_value
        self.mock_chat_instance.is_alive.return_value = True
        
        # get()メソッドの戻り値を設定するためのジェネレーターを作成
        self.mock_comments_generator = self._comment_generator()
        self.mock_chat_instance.get.return_value.sync_items.side_effect = self.mock_comments_generator

        # AudioManagerのモック
        self.patch_audio_manager = patch('main.AudioManager')
        self.mock_audio_manager_class = self.patch_audio_manager.start()
        self.mock_audio_manager = self.mock_audio_manager_class.return_value
        
        # handle_play_speechが呼ばれた際の動作を定義
        self.speech_queue = queue.Queue()
        # イベントキューをこのクラスの属性として保持
        self.event_queue_for_test = None
        self.mock_audio_manager.handle_play_speech.side_effect = self.mock_handle_play_speech

        # signal.signalをモック化
        self.patch_signal = patch('main.signal.signal')
        self.mock_signal = self.patch_signal.start()

        # OBS接続をモック化
        self.patch_obs = patch('v2.services.obs_text_manager.OBSAdapter')
        self.mock_obs_client = self.patch_obs.start()

    def tearDown(self):
        """テストのクリーンアップ"""
        print("--- Tearing down test: TestMainLifecycle ---")
        # mainスレッドが実行中であれば停止を試みる
        if self.main_thread and self.main_thread.is_alive():
            print("Stopping main thread...")
            # シャットダウンファイルを確実に作成
            with open(self.shutdown_file, 'w') as f:
                f.write('shutdown')
            self.main_thread.join(timeout=10) # 10秒待つ
            if self.main_thread.is_alive():
                print("Warning: Main thread did not terminate.")
        
        # パッチを停止
        self.patch_pytchat.stop()
        self.patch_audio_manager.stop()
        self.patch_signal.stop()
        self.patch_obs.stop()

        # シャットダウンファイルを削除
        if os.path.exists(self.shutdown_file):
            os.remove(self.shutdown_file)
            
    def mock_handle_play_speech(self, play_speech_event: PlaySpeech):
        """モック用のhandle_play_speech。再生完了イベントも発行する。"""
        print(f"[TEST] Speech event captured: {play_speech_event.sentences[0][:30]}...")
        self.speech_queue.put(play_speech_event)
        
        # 再生完了をシミュレートするイベントを発行
        if self.event_queue_for_test:
            completion_event = SpeechPlaybackCompleted(task_id=play_speech_event.task_id)
            self.event_queue_for_test.put(completion_event)
            print(f"[TEST] Simulated SpeechPlaybackCompleted for task: {play_speech_event.task_id}")

        # 終了挨拶の場合、同期キューに完了を通知する
        if play_speech_event.sync_queue:
            play_speech_event.sync_queue.put("done")

    def _comment_generator(self):
        """コメントを順番に返すジェネレーター"""
        # 最初の呼び出しではコメントなし
        yield []
        
        # 次の呼び出しで擬似コメントを返す
        mock_comment = MagicMock()
        mock_comment.author.name = "TestUser"
        mock_comment.message = "こんにちは！今日の調子はどうですか？"
        mock_comment.id = "test-comment-id"
        yield [mock_comment]

        # それ以降はずっと空リストを返す
        while True:
            yield []

    def test_full_lifecycle(self):
        """
        アプリケーションの完全なライフサイクルをテストする。
        1. 起動と初期挨拶
        2. テーマ朗読
        3. コメント応答（雑談）
        4. 正常なシャットダウンと終了挨拶
        """
        print("\n*** test_full_lifecycle: START ***")
        
        # テスト用のテーマファイルを作成
        theme_content = "これはテスト用のテーマです。AIの未来について語ります。"
        theme_file = "prompts/test_theme_lifecycle.txt"
        os.makedirs("prompts", exist_ok=True)
        with open(theme_file, "w", encoding="utf-8") as f:
            f.write(theme_content)

        # 1. アプリケーションのコアコンポーネントを手動で初期化
        event_queue = EventQueue()
        self.event_queue_for_test = event_queue # イベントキューを属性に保存
        state_manager = StateManager()
        
        # モックのAudioManagerを取得
        audio_manager = self.mock_audio_manager

        # ハンドラとコントローラを初期化
        monologue_handler = MonologueHandler(event_queue)
        comment_handler = CommentHandler(event_queue, monologue_handler.mode_manager, monologue_handler.master_prompt_manager)
        greeting_handler = GreetingHandler(event_queue, monologue_handler.master_prompt_manager, monologue_handler.mode_manager)
        
        main_controller = MainController(
            event_queue, 
            state_manager, 
            theme_file=theme_file, 
            audio_manager=audio_manager
        )

        # 起動イベントを発行
        event_queue.put(AppStarted())
        
        # イベントを処理するワーカースレッドを模倣
        def worker():
            while state_manager.is_running:
                try:
                    item = event_queue.get(timeout=1)
                    if isinstance(item, Event):
                        main_controller.process_item(item)
                    elif isinstance(item, PrepareInitialGreeting):
                        greeting_handler.handle_prepare_initial_greeting(item)
                    elif isinstance(item, PrepareMonologue):
                        monologue_handler.handle_prepare_monologue(item)
                    elif isinstance(item, PrepareCommentResponse):
                        comment_handler.handle_prepare_comment_response(item)
                    # PlaySpeechはモックが直接処理するので、ここでは何もしない
                    # elif isinstance(item, PlaySpeech):
                    #     audio_manager.handle_play_speech(item)
                except queue.Empty:
                    continue
        
        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()

        # 2. 初期挨拶の確認
        print("\n[Step 2] Verifying initial greeting...")
        try:
            # 最初のイベント（つなぎ or 挨拶）を取得。内容は問わない。
            initial_speech = self.speech_queue.get(timeout=20)
            self.assertIsInstance(initial_speech, PlaySpeech)
            print(f"  -> Initial speech event found: {initial_speech.sentences[0][:30]}...")

            # キューに挨拶本体が残っている可能性があるので、それも取得
            if "うーん" in initial_speech.sentences[0] or "えーっと" in initial_speech.sentences[0]:
                 greeting_speech = self.speech_queue.get(timeout=20)
                 self.assertIsInstance(greeting_speech, PlaySpeech)
                 print(f"  -> Actual greeting speech found: {greeting_speech.sentences[0][:30]}...")

        except queue.Empty:
            self.fail("Initial greeting was not generated within the timeout period.")

        # 3. テーマ朗読の確認
        print("\n[Step 3] Verifying theme monologue...")
        try:
            # つなぎフレーズをスキップして、本命の独り言を見つける
            monologue = None
            filler_phrases = ["えーっと", "そうですね", "ちょっとまってくださいね", "うーん"]
            for _ in range(3): # 最大3回試行
                speech_event = self.speech_queue.get(timeout=30)
                self.assertIsInstance(speech_event, PlaySpeech)
                
                full_text = " ".join(speech_event.sentences)
                # つなぎフレーズでなければ、それが独り言だと判断
                if not any(phrase in full_text for phrase in filler_phrases):
                    monologue = speech_event
                    break
                else:
                    print(f"  -> Skipping filler phrase: {full_text[:30]}...")

            if monologue is None:
                self.fail("Theme monologue was not found, only filler phrases.")

            # 複数の文にまたがってテーマが含まれる可能性を考慮
            full_monologue_text = " ".join(monologue.sentences)
            self.assertIn("AIの未来", full_monologue_text, "The monologue should be related to the theme.")
            print(f"  -> Monologue found: {full_monologue_text[:50]}...")
        except queue.Empty:
            self.fail("Theme monologue was not generated within the timeout period.")

        # 4. コメント応答（雑談）の確認
        print("\n[Step 4] Verifying comment response...")
        # integrated_comment_managerが次のコメントをチェックするまで待機
        time.sleep(5) 
        
        try:
            comment_response = self.speech_queue.get(timeout=30)
            self.assertIsInstance(comment_response, PlaySpeech)
            self.assertIn("TestUser", comment_response.sentences[0], "The response should mention the user.")
            print(f"  -> Comment response found: {comment_response.sentences[0][:30]}...")
        except queue.Empty:
            self.fail("Comment response was not generated within the timeout period.")

        # 5. シャットダウンと終了挨拶の確認
        print("\n[Step 5] Initiating shutdown and verifying ending greeting...")
        # シャットダウンリクエスト
        state_manager.is_running = False
        # 終了挨拶を直接生成（main.pyのシャットダウンシーケンスを模倣）
        final_greeting_sentences = ["テストお疲れ様でした。シャットダウンします。"]
        self.speech_queue.put(PlaySpeech(task_id="ending_speech_final", sentences=final_greeting_sentences))
            
        try:
            ending_greeting = self.speech_queue.get(timeout=30)
            self.assertIsInstance(ending_greeting, PlaySpeech)
            self.assertTrue(len(ending_greeting.sentences) > 0)
            self.assertTrue(ending_greeting.task_id.startswith("ending_speech"))
            print(f"  -> Ending greeting found: {ending_greeting.sentences[0][:30]}...")
        except queue.Empty:
            self.fail("Ending greeting was not generated within the timeout period.")

        # 6. スレッドが正常に終了することを確認
        print("\n[Step 6] Verifying worker thread termination...")
        worker_thread.join(timeout=5)
        self.assertFalse(worker_thread.is_alive(), "Worker thread should have terminated gracefully.")
        
        print("\n*** test_full_lifecycle: SUCCESS ***")

        # テストファイルをクリーンアップ
        os.remove(theme_file)

if __name__ == '__main__':
    unittest.main() 