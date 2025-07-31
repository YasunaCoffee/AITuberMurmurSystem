import os
import unittest
from unittest.mock import Mock, patch
from v2.core.event_queue import EventQueue
from v2.core.events import PlaySpeech, SpeechPlaybackCompleted
from v2.services.obs_text_manager import OBSTextManager

class TestOBSTextManager(unittest.TestCase):
    def setUp(self):
        self.event_queue = Mock(spec=EventQueue)
        self.obs_text_manager = OBSTextManager(self.event_queue)
        self.test_file_path = "txt/obs_answer.txt"
        
        # テスト用のディレクトリを作成
        os.makedirs("txt", exist_ok=True)
    
    def tearDown(self):
        # テストファイルを削除
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
    
    def test_display_subtitle(self):
        """字幕表示のテスト"""
        test_text = "これはテストの字幕です。"
        test_task_id = "test_task_1"
        
        # PlaySpeechイベントを処理
        self.obs_text_manager.handle_play_speech(
            PlaySpeech(task_id=test_task_id, sentences=[test_text])
        )
        
        # ファイルが作成され、内容が正しいことを確認
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertEqual(content, test_text)
    
    def test_clear_subtitle(self):
        """字幕クリアのテスト"""
        # まず字幕を表示
        test_text = "これはテストの字幕です。"
        test_task_id = "test_task_2"
        self.obs_text_manager.handle_play_speech(
            PlaySpeech(task_id=test_task_id, sentences=[test_text])
        )
        
        # 字幕をクリア
        self.obs_text_manager.handle_speech_completed(
            SpeechPlaybackCompleted(task_id=test_task_id)
        )
        
        # ファイルが空になっていることを確認
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertEqual(content, "")
    
    def test_multiple_sentences(self):
        """複数の文章を含む字幕表示のテスト"""
        test_sentences = [
            "1つ目の文章です。",
            "2つ目の文章です。",
            "3つ目の文章です。"
        ]
        test_task_id = "test_task_3"
        
        # PlaySpeechイベントを処理
        self.obs_text_manager.handle_play_speech(
            PlaySpeech(task_id=test_task_id, sentences=test_sentences)
        )
        
        # 最後の文章が表示されていることを確認
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertEqual(content, test_sentences[-1])
    
    @patch("builtins.open")
    def test_error_handling(self, mock_open):
        """エラー処理のテスト"""
        # ファイル操作でエラーを発生させる
        mock_open.side_effect = IOError("Test error")
        
        test_text = "これはテストの字幕です。"
        test_task_id = "test_task_4"
        
        # エラーが発生しても例外が伝播しないことを確認
        try:
            self.obs_text_manager.handle_play_speech(
                PlaySpeech(task_id=test_task_id, sentences=[test_text])
            )
            self.obs_text_manager.handle_speech_completed(
                SpeechPlaybackCompleted(task_id=test_task_id)
            )
        except Exception as e:
            self.fail(f"Unexpected exception raised: {e}")

if __name__ == "__main__":
    unittest.main() 