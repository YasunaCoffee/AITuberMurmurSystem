#!/usr/bin/env python3
"""
修正されたCommentHandlerのテスト
停止問題が解決されているかを確認
"""

import sys
import os
import time
import threading

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.handlers.comment_handler import CommentHandler
from murmur.core.events import PrepareCommentResponse, CommentResponseReady

print("=== CommentHandler修正版テスト ===")

def test_comment_processing():
    """コメント処理のテスト"""
    
    # システム初期化
    event_queue = EventQueue()
    comment_handler = CommentHandler(event_queue)
    
    # テストコメント
    test_comments = [
        {
            'message': 'こんにちはハヤテちゃん！',
            'username': 'テストユーザー1',
            'user_id': 'user1',
            'timestamp': '2025-07-25 13:10:00'
        },
        {
            'message': '今日の配信楽しいです',
            'username': 'テストユーザー2', 
            'user_id': 'user2',
            'timestamp': '2025-07-25 13:10:05'
        },
        {
            'message': 'ハヤテちゃんかわいい！',
            'username': 'テストユーザー3',
            'user_id': 'user3', 
            'timestamp': '2025-07-25 13:10:10'
        }
    ]
    
    print(f"📊 {len(test_comments)}件のコメントで処理テスト開始...")
    
    # タイムアウト監視用のフラグ
    processing_completed = threading.Event()
    response_received = False
    
    def monitor_queue():
        """キューを監視して応答を確認"""
        nonlocal response_received
        timeout = 30  # 30秒でタイムアウト
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                item = event_queue.get_nowait()
                if isinstance(item, CommentResponseReady):
                    print(f"✅ 応答受信: task_id={item.task_id}, sentences={len(item.sentences)}")
                    print(f"📝 応答内容: {item.sentences}")
                    response_received = True
                    processing_completed.set()
                    return
            except:
                pass
            time.sleep(0.1)
        
        print("⏰ タイムアウト: 30秒以内に応答が得られませんでした")
        processing_completed.set()
    
    # 監視スレッドを開始
    monitor_thread = threading.Thread(target=monitor_queue, daemon=True)
    monitor_thread.start()
    
    # コメント処理を開始
    test_start = time.time()
    command = PrepareCommentResponse(task_id='test_fix_001', comments=test_comments)
    
    print("🚀 コメント処理開始...")
    comment_handler.handle_prepare_comment_response(command)
    
    # 完了まで待機
    processing_completed.wait(timeout=35)
    
    test_duration = time.time() - test_start
    
    # 結果表示
    print("\n" + "="*50)
    print("📊 テスト結果")
    print("="*50)
    print(f"⏱️  総処理時間: {test_duration:.2f}秒")
    print(f"✅ 応答受信: {'成功' if response_received else '失敗'}")
    print(f"🎯 停止問題: {'解決' if response_received else '未解決'}")
    
    if response_received:
        print("🎉 修正成功！コメント処理が正常に完了しました")
    else:
        print("⚠️  まだ問題が残っています。ログを確認してください")
    
    return response_received

if __name__ == "__main__":
    # 環境変数設定（テストモード）
    os.environ['CHAT_TEST_MODE'] = 'true'
    
    try:
        success = test_comment_processing()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  テスト中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        sys.exit(1)