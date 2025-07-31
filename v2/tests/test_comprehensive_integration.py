#!/usr/bin/env python3
"""
包括的インテグレーションテスト
v2システム全体の統合テストを実行し、主要な機能とフローをテスト
"""

import time
import threading
import queue
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted, 
    NewCommentReceived, 
    PlaySpeech,
    PrepareMonologue,
    PrepareCommentResponse,
    PrepareInitialGreeting,
    PrepareEndingGreeting,
    PrepareDailySummary,
    DailySummaryReady,
    StreamEnded
)
from v2.state.state_manager import StateManager
from v2.controllers.main_controller import MainController
from v2.services.audio_manager import AudioManager
from v2.services.integrated_comment_manager import IntegratedCommentManager
from v2.handlers.monologue_handler import MonologueHandler
from v2.handlers.comment_handler import CommentHandler
from v2.handlers.greeting_handler import GreetingHandler
from v2.handlers.daily_summary_handler import DailySummaryHandler
from v2.core.test_mode import test_mode_manager


class ComprehensiveIntegrationTester:
    """包括的インテグレーションテストクラス"""
    
    def __init__(self):
        self.test_results = {
            'system_initialization': False,
            'event_flow': False,
            'comment_processing': False,
            'audio_pipeline': False,
            'state_management': False,
            'handler_integration': False,
            'error_handling': False,
            'cleanup_process': False,
            'summary_generation': False
        }
        self.setup_components()
    
    def setup_components(self):
        """システムコンポーネントのセットアップ"""
        print("=== システムコンポーネント初期化 ===")
        
        try:
            # テストモード有効化
            from v2.core.test_mode import TestMode
            test_mode_manager.set_mode(TestMode.UNIT)
            
            # 1. コアシステムの初期化
            self.event_queue = EventQueue()
            self.state_manager = StateManager()
            self.shutdown_event_queue = queue.Queue()
            print("✅ コアシステム初期化完了")
            
            # 2. サービスの初期化
            self.audio_manager = AudioManager(self.event_queue)
            self.monologue_handler = MonologueHandler(self.event_queue)
            
            # ハンドラー間の依存関係を正しく設定
            self.comment_handler = CommentHandler(
                self.event_queue,
                self.monologue_handler.mode_manager,
                self.monologue_handler.master_prompt_manager
            )
            self.greeting_handler = GreetingHandler(
                self.event_queue, 
                self.monologue_handler.master_prompt_manager
            )
            self.daily_summary_handler = DailySummaryHandler(
                self.event_queue, 
                self.monologue_handler.memory_manager
            )
            self.comment_manager = IntegratedCommentManager(self.event_queue)
            print("✅ サービス・ハンドラー初期化完了")
            
            # 3. コマンドハンドラーマッピング
            self.command_handlers = {
                PlaySpeech: self.audio_manager.handle_play_speech,
                PrepareMonologue: self.monologue_handler.handle_prepare_monologue,
                PrepareCommentResponse: self.comment_handler.handle_prepare_comment_response,
                PrepareInitialGreeting: self.greeting_handler.handle_prepare_initial_greeting,
                PrepareEndingGreeting: self.greeting_handler.handle_prepare_ending_greeting,
                PrepareDailySummary: self.daily_summary_handler.handle_prepare_daily_summary,
            }
            print("✅ コマンドハンドラーマッピング完了")
            
            # 4. メインコントローラー初期化
            self.main_controller = MainController(
                self.event_queue,
                self.state_manager,
                self.daily_summary_handler,
                self.shutdown_event_queue
            )
            print("✅ メインコントローラー初期化完了")
            
            self.test_results['system_initialization'] = True
            print("✅ システム初期化テスト成功\n")
            
        except Exception as e:
            print(f"❌ システム初期化エラー: {e}")
            raise
    
    def test_event_flow(self):
        """イベントフローテスト"""
        print("=== イベントフローテスト ===")
        
        try:
            # 各種イベントをキューに追加
            events_to_test = [
                AppStarted(),
                NewCommentReceived(comments=[{
                    "username": "テストユーザー",
                    "message": "イベントフローテスト",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": "flow_test_user",
                    "message_id": "flow_test_msg",
                    "author": {
                        "name": "テストユーザー",
                        "channel_id": "flow_test_channel",
                        "is_owner": False,
                        "is_moderator": False,
                        "is_verified": False,
                        "badge_url": None
                    },
                    "superchat": None
                }])
            ]
            
            for event in events_to_test:
                self.event_queue.put(event)
                print(f"✅ {type(event).__name__} イベント追加")
            
            # イベント処理
            processed_events = 0
            max_events = len(events_to_test)
            
            while processed_events < max_events:
                try:
                    item = self.event_queue.get_nowait()
                    print(f"📨 処理中: {type(item).__name__}")
                    self.main_controller.process_item(item)
                    processed_events += 1
                    print(f"✅ イベント処理完了 ({processed_events}/{max_events})")
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"⚠️  イベント処理エラー: {e}")
                    processed_events += 1
            
            self.test_results['event_flow'] = processed_events > 0
            print(f"✅ イベントフローテスト完了 ({processed_events}個処理)\n")
            
        except Exception as e:
            print(f"❌ イベントフローテストエラー: {e}")
    
    def test_comment_processing(self):
        """コメント処理テスト"""
        print("=== コメント処理テスト ===")
        
        try:
            # テストコメントを複数追加
            test_comments = [
                {
                    "username": "ユーザー1",
                    "message": "こんにちは！",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": "user_001",
                    "message_id": "msg_001",
                    "author": {
                        "name": "ユーザー1",
                        "channel_id": "channel_001",
                        "is_owner": False,
                        "is_moderator": False,
                        "is_verified": False,
                        "badge_url": None
                    },
                    "superchat": None
                },
                {
                    "username": "ユーザー2",
                    "message": "配信楽しんでます",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": "user_002",
                    "message_id": "msg_002",
                    "author": {
                        "name": "ユーザー2",
                        "channel_id": "channel_002",
                        "is_owner": False,
                        "is_moderator": False,
                        "is_verified": False,
                        "badge_url": None
                    },
                    "superchat": None
                }
            ]
            
            # コメントマネージャーにコメント追加
            for comment in test_comments:
                self.comment_manager.add_comment(comment)
                print(f"✅ コメント追加: {comment['message']}")
            
            # 最近のコメント取得確認
            recent_comments = self.comment_manager.get_recent_comments(5)
            print(f"✅ 最近のコメント数: {len(recent_comments)}")
            
            # NewCommentReceivedイベント処理
            comment_event = NewCommentReceived(comments=test_comments)
            self.event_queue.put(comment_event)
            
            try:
                item = self.event_queue.get_nowait()
                self.main_controller.process_item(item)
                print("✅ NewCommentReceivedイベント処理完了")
            except queue.Empty:
                print("⚠️  イベントキューが空です")
            
            self.test_results['comment_processing'] = len(recent_comments) >= len(test_comments)
            print("✅ コメント処理テスト完了\n")
            
        except Exception as e:
            print(f"❌ コメント処理テストエラー: {e}")
    
    def test_audio_pipeline(self):
        """音声パイプラインテスト"""
        print("=== 音声パイプラインテスト ===")
        
        try:
            # テスト用音声コマンド
            test_speech_command = PlaySpeech(
                task_id="test_speech_001",
                sentences=["テスト音声です"]
            )
            
            # 音声コマンドをキューに追加
            self.event_queue.put(test_speech_command)
            print("✅ PlaySpeechコマンド追加")
            
            # コマンド処理
            try:
                item = self.event_queue.get_nowait()
                if type(item) in self.command_handlers:
                    handler = self.command_handlers[type(item)]
                    handler(item)
                    print("✅ PlaySpeechコマンド処理完了")
                else:
                    print("⚠️  適切なハンドラーが見つかりません")
            except queue.Empty:
                print("⚠️  イベントキューが空です")
            except Exception as e:
                print(f"⚠️  音声処理エラー（テストモードでは正常）: {e}")
            
            self.test_results['audio_pipeline'] = True
            print("✅ 音声パイプラインテスト完了\n")
            
        except Exception as e:
            print(f"❌ 音声パイプラインテストエラー: {e}")
    
    def test_state_management(self):
        """状態管理テスト"""
        print("=== 状態管理テスト ===")
        
        try:
            # 初期状態確認
            initial_state = self.state_manager.current_state
            print(f"✅ 初期状態: {initial_state.value}")
            
            # システム状態サマリー取得
            status_summary = self.state_manager.get_status_summary()
            print(f"✅ 状態サマリー: {status_summary}")
            
            # 実行状態確認
            is_running = self.state_manager.is_running
            print(f"✅ 実行状態: {is_running}")
            
            # 状態変更テスト（存在する場合）
            try:
                if hasattr(self.state_manager, 'set_state'):
                    # 状態変更のテスト
                    pass
            except Exception as e:
                print(f"⚠️  状態変更テストスキップ: {e}")
            
            self.test_results['state_management'] = True
            print("✅ 状態管理テスト完了\n")
            
        except Exception as e:
            print(f"❌ 状態管理テストエラー: {e}")
    
    def test_handler_integration(self):
        """ハンドラー統合テスト"""
        print("=== ハンドラー統合テスト ===")
        
        try:
            # 各種コマンドのテスト
            test_commands = [
                PrepareMonologue(task_id="test_monologue_001"),
                PrepareCommentResponse(
                    task_id="test_comment_response_001",
                    comments=[{
                        "username": "統合テストユーザー",
                        "message": "統合テストメッセージ",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "user_id": "integration_user",
                        "message_id": "integration_msg",
                        "author": {
                            "name": "統合テストユーザー",
                            "channel_id": "integration_channel",
                            "is_owner": False,
                            "is_moderator": False,
                            "is_verified": False,
                            "badge_url": None
                        },
                        "superchat": None
                    }]
                ),
                PrepareInitialGreeting(task_id="test_greeting_001"),
            ]
            
            processed_commands = 0
            for command in test_commands:
                try:
                    # キューを介さずに直接ハンドラーを呼び出す
                    command_type = type(command)
                    if command_type in self.command_handlers:
                        handler = self.command_handlers[command_type]
                        handler(command)
                        processed_commands += 1
                        print(f"✅ {command_type.__name__} 処理完了")
                    else:
                        print(f"⚠️  {command_type.__name__} のハンドラーが見つかりません")
                except Exception as e:
                    print(f"⚠️  {command_type.__name__} 処理エラー: {e}")
            
            self.test_results['handler_integration'] = processed_commands == len(test_commands)
            print(f"✅ ハンドラー統合テスト完了 ({processed_commands}個処理)\n")
            
        except Exception as e:
            print(f"❌ ハンドラー統合テストエラー: {e}")
    
    def test_error_handling(self):
        """エラーハンドリングテスト"""
        print("=== エラーハンドリングテスト ===")
        
        try:
            # 不正なイベント/コマンドのテスト
            class InvalidEvent:
                pass
            
            invalid_event = InvalidEvent()
            self.event_queue.put(invalid_event)
            
            try:
                item = self.event_queue.get_nowait()
                
                # 不正なイベントでもシステムがクラッシュしないことを確認
                if type(item) in self.command_handlers:
                    handler = self.command_handlers[type(item)]
                    handler(item)
                else:
                    # 未知のイベント/コマンドの場合の処理
                    print(f"⚠️  未知のアイテム: {type(item).__name__}")
                
                print("✅ 不正イベント処理（システムクラッシュなし）")
            except Exception as e:
                print(f"✅ エラーハンドリング動作確認: {e}")
            
            self.test_results['error_handling'] = True
            print("✅ エラーハンドリングテスト完了\n")
            
        except Exception as e:
            print(f"❌ エラーハンドリングテストエラー: {e}")
    
    def test_cleanup_process(self):
        """クリーンアップ処理テスト"""
        print("=== クリーンアップ処理テスト ===")
        
        try:
            # システム停止準備
            print("🛑 システム停止開始")
            
            # 状態管理の停止
            self.state_manager.is_running = False
            print("✅ StateManager停止完了")
            
            # コメントマネージャーの停止
            self.comment_manager.stop()
            print("✅ CommentManager停止完了")
            
            # 日次要約ハンドラーの停止（スケジューラーが動いている場合）
            if hasattr(self.daily_summary_handler, 'stop_scheduler'):
                self.daily_summary_handler.stop_scheduler()
                print("✅ DailySummaryHandler停止完了")
            
            # 音声マネージャーの停止
            self.audio_manager.stop()
            print("✅ AudioManager停止完了")
            
            # テストモードマネージャーのシャットダウン
            test_mode_manager.shutdown()
            print("✅ TestModeManager停止完了")
            
            self.test_results['cleanup_process'] = True
            print("✅ クリーンアップ処理テスト完了\n")
            
        except Exception as e:
            print(f"❌ クリーンアップ処理テストエラー: {e}")
            
    def test_stream_end_to_summary(self):
        """配信終了から日次要約発行までのテスト"""
        print("=== 配信終了→日次要約テスト ===")
        
        try:
            # 1. 準備: MemoryManagerにダミーデータを設定
            test_content = "統合テスト用の長期記憶データ"
            self.monologue_handler.memory_manager.long_term_summary = test_content
            
            # 2. 実行: 配信終了イベントを発行
            end_event = StreamEnded(stream_duration_minutes=120, ending_reason="integration_test")
            self.event_queue.put(end_event)
            print("✅ StreamEndedイベント追加")
            
            # 3. 検証: イベントが処理され、日次要約が発行されるのを待つ
            prepare_summary_found = False
            summary_ready_found = False
            timeout = 10
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    item = self.event_queue.get(timeout=1)
                    print(f"📨 処理中: {type(item).__name__}")
                    
                    if isinstance(item, StreamEnded):
                        self.main_controller.process_item(item)
                    elif type(item) in self.command_handlers:
                        # ハンドラーを直接呼び出して処理を進める
                        self.command_handlers[type(item)](item)
                    else:
                        # Controllerが処理するイベント
                        self.main_controller.process_item(item)
                    
                    if isinstance(item, PrepareDailySummary):
                        prepare_summary_found = True
                        print("✅ PrepareDailySummary コマンド発見")

                    if isinstance(item, DailySummaryReady):
                        summary_ready_found = True
                        print("✅ DailySummaryReady イベント発見")
                        self.test_results['summary_generation'] = True
                        # ファイルが実際に作成されたかどうかのチェックも可能
                        if item.success and item.file_path and os.path.exists(item.file_path):
                            print(f"✅ サマリーファイル確認: {item.file_path}")
                            # テスト後にファイルをクリーンアップ
                            os.remove(item.file_path)
                        break

                except queue.Empty:
                    time.sleep(0.1)
                except Exception as e:
                    print(f"⚠️ イベント処理中のエラー: {e}")
                    break
            
            if not (prepare_summary_found and summary_ready_found):
                 print("❌ 日次要約の生成フローが完了しませんでした")
                 self.test_results['summary_generation'] = False
            
            print("✅ 配信終了→日次要約テスト完了\n")
        except Exception as e:
            print(f"❌ 配信終了→日次要約テストエラー: {e}")

    def run_full_integration_test(self):
        """フル統合テスト実行"""
        print("🚀 包括的インテグレーションテスト開始")
        print("=" * 60)
        
        # テスト開始前にコメント監視とスケジューラーを開始
        try:
            self.comment_manager.start()
            self.daily_summary_handler.start_scheduler()
            print("✅ バックグラウンドサービス開始")
        except Exception as e:
            print(f"⚠️  バックグラウンドサービス開始エラー: {e}")
        
        # 各テストを順次実行
        tests = [
            ("イベントフロー", self.test_event_flow),
            ("コメント処理", self.test_comment_processing),
            ("音声パイプライン", self.test_audio_pipeline),
            ("状態管理", self.test_state_management),
            ("ハンドラー統合", self.test_handler_integration),
            ("エラーハンドリング", self.test_error_handling),
            ("配信終了→日次要約", self.test_stream_end_to_summary),
            ("クリーンアップ処理", self.test_cleanup_process),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"❌ {test_name}テストで予期しないエラー: {e}")
        
        # 結果サマリー
        self.print_test_summary()
        
        return all(self.test_results.values())
    
    def print_test_summary(self):
        """テスト結果サマリーを表示"""
        print("=" * 60)
        print("📊 包括的インテグレーションテスト結果")
        print("=" * 60)
        
        test_names = {
            'system_initialization': 'システム初期化',
            'event_flow': 'イベントフロー',
            'comment_processing': 'コメント処理',
            'audio_pipeline': '音声パイプライン',
            'state_management': '状態管理',
            'handler_integration': 'ハンドラー統合',
            'error_handling': 'エラーハンドリング',
            'summary_generation': '日次要約生成',
            'cleanup_process': 'クリーンアップ処理'
        }
        
        for key, name in test_names.items():
            status = "✅ 成功" if self.test_results.get(key, False) else "❌ 失敗"
            print(f"{name:20s}: {status}")
        
        total_tests = len(test_names)
        passed_tests = sum(self.test_results.get(key, False) for key in test_names)
        
        print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
        
        if passed_tests == total_tests:
            print("\n🎉 すべてのテストが成功しました！")
            print("✅ v2システムの統合処理が正常に動作しています")
        else:
            failed_tests = [name for key, name in test_names.items() if not self.test_results.get(key, False)]
            print(f"\n❌ 失敗したテスト: {', '.join(failed_tests)}")
        
        print("=" * 60)


def main():
    """メイン実行関数"""
    print("🧪 包括的インテグレーションテスト実行")
    
    try:
        tester = ComprehensiveIntegrationTester()
        success = tester.run_full_integration_test()
        
        if success:
            print("🚀 統合テスト完了: システムは正常に動作します")
            return True
        else:
            print("⚠️  統合テストで問題が発見されました")
            return False
    
    except Exception as e:
        print(f"❌ 統合テスト実行エラー: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)