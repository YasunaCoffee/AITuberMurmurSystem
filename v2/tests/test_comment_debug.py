#!/usr/bin/env python3
"""
コメント処理の詳細デバッグテスト
どの段階で止まっているかを特定する
"""

import sys
import os
import time
import threading
import signal

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from v2.core.event_queue import EventQueue
from v2.handlers.comment_handler import CommentHandler
from v2.core.events import PrepareCommentResponse, CommentResponseReady

def timeout_handler(signum, frame):
    print("\n⏰ タイムアウト！30秒以内に処理が完了しませんでした")
    print("現在実行中のスレッド:")
    for thread in threading.enumerate():
        print(f"  - {thread.name}: {thread.is_alive()}")
    sys.exit(1)

def test_comment_processing_debug():
    """詳細デバッグ付きコメント処理テスト"""
    
    print("=== CommentHandler詳細デバッグテスト ===")
    
    # 30秒でタイムアウト
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)
    
    try:
        print("🔍 Step 1: システム初期化開始...")
        
        # システム初期化
        print("🔍 Step 1.1: EventQueue作成中...")
        event_queue = EventQueue()
        print("✅ EventQueue作成完了")
        
        print("🔍 Step 1.2: CommentHandler作成中...")
        comment_handler = CommentHandler(event_queue)
        print("✅ CommentHandler作成完了")
        
        # テストコメント（シンプルに1件のみ）
        test_comment = {
            'message': 'テストコメント',
            'username': 'テストユーザー',
            'user_id': 'test_user',
            'timestamp': '2025-07-25 13:20:00'
        }
        
        print("🔍 Step 2: コメント処理開始...")
        
        # 進行状況監視用
        processing_started = threading.Event()
        processing_completed = threading.Event()
        response_received = False
        last_log_time = time.time()
        
        def monitor_progress():
            """進行状況を監視"""
            nonlocal response_received, last_log_time
            
            while not processing_completed.is_set():
                try:
                    # キューをチェック
                    item = event_queue.get_nowait()
                    if isinstance(item, CommentResponseReady):
                        print(f"✅ 応答受信成功: {item.task_id}")
                        response_received = True
                        processing_completed.set()
                        return
                except:
                    pass
                
                # 10秒ごとに生存確認
                current_time = time.time()
                if current_time - last_log_time > 10:
                    print(f"🔍 生存確認: {current_time - last_log_time:.1f}秒経過")
                    print(f"🔍 アクティブスレッド数: {threading.active_count()}")
                    for thread in threading.enumerate():
                        if thread.name.startswith("CommentProcessor"):
                            print(f"  - {thread.name}: {'生存中' if thread.is_alive() else '停止'}")
                    last_log_time = current_time
                
                time.sleep(0.5)
        
        # 監視スレッド開始
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()
        
        print("🔍 Step 2.1: PrepareCommentResponseコマンド作成...")
        command = PrepareCommentResponse(task_id='debug_test_001', comments=[test_comment])
        print(f"✅ コマンド作成完了: {command.task_id}")
        
        print("🔍 Step 2.2: handle_prepare_comment_response呼び出し...")
        test_start = time.time()
        
        comment_handler.handle_prepare_comment_response(command)
        
        print("🔍 Step 2.3: 処理完了待機中...")
        processing_completed.wait(timeout=25)
        
        test_duration = time.time() - test_start
        
        # タイムアウト解除
        signal.alarm(0)
        
        # 結果表示
        print("\n" + "="*60)
        print("📊 詳細デバッグテスト結果")
        print("="*60)
        print(f"⏱️  総処理時間: {test_duration:.2f}秒")
        print(f"✅ 応答受信: {'成功' if response_received else '失敗'}")
        print(f"🧵 アクティブスレッド数: {threading.active_count()}")
        
        if not response_received:
            print("\n🔍 失敗原因分析:")
            print("現在のスレッド状況:")
            for thread in threading.enumerate():
                print(f"  - {thread.name}: {'生存中' if thread.is_alive() else '停止'}")
        
        return response_received
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ テスト中にエラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 環境変数設定
    os.environ['CHAT_TEST_MODE'] = 'true'
    
    try:
        success = test_comment_processing_debug()
        print(f"\n🎯 テスト結果: {'成功' if success else '失敗'}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  テスト中断")
        sys.exit(1)