import unittest
import time
import numpy as np
from unittest.mock import MagicMock, patch

from v2.core.event_queue import EventQueue
from v2.services.audio_manager import AudioManager
from v2.core.events import PlaySpeech, SpeechPlaybackCompleted

# モックする対象のパス
AIVIS_ADAPTER_PATH = "v2.services.audio_manager.AivisSpeechAdapter"
SOUNDDEVICE_PATH = "v2.services.audio_manager.sd"


class TestAudioManager(unittest.TestCase):

    def setUp(self):
        """テストのセットアップ。依存関係をモック化する。"""
        self.event_queue = EventQueue()
        self.event_queue.put = MagicMock()

        # パッチを開始
        self.aivis_patcher = patch(AIVIS_ADAPTER_PATH)
        self.sounddevice_patcher = patch(SOUNDDEVICE_PATH)
        
        mock_aivis_adapter = self.aivis_patcher.start()
        self.mock_sounddevice = self.sounddevice_patcher.start()
        
        # モックのインスタンスと返り値を設定
        self.mock_aivis_adapter_instance = mock_aivis_adapter.return_value
        self.mock_aivis_adapter_instance.get_voice.return_value = (
            np.zeros(100, dtype=np.float32), 24000
        )
        
        # AudioManagerのインスタンス化
        self.audio_manager = AudioManager(self.event_queue)
        time.sleep(0.1)  # ワーカースレッドが開始するのを少し待つ

    def tearDown(self):
        """テストのクリーンアップ。AudioManagerを停止させ、パッチを停止する。"""
        self.audio_manager.stop()
        self.aivis_patcher.stop()
        self.sounddevice_patcher.stop()

    def _wait_for_event(self, timeout=2.0):
        """イベントがキューに追加されるのを待つヘルパー関数"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.event_queue.put.called:
                return self.event_queue.put.call_args[0][0]
            time.sleep(0.01)
        self.fail("Event was not put into the queue within the timeout period.")

    def test_pipeline_single_sentence(self):
        """単一の文章がパイプラインを通り、完了イベントが発行されることを確認する"""
        task_id = "single_sentence_task"
        sentences = ["This is a test."]
        command = PlaySpeech(task_id=task_id, sentences=sentences)

        self.audio_manager.handle_play_speech(command)

        # イベントの発生を待つ
        event = self._wait_for_event()

        # 検証
        self.assertIsInstance(event, SpeechPlaybackCompleted)
        self.assertEqual(event.task_id, task_id)
        self.mock_aivis_adapter_instance.get_voice.assert_called_once_with(
            "This is a test.", 1
        )
        self.mock_sounddevice.play.assert_called_once()
        self.mock_sounddevice.wait.assert_called_once()

    def test_pipeline_multiple_sentences(self):
        """複数の文章が順番に処理され、最後に一度だけ完了イベントが発行されることを確認する"""
        task_id = "multiple_sentences_task"
        sentences = ["Sentence one.", "Sentence two.", "Sentence three."]
        command = PlaySpeech(task_id=task_id, sentences=sentences)

        self.audio_manager.handle_play_speech(command)

        # イベントの発生を待つ
        event = self._wait_for_event(timeout=5.0)  # 複数文なので長めに待つ

        # 検証
        self.assertIsInstance(event, SpeechPlaybackCompleted)
        self.assertEqual(event.task_id, task_id)
        self.assertEqual(
            self.mock_aivis_adapter_instance.get_voice.call_count, 3
        )
        self.assertEqual(self.mock_sounddevice.play.call_count, 3)
        self.assertEqual(self.mock_sounddevice.wait.call_count, 3)
        self.event_queue.put.assert_called_once()  # イベントは1回だけ

    def test_synthesis_failure_continues_pipeline(self):
        """音声合成が失敗してもパイプラインが継続し、完了イベントが発行されることを確認する"""
        task_id = "failure_task"
        sentences = [
            "This will succeed.",
            "This will fail.",
            "This will succeed again."
        ]
        
        # 2番目の合成だけ失敗させるようにモックを設定
        self.mock_aivis_adapter_instance.get_voice.side_effect = [
            (np.zeros(100, dtype=np.float32), 24000),  # 1st success
            Exception("Synthesis API error"),  # 2nd failure
            (np.zeros(100, dtype=np.float32), 24000),  # 3rd success
        ]
        
        command = PlaySpeech(task_id=task_id, sentences=sentences)
        self.audio_manager.handle_play_speech(command)

        event = self._wait_for_event(timeout=5.0)

        # 検証
        self.assertIsInstance(event, SpeechPlaybackCompleted)
        self.assertEqual(event.task_id, task_id)
        self.assertEqual(
            self.mock_aivis_adapter_instance.get_voice.call_count, 3
        )
        # 失敗してもフォールバック用の無音データが再生されるため、playは3回呼ばれる
        self.assertEqual(self.mock_sounddevice.play.call_count, 3)


if __name__ == '__main__':
    unittest.main() 