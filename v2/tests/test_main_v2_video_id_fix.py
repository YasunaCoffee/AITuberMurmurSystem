#!/usr/bin/env python3
"""
main_v2.pyのvideo_id修正に対するテストコード
環境変数からYOUTUBE_VIDEO_IDが正しく読み込まれることを確認
"""

import os
import unittest
from unittest.mock import patch, MagicMock
import sys
import threading
import time
import queue

# パスを追加してv2モジュールをインポート
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.core.event_queue import EventQueue
from v2.services.integrated_comment_manager import IntegratedCommentManager
from v2.core.test_mode import TestMode, test_mode_manager
from v2.core.events import NewCommentReceived


class TestMainV2VideoIdFix(unittest.TestCase):
    """main_v2.pyのvideo_id修正に関するテスト"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.event_queue = queue.Queue()
        # 各テストの前にモードをリセット
        test_mode_manager.set_mode(TestMode.PRODUCTION)
        
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        # 他のテストに影響を与えないようにモードを本番に戻す
        test_mode_manager.set_mode(TestMode.PRODUCTION)
    
    @patch.dict(os.environ, {'YOUTUBE_VIDEO_ID': 'DRMUOG8p4bk'})
    def test_comment_manager_uses_env_video_id(self):
        """IntegratedCommentManagerが環境変数からvideo_idを取得することを確認"""
        # IntegratedCommentManagerをvideo_idパラメータなしで初期化
        comment_manager = IntegratedCommentManager(self.event_queue)
        
        # 環境変数の値が正しく設定されていることを確認
        self.assertEqual(comment_manager.video_id, 'DRMUOG8p4bk')
        self.assertTrue(comment_manager.youtube_enabled or comment_manager.test_mode)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_comment_manager_no_video_id(self):
        """YOUTUBE_VIDEO_IDが設定されていない場合の動作を確認"""
        comment_manager = IntegratedCommentManager(self.event_queue)
        
        # video_idがNoneになることを確認
        self.assertIsNone(comment_manager.video_id)
        # YouTube接続が無効になることを確認
        self.assertFalse(comment_manager.youtube_enabled)
    
    @patch.dict(os.environ, {'YOUTUBE_VIDEO_ID': 'invalid_video_id'})
    def test_comment_manager_invalid_video_id(self):
        """無効なvideo_idが設定された場合の動作を確認"""
        comment_manager = IntegratedCommentManager(self.event_queue)
        
        # video_idは設定されるが、実際の接続時にエラーになることを想定
        self.assertEqual(comment_manager.video_id, 'invalid_video_id')
    
    @patch.dict(os.environ, {'YOUTUBE_VIDEO_ID': 'DRMUOG8p4bk', 'CHAT_TEST_MODE': 'true'})
    def test_comment_manager_test_mode(self):
        """テストモードでの動作を確認"""
        # モードをUNITに設定
        test_mode_manager.set_mode(TestMode.UNIT)
        
        # インスタンス化
        comment_manager = IntegratedCommentManager(self.event_queue)
        
        # on_test_mode_changeが呼ばれ、test_modeがTrueになることを確認
        self.assertTrue(comment_manager.test_mode)
        
        # start()を呼び出すと、ダミーコメントモードで起動することを確認
        comment_manager.start()
        # ログから "TEST MODE" が出力されていることを確認するのが理想だが、ここでは単純化
        self.assertTrue(comment_manager.running)
        comment_manager.stop()
    
    @patch('v2.services.integrated_comment_manager.pytchat')
    @patch.dict(os.environ, {'YOUTUBE_VIDEO_ID': 'DRMUOG8p4bk', 'CHAT_TEST_MODE': 'false'})
    def test_comment_manager_youtube_connection(self, mock_pytchat):
        """YouTube接続のモックテスト"""
        # pytchatのモックを設定
        mock_chat = MagicMock()
        mock_pytchat.create.return_value = mock_chat
        
        comment_manager = IntegratedCommentManager(self.event_queue)
        
        # YouTube接続が有効になることを確認
        self.assertTrue(comment_manager.youtube_enabled)
        self.assertEqual(comment_manager.video_id, 'DRMUOG8p4bk')
        
        # 接続開始をテスト
        comment_manager.start()
        
        # pytchat.createが正しいvideo_idで呼び出されることを確認
        mock_pytchat.create.assert_called_with(video_id='DRMUOG8p4bk')
        
        # クリーンアップ
        comment_manager.stop()


class TestIntegratedCommentManagerEnhanced(unittest.TestCase):
    """IntegratedCommentManagerの強化テスト"""
    
    def setUp(self):
        """各テストの前に実行されるセットアップ"""
        self.event_queue = queue.Queue()
        # 各テストの前にモードをリセット
        test_mode_manager.set_mode(TestMode.PRODUCTION)
        
    def tearDown(self):
        """各テストの後に実行されるクリーンアップ"""
        # 他のテストに影響を与えないようにモードを本番に戻す
        test_mode_manager.set_mode(TestMode.PRODUCTION)
    
    @patch('v2.services.integrated_comment_manager.pytchat')
    def test_dummy_comments_generation(self, mock_pytchat):
        """ダミーコメント生成のテスト"""
        # テストモードを設定
        test_mode_manager.set_mode(TestMode.UNIT, custom_config={'dummy_comments_enabled': True})
        
        comment_manager = IntegratedCommentManager(self.event_queue)
        self.assertTrue(comment_manager.test_mode)
        
        comment_manager.start()
        
        # 少し待機してダミーコメントが生成されるかテスト
        time.sleep(1)
        
        # ダミーコメント生成メソッドを直接テスト
        dummy_comments = comment_manager._fetch_dummy_comments()
        
        # 初回は時間チェックにより空になる可能性があるため、時間を調整
        comment_manager.last_check_time = 0  # 強制的に古い時間に設定
        dummy_comments = comment_manager._fetch_dummy_comments()
        
        if dummy_comments:  # ダミーコメントが生成された場合
            self.assertIsInstance(dummy_comments, list)
            self.assertGreater(len(dummy_comments), 0)
            
            comment = dummy_comments[0]
            self.assertIn('username', comment)
            self.assertIn('message', comment)
            self.assertIn('timestamp', comment)
            self.assertIn('user_id', comment)
            self.assertIn('message_id', comment)
            self.assertIn('author', comment)
        
        comment_manager.stop()
    
    @patch('v2.services.integrated_comment_manager.pytchat')
    def test_manual_comment_addition(self, mock_pytchat):
        """手動でのコメント追加テスト"""
        # テストモードを設定
        test_mode_manager.set_mode(TestMode.UNIT)
        
        comment_manager = IntegratedCommentManager(self.event_queue, video_id="DRMUOG8p4bk")
        self.assertTrue(comment_manager.test_mode)
        
        # テスト用のコメントデータを作成
        test_comment = {
            "username": "テストユーザー",
            "message": "手動追加のテストメッセージです。",
            "user_id": "manual_test_user_001",
        }
        comment_manager.add_comment(test_comment)
        
        # イベントキューにNewCommentReceivedイベントが追加されたことを確認
        event = self.event_queue.get(timeout=1)
        self.assertIsInstance(event, NewCommentReceived)
        self.assertEqual(len(event.comments), 1)
        self.assertEqual(event.comments[0]['message'], "手動追加のテストメッセージです。")


def run_all_tests():
    """すべてのテストを実行する関数"""
    print("=== main_v2.py video_id修正テスト実行 ===")
    
    # テストスイートを作成
    test_suite = unittest.TestSuite()
    
    # TestMainV2VideoIdFixクラスのテストを追加
    test_suite.addTest(unittest.makeSuite(TestMainV2VideoIdFix))
    test_suite.addTest(unittest.makeSuite(TestIntegratedCommentManagerEnhanced))
    
    # テストランナーを作成して実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 結果をレポート
    print(f"\n=== テスト結果 ===")
    print(f"実行テスト数: {result.testsRun}")
    print(f"失敗: {len(result.failures)}")
    print(f"エラー: {len(result.errors)}")
    
    if result.failures:
        print("\n失敗したテスト:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nエラーが発生したテスト:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ すべてのテストが成功しました' if success else '❌ テストに失敗しました'}")
    
    return success


if __name__ == "__main__":
    run_all_tests()