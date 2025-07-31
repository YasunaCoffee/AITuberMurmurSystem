import unittest
from unittest.mock import MagicMock, patch
from queue import Queue

from v2.core.events import PrepareCommentResponse, CommentResponseReady
from v2.handlers.comment_handler import CommentHandler

class TestCommentHandler(unittest.TestCase):

    @patch('v2.handlers.comment_handler.PromptManager')
    @patch('v2.handlers.comment_handler.MasterPromptManager')
    @patch('v2.handlers.comment_handler.ModeManager')
    @patch('v2.handlers.comment_handler.CommentFilter')
    @patch('v2.handlers.comment_handler.ConversationHistory')
    @patch('v2.handlers.comment_handler.MemoryManager')
    def test_handle_prepare_comment_response(self, mock_memory, mock_history, mock_filter, mock_mode, mock_master, mock_prompt):
        """PrepareCommentResponseがCommentResponseReadyイベントを発行することを確認"""
        event_queue = Queue()
        
        # CommentHandlerをインスタンス化
        handler = CommentHandler(event_queue, mock_mode.return_value, mock_master.return_value)
        
        # handlerインスタンスのopenai_adapterを直接モックに差し替える
        with patch.object(handler, 'openai_adapter', autospec=True) as mock_openai_adapter:
            # セットアップ
            task_id = "test-comment-task-123"
            comments = [{'username': 'test_user', 'message': 'こんにちは'}]
            command = PrepareCommentResponse(task_id=task_id, comments=comments)
            
            # モックの応答とメソッドを設定
            mock_response_text = "こんにちは、テストユーザーさん。"
            mock_openai_adapter.create_chat_for_response.return_value = mock_response_text
            handler._split_into_sentences = MagicMock(return_value=[mock_response_text])

            # _execute_in_background を直接呼び出してテスト
            handler._execute_in_background(command)

            # 検証
            ready_event = event_queue.get(timeout=1)
            self.assertIsInstance(ready_event, CommentResponseReady)
            self.assertEqual(ready_event.task_id, task_id)
            self.assertEqual(ready_event.sentences, [mock_response_text])
            self.assertEqual(ready_event.original_comments, comments)

            # LLMが呼び出されたことを確認
            mock_openai_adapter.create_chat_for_response.assert_called_once()

if __name__ == '__main__':
    unittest.main() 