import unittest
from unittest.mock import MagicMock, patch
import os
import time
import sys

# テスト対象のモジュールをインポートするためにsys.pathを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 '../../..')))

from v2.services.integrated_comment_manager import IntegratedCommentManager
from v2.core.event_queue import EventQueue
from v2.core.events import NewCommentReceived


class TestIntegratedCommentManager(unittest.TestCase):

    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.mock_event_queue = MagicMock(spec=EventQueue)
        self.video_id = "test_video_id"
        
        # pytchat.create をモック化
        self.patcher_pytchat = patch(
            'v2.services.integrated_comment_manager.pytchat'
        )
        self.mock_pytchat = self.patcher_pytchat.start()
        
        self.mock_chat = MagicMock()
        self.mock_pytchat.create.return_value = self.mock_chat

        # IntegratedCommentManagerのインスタンスを作成
        self.comment_manager = IntegratedCommentManager(
            self.mock_event_queue, self.video_id
        )

    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        self.comment_manager.stop()
        self.patcher_pytchat.stop()

    def _create_mock_comment(self, comment_id, user_name, message):
        """テスト用のモックコメントオブジェクトを作成するヘルパー関数"""
        mock_comment = MagicMock()
        mock_comment.id = comment_id
        mock_comment.author.name = user_name
        mock_comment.author.channelId = f"channel_{user_name}"
        mock_comment.message = message
        mock_comment.datetime = time.strftime('%Y-%m-%d %H:%M:%S')
        # その他の必要な属性も適宜モック化
        mock_comment.author.isOwner = False
        mock_comment.author.isModerator = False
        mock_comment.author.isVerified = False
        mock_comment.author.badgeUrl = None
        mock_comment.amountValue = None
        return mock_comment

    def test_fetch_new_comments_and_avoid_duplicates(self):
        """新しいコメントを取得し、重複を避ける機能のテスト"""
        # --- 1回目のコメント取得 ---
        # モックコメントを作成
        comments_batch1 = [
            self._create_mock_comment("id1", "user1", "Hello"),
            self._create_mock_comment("id2", "user2", "World"),
        ]
        self.mock_chat.get.return_value.sync_items.return_value = comments_batch1

        # fetchを直接呼び出してテスト
        new_comments = self.comment_manager._fetch_youtube_comments()
        
        # 結果の検証
        self.assertEqual(len(new_comments), 2)
        self.assertEqual(new_comments[0]['message_id'], 'id1')
        self.assertEqual(new_comments[1]['message_id'], 'id2')
        self.assertEqual(
            self.comment_manager.processed_comment_ids, {'id1', 'id2'}
        )

        # --- 2回目のコメント取得（重複） ---
        # 同じコメントリストを返すように設定
        self.mock_chat.get.return_value.sync_items.return_value = comments_batch1
        new_comments_duplicate = self.comment_manager._fetch_youtube_comments()

        # 結果の検証（新しいコメントはないはず）
        self.assertEqual(len(new_comments_duplicate), 0)
        self.assertEqual(
            self.comment_manager.processed_comment_ids, {'id1', 'id2'}
        )

        # --- 3回目のコメント取得（新しいコメント1件追加） ---
        comments_batch2 = [
            self._create_mock_comment("id1", "user1", "Hello"),
            self._create_mock_comment("id2", "user2", "World"),
            self._create_mock_comment("id3", "user3", "New Comment!"),
        ]
        self.mock_chat.get.return_value.sync_items.return_value = comments_batch2
        new_comments_with_new = self.comment_manager._fetch_youtube_comments()

        # 結果の検証（新しいコメント1件だけが取得される）
        self.assertEqual(len(new_comments_with_new), 1)
        self.assertEqual(new_comments_with_new[0]['message_id'], 'id3')
        self.assertEqual(
            self.comment_manager.processed_comment_ids, {'id1', 'id2', 'id3'}
        )

    def test_monitor_comments_flow(self):
        """コメント監視ループが重複なくイベントを発行するかのテスト"""
        # --- 1回目のループ ---
        comments_batch1 = [self._create_mock_comment("id1", "user1", "First")]
        self.mock_chat.get.return_value.sync_items.return_value = comments_batch1
        
        # _monitor_commentsを1回だけ実行するシミュレーション
        with patch.object(self.comment_manager,
                          'running',
                          side_effect=[True, False]):
            self.comment_manager._monitor_comments()
        
        # イベントが1回発行されたことを確認
        self.mock_event_queue.put.assert_called_once()
        args, _ = self.mock_event_queue.put.call_args
        event = args[0]
        self.assertIsInstance(event, NewCommentReceived)
        self.assertEqual(len(event.comments), 1)
        self.assertEqual(event.comments[0]['message_id'], 'id1')

        # --- 2回目のループ（同じコメント） ---
        self.mock_event_queue.reset_mock()  # putの呼び出し履歴をリセット
        self.mock_chat.get.return_value.sync_items.return_value = comments_batch1
        
        with patch.object(self.comment_manager,
                          'running',
                          side_effect=[True, False]):
            self.comment_manager._monitor_comments()
        
        # イベントが発行されないことを確認
        self.mock_event_queue.put.assert_not_called()


if __name__ == '__main__':
    unittest.main() 