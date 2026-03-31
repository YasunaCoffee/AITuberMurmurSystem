#!/usr/bin/env python3
"""
テストモード設定のデバッグスクリプト
実際の設定値とシステムの動作を詳細確認
"""

import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.services.integrated_comment_manager import IntegratedCommentManager


def debug_environment():
    """環境変数の詳細デバッグ"""
    print("=== Environment Debug ===")
    
    # 1. .envファイルの内容を直接確認
    print("1. .env file content:")
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'CHAT_TEST_MODE' in line:
                print(f"   Line {i}: {line.strip()}")
    except Exception as e:
        print(f"   Error reading .env: {e}")
    
    # 2. 環境変数読み込み前の状態
    print("\n2. Before load_dotenv():")
    print(f"   os.environ.get('CHAT_TEST_MODE'): {os.environ.get('CHAT_TEST_MODE', 'NOT_SET')}")
    
    # 3. dotenvで読み込み
    load_dotenv()
    print("\n3. After load_dotenv():")
    print(f"   os.getenv('CHAT_TEST_MODE'): {os.getenv('CHAT_TEST_MODE', 'NOT_SET')}")
    print(f"   os.environ.get('CHAT_TEST_MODE'): {os.environ.get('CHAT_TEST_MODE', 'NOT_SET')}")
    
    # 4. 文字列比較のテスト
    test_mode_str = os.getenv('CHAT_TEST_MODE', 'false')
    print(f"\n4. String comparison test:")
    print(f"   Raw value: '{test_mode_str}'")
    print(f"   Lower: '{test_mode_str.lower()}'")
    print(f"   test_mode_str.lower() == 'true': {test_mode_str.lower() == 'true'}")
    print(f"   test_mode_str.lower() == 'false': {test_mode_str.lower() == 'false'}")
    
    # 5. IntegratedCommentManagerでの判定
    print("\n5. IntegratedCommentManager initialization:")
    event_queue = EventQueue()
    comment_manager = IntegratedCommentManager(event_queue)
    
    print(f"   comment_manager.test_mode: {comment_manager.test_mode}")
    print(f"   comment_manager.youtube_enabled: {comment_manager.youtube_enabled}")
    print(f"   comment_manager.video_id: {comment_manager.video_id}")


def test_comment_fetching():
    """実際のコメント取得をテスト"""
    print("\n=== Comment Fetching Test ===")
    
    load_dotenv()
    event_queue = EventQueue()
    comment_manager = IntegratedCommentManager(event_queue)
    
    print(f"Test mode: {comment_manager.test_mode}")
    print(f"YouTube enabled: {comment_manager.youtube_enabled}")
    
    # _fetch_new_commentsを直接呼び出し
    print("\nCalling _fetch_new_comments() directly:")
    try:
        comments = comment_manager._fetch_new_comments()
        if comments:
            print(f"Retrieved {len(comments)} comments:")
            for comment in comments[:2]:  # 最初の2つだけ表示
                print(f"   - {comment.get('username', 'Unknown')}: {comment.get('message', '')[:50]}...")
        else:
            print("No comments retrieved")
    except Exception as e:
        print(f"Error: {e}")


def check_youtube_connection():
    """YouTube接続状態の確認"""
    print("\n=== YouTube Connection Check ===")
    
    load_dotenv()
    
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    print(f"Video ID: {video_id}")
    
    try:
        import pytchat
        print("pytchat library: Available")
        
        if video_id:
            try:
                chat = pytchat.create(video_id=video_id)
                print(f"YouTube connection: {chat.is_alive()}")
                chat.terminate()
            except Exception as e:
                print(f"YouTube connection error: {e}")
        else:
            print("No video ID provided")
            
    except ImportError:
        print("pytchat library: Not available")


def main():
    """メイン実行"""
    print("🔍 Test Mode Debug Analysis")
    print("=" * 50)
    
    debug_environment()
    test_comment_fetching()
    check_youtube_connection()
    
    print("\n" + "=" * 50)
    print("Debug analysis completed")


if __name__ == "__main__":
    main()