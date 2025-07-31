#!/usr/bin/env python3
"""
日次要約機能のテストスクリプト
"""

import sys
import os
import time

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

import shutil
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import os
import pytz

from v2.handlers.daily_summary_handler import DailySummaryHandler
from v2.core.events import StreamEnded, DailySummaryReady
from v2.core.event_queue import EventQueue
from memory_manager import MemoryManager
from config import config
from openai_adapter import OpenAIAdapter
from v2.core.events import PrepareDailySummary

class TestDailySummaryHandler(unittest.TestCase):
    def setUp(self):
        """テストのセットアップ"""
        # テスト用のサマリーディレクトリを作成
        self.test_summary_dir = "test_summary_dir"
        os.makedirs(self.test_summary_dir, exist_ok=True)
        
        # モックオブジェクトの作成
        self.mock_event_queue = MagicMock(spec=EventQueue)
        self.mock_llm_adapter = MagicMock(spec=OpenAIAdapter)
        
        # MemoryManagerのインスタンスを作成
        self.memory_manager = MemoryManager(
            llm_adapter=self.mock_llm_adapter,
            event_queue=self.mock_event_queue
        )
        
        # DailySummaryHandlerのインスタンスを作成
        self.handler = DailySummaryHandler(
            event_queue=self.mock_event_queue,
            memory_manager=self.memory_manager
        )
        # テスト用にサマリーディレクトリを上書き
        self.handler.summary_dir = self.test_summary_dir
        self.handler.post_stream_summary_enabled = True # テストのため有効化

    def tearDown(self):
        """テストの後片付け"""
        # テスト用のサマリーディレクトリを削除
        if os.path.exists(self.test_summary_dir):
            shutil.rmtree(self.test_summary_dir)

    def test_initialization(self):
        """初期化が正しく行われるかテスト"""
        self.assertEqual(self.handler.summary_dir, self.test_summary_dir)
        self.assertIsNotNone(self.handler.memory_manager)

    def test_manual_daily_summary(self):
        """手動での日次要約が正しく機能するかテスト"""
        # MemoryManagerのsave_daily_summaryをモック化
        with patch.object(self.memory_manager, 'save_daily_summary') as mock_save_summary:
            # 手動で要約をトリガー
            self.handler.trigger_daily_summary()

            # イベントキューからコマンドを取得
            put_command = self.mock_event_queue.put.call_args[0][0]
            self.assertIsInstance(put_command, PrepareDailySummary)

            # コマンドハンドラを直接呼び出し
            self.handler.handle_prepare_daily_summary(put_command)

            # バックグラウンドスレッドが実行されるのを少し待つ
            time.sleep(0.1)

            # memory_manager.save_daily_summary が呼ばれたことを確認
            mock_save_summary.assert_called_once()
            
            # 呼び出し引数を取得して検証
            args, _ = mock_save_summary.call_args
            self.assertEqual(args[0], self.test_summary_dir) # summary_dir
            self.assertEqual(args[1], put_command.task_id) # task_id

    def test_end_to_end_summary_save(self):
        """日次要約がトリガーされてからファイルが実際に保存されるまでをテスト"""
        # 1. 準備: MemoryManagerに長期記憶のダミーデータを設定
        test_summary_content = "これが長期記憶のテスト内容です。"
        with self.memory_manager.lock:
            self.memory_manager.long_term_summary = test_summary_content

        # 2. 実行: 要約生成をトリガーし、ハンドラを呼び出す
        self.handler.trigger_daily_summary()
        
        # イベントキューからコマンドを取得
        prepare_command = self.mock_event_queue.put.call_args[0][0]
        self.assertIsInstance(prepare_command, PrepareDailySummary)
        
        # コマンドハンドラを呼び出す（これによりMemoryManagerの非同期処理が開始される）
        self.handler.handle_prepare_daily_summary(prepare_command)

        # 3. 検証: MemoryManagerの非同期処理が完了し、
        #    DailySummaryReadyイベントがキューに追加されるのを待つ
        
        # イベントがキューに追加されるまで最大5秒待つ
        timeout = 5
        start_time = time.time()
        ready_event = None
        while time.time() - start_time < timeout:
            # mock_event_queue.putが2回呼ばれるのを待つ (PrepareDailySummary, DailySummaryReady)
            if self.mock_event_queue.put.call_count > 1:
                # 2番目のイベントがDailySummaryReadyか確認
                last_call = self.mock_event_queue.put.call_args_list[-1]
                event = last_call[0][0]
                if isinstance(event, DailySummaryReady):
                    ready_event = event
                    break
            time.sleep(0.1)

        # イベントが取得できたか検証
        self.assertIsNotNone(ready_event, "DailySummaryReadyイベントが時間内に発行されませんでした")

        # イベント内容の検証
        self.assertTrue(ready_event.success)
        self.assertIsNotNone(ready_event.file_path)
        self.assertIn(self.test_summary_dir, ready_event.file_path)

        # ファイルの存在と内容を検証
        self.assertTrue(os.path.exists(ready_event.file_path))
        with open(ready_event.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn(test_summary_content, content)
            self.assertIn("# 長期記憶要約", content) # ヘッダーの確認

    def test_summary_file_existence(self):
        """要約ファイルが既に存在する場合、処理がスキップされることをテスト"""
        # ダミーの要約ファイルを先に作成
        summary_path = self.handler.get_today_summary_path()
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("既存の要約")
        
        with patch.object(self.mock_event_queue, 'put') as mock_put:
            self.handler.trigger_daily_summary(reason="manual")
            # イベントキューに何も追加されなかったことを確認
            mock_put.assert_not_called()

    def test_stream_ended_triggers_summary(self):
        """StreamEndedイベントが要約生成をトリガーすることをテスト"""
        with patch.object(self.handler, 'trigger_daily_summary') as mock_trigger:
            stream_ended_event = StreamEnded(
                stream_duration_minutes=60,
                ending_reason="Test ended"
            )
            self.handler.handle_stream_ended(stream_ended_event)
            
            # trigger_daily_summary が呼ばれたことを確認
            mock_trigger.assert_called_once_with(reason="post_stream")


if __name__ == '__main__':
    unittest.main()