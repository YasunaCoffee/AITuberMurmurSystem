import unittest
from unittest.mock import MagicMock, patch
from queue import Queue

from v2.core.events import PrepareMonologue, MonologueReady
from v2.handlers.monologue_handler import MonologueHandler

class TestMonologueHandler(unittest.TestCase):

    @patch('v2.handlers.monologue_handler.PromptManager')
    @patch('v2.handlers.monologue_handler.MasterPromptManager')
    @patch('v2.handlers.monologue_handler.ModeManager')
    def test_handle_prepare_monologue_with_theme(self, mock_mode_manager, mock_master_prompt_manager, mock_prompt_manager):
        """テーマファイル付きのPrepareMonologueがMonologueReadyイベントを発行することを確認"""
        event_queue = Queue()
        
        # MonologueHandlerをインスタンス化
        handler = MonologueHandler(event_queue)
        
        # handlerインスタンスのopenai_adapterを直接モックに差し替える
        with patch.object(handler, 'openai_adapter', autospec=True) as mock_openai_adapter:
            # セットアップ
            task_id = "test-task-123"
            theme_file = "prompts/test_theme.txt"
            command = PrepareMonologue(task_id=task_id, theme_file=theme_file)
            
            # モックの応答とメソッドを設定
            mock_response_text = "これはテスト用の独り言です。"
            mock_openai_adapter.create_chat_for_response.return_value = mock_response_text
            handler._split_into_sentences = MagicMock(return_value=[mock_response_text])

            # _execute_monologue_in_background を直接呼び出してテスト
            handler._execute_monologue_in_background(command)

            # 検証
            ready_event = event_queue.get(timeout=1)
            self.assertIsInstance(ready_event, MonologueReady)
            self.assertEqual(ready_event.task_id, task_id)
            self.assertEqual(ready_event.sentences, [mock_response_text])

            # LLMへのプロンプト構築が正しく呼ばれたか
            mock_openai_adapter.create_chat_for_response.assert_called_once()


if __name__ == '__main__':
    unittest.main() 