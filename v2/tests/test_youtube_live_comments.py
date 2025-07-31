#!/usr/bin/env python3
"""
YouTubeライブコメント取得のテスト用スクリプト
実際のライブ配信に接続してコメントを取得・表示します
"""

import os
import time
import sys
from datetime import datetime
from typing import Optional

try:
    import pytchat
except ImportError:
    print("❌ pytchatライブラリがインストールされていません")
    print("インストール: pip install pytchat")
    sys.exit(1)

# 環境変数から設定を読み込み
from dotenv import load_dotenv
load_dotenv()


def test_youtube_connection(video_id: str, test_duration: int = 60):
    """
    YouTubeライブコメント取得のテスト
    
    Args:
        video_id: YouTubeビデオID
        test_duration: テスト実行時間（秒）
    """
    print("=== YouTube Live Comments Test ===")
    print(f"📺 Video ID: {video_id}")
    print(f"⏱️  Test Duration: {test_duration} seconds")
    print("=" * 50)
    
    try:
        # YouTubeチャットに接続
        print("🔌 Connecting to YouTube Live Chat...")
        chat = pytchat.create(video_id=video_id)
        print("✅ Connected successfully!")
        
        start_time = time.time()
        comment_count = 0
        
        while chat.is_alive() and (time.time() - start_time) < test_duration:
            try:
                for comment in chat.get().sync_items():
                    comment_count += 1
                    
                    # コメント情報の表示
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\n[{timestamp}] Comment #{comment_count}")
                    print(f"👤 User: {comment.author.name}")
                    print(f"💬 Message: {comment.message}")
                    print(f"🆔 Message ID: {comment.id}")
                    print(f"📅 DateTime: {comment.datetime}")
                    
                    # ユーザー情報
                    author = comment.author
                    user_info = []
                    if author.isOwner:
                        user_info.append("🎬 Owner")
                    if author.isModerator:
                        user_info.append("🛡️ Moderator")
                    if author.isVerified:
                        user_info.append("✅ Verified")
                    
                    if user_info:
                        print(f"🏷️  Status: {', '.join(user_info)}")
                    
                    # スーパーチャット情報
                    if hasattr(comment, 'amountValue') and comment.amountValue:
                        print(f"💰 Super Chat: {comment.amountString}")
                    
                    print("-" * 30)
                
                # 少し待機してCPU使用率を抑制
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n⏹️  Test interrupted by user")
                break
            except Exception as e:
                print(f"⚠️  Error processing comments: {e}")
                time.sleep(2)
                continue
        
        # 接続終了
        chat.terminate()
        
        # 結果サマリー
        elapsed_time = time.time() - start_time
        print(f"\n📊 Test Results:")
        print(f"   - Total Comments: {comment_count}")
        print(f"   - Test Duration: {elapsed_time:.1f} seconds")
        print(f"   - Comments per minute: {(comment_count / elapsed_time * 60):.1f}")
        
        return comment_count > 0
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔍 Troubleshooting:")
        print("   1. ライブ配信が実行中か確認してください")
        print("   2. ビデオIDが正しいか確認してください")
        print("   3. チャット機能が有効か確認してください")
        print("   4. インターネット接続を確認してください")
        return False


def get_video_info(video_id: str) -> Optional[dict]:
    """ビデオ情報を取得（可能な場合）"""
    try:
        # pytchatでビデオの基本情報を取得
        chat = pytchat.create(video_id=video_id)
        if chat.is_alive():
            info = {
                "video_id": video_id,
                "status": "live",
                "chat_available": True
            }
            chat.terminate()
            return info
        else:
            return {
                "video_id": video_id,
                "status": "not_live",
                "chat_available": False
            }
    except Exception as e:
        return {
            "video_id": video_id,
            "status": "error",
            "error": str(e),
            "chat_available": False
        }


def main():
    """メイン実行関数"""
    print("🎬 YouTube Live Comments Connection Test")
    print("=" * 50)
    
    # 環境変数からビデオIDを取得
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    if not video_id:
        print("❌ YOUTUBE_VIDEO_ID environment variable not set")
        print("Please set it in your .env file")
        return
    
    print(f"📺 Target Video ID: {video_id}")
    
    # ビデオ情報の確認
    print("\n🔍 Checking video status...")
    video_info = get_video_info(video_id)
    print(f"Video Info: {video_info}")
    
    if not video_info.get('chat_available', False):
        print("⚠️  Chat is not available for this video")
        print("This might be because:")
        print("   - The stream is not live")
        print("   - Chat is disabled")
        print("   - The video ID is incorrect")
        
        # テストモードの提案
        print("\n💡 Would you like to continue anyway? (y/n): ", end="")
        response = input().lower().strip()
        if response != 'y':
            print("Test cancelled.")
            return
    
    # テスト実行時間の設定
    print(f"\n⏱️  How long should we test? (default: 60 seconds): ", end="")
    duration_input = input().strip()
    
    try:
        test_duration = int(duration_input) if duration_input else 60
    except ValueError:
        test_duration = 60
    
    print(f"Testing for {test_duration} seconds...")
    print("\n🚀 Starting YouTube Live Comments Test...")
    print("Press Ctrl+C to stop early\n")
    
    # テスト実行
    success = test_youtube_connection(video_id, test_duration)
    
    if success:
        print("\n✅ Test completed successfully!")
        print("YouTube Live Comments integration is working correctly.")
    else:
        print("\n❌ Test failed or no comments received")
        print("Please check the troubleshooting information above.")


if __name__ == "__main__":
    main()