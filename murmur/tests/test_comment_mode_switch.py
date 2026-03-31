#!/usr/bin/env python3
"""
コメントモード切り替えテスト
テストモードと実際のYouTubeモードの動作確認
"""

import os
import sys
import time
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.services.integrated_comment_manager import IntegratedCommentManager


def test_current_mode():
    """現在の設定でのモード確認"""
    print("=== Current Comment Mode Test ===")
    
    # 環境変数を読み込み
    load_dotenv()
    
    # 現在の設定を表示
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    test_mode = os.getenv('CHAT_TEST_MODE', 'false')
    
    print(f"📺 YOUTUBE_VIDEO_ID: {video_id}")
    print(f"🧪 CHAT_TEST_MODE: {test_mode}")
    print("=" * 50)
    
    # IntegratedCommentManagerを初期化
    event_queue = EventQueue()
    comment_manager = IntegratedCommentManager(event_queue)
    
    print(f"Test Mode Detected: {comment_manager.test_mode}")
    print(f"YouTube Enabled: {comment_manager.youtube_enabled}")
    
    # 短時間実行してモードを確認
    print("\n🚀 Starting comment manager for 5 seconds...")
    comment_manager.start()
    
    # 5秒間実行
    start_time = time.time()
    while time.time() - start_time < 5:
        time.sleep(0.5)
        # イベントキューからコメントをチェック
        try:
            item = event_queue.get_nowait()
            print(f"📨 Received event: {type(item).__name__}")
            if hasattr(item, 'comments') and item.comments:
                for comment in item.comments[:2]:  # 最初の2つだけ表示
                    print(f"   💬 {comment.get('username', 'Unknown')}: {comment.get('message', '')[:50]}...")
        except:
            pass
    
    comment_manager.stop()
    print("\n✅ Test completed!")


def test_mode_switching():
    """テストモードと実際のモードの切り替えテスト"""
    print("\n=== Mode Switching Test ===")
    
    # 現在の設定を保存
    load_dotenv()
    original_test_mode = os.getenv('CHAT_TEST_MODE', 'false')
    
    print(f"Original CHAT_TEST_MODE: {original_test_mode}")
    
    # テストモード1: TEST MODE (true)
    print("\n1️⃣ Testing with CHAT_TEST_MODE=true")
    os.environ['CHAT_TEST_MODE'] = 'true'
    
    event_queue = EventQueue()
    comment_manager = IntegratedCommentManager(event_queue)
    print(f"   Test Mode: {comment_manager.test_mode}")
    print(f"   YouTube Enabled: {comment_manager.youtube_enabled}")
    
    # テストモード2: REAL MODE (false)
    print("\n2️⃣ Testing with CHAT_TEST_MODE=false")
    os.environ['CHAT_TEST_MODE'] = 'false'
    
    event_queue = EventQueue()
    comment_manager = IntegratedCommentManager(event_queue)
    print(f"   Test Mode: {comment_manager.test_mode}")
    print(f"   YouTube Enabled: {comment_manager.youtube_enabled}")
    
    # 元の設定を復元
    os.environ['CHAT_TEST_MODE'] = original_test_mode
    print(f"\n🔄 Restored CHAT_TEST_MODE to: {original_test_mode}")


def show_configuration_guide():
    """設定変更ガイドの表示"""
    print("\n=== Configuration Guide ===")
    print()
    print("📝 To switch to TEST MODE (dummy comments):")
    print("   Edit .env file:")
    print("   CHAT_TEST_MODE=true")
    print()
    print("📺 To switch to REAL MODE (YouTube live comments):")
    print("   Edit .env file:")
    print("   CHAT_TEST_MODE=false")
    print("   YOUTUBE_VIDEO_ID=your_video_id")
    print()
    print("🔄 After editing .env, restart the application")
    print()


def main():
    """メイン実行関数"""
    print("🎬 Comment Mode Switching Test")
    print("=" * 50)
    
    # 現在のモードをテスト
    test_current_mode()
    
    # モード切り替えテスト
    test_mode_switching()
    
    # 設定ガイド表示
    show_configuration_guide()
    
    print("=" * 50)
    print("✅ All tests completed!")


if __name__ == "__main__":
    main()