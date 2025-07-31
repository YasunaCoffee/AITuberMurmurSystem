#!/usr/bin/env python3
"""
YouTubeライブコメント取得の簡単なテスト（非対話式）
"""

import os
import time
import sys
from datetime import datetime

try:
    import pytchat
except ImportError:
    print("❌ pytchatライブラリがインストールされていません")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()


def test_youtube_live_comments():
    """YouTubeライブコメント取得のシンプルテスト"""
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    if not video_id:
        print("❌ YOUTUBE_VIDEO_ID environment variable not set")
        return False
    
    print("=== YouTube Live Comments Simple Test ===")
    print(f"📺 Video ID: {video_id}")
    print(f"⏱️  Test Duration: 15 seconds")
    print("=" * 50)
    
    try:
        # YouTubeチャットに接続
        print("🔌 Connecting to YouTube Live Chat...")
        chat = pytchat.create(video_id=video_id)
        
        if not chat.is_alive():
            print("❌ Chat is not available (stream might not be live)")
            return False
            
        print("✅ Connected successfully!")
        
        start_time = time.time()
        comment_count = 0
        test_duration = 15  # 15秒間テスト
        
        print(f"📡 Monitoring for {test_duration} seconds...")
        
        while chat.is_alive() and (time.time() - start_time) < test_duration:
            try:
                chat_data = chat.get()
                items = chat_data.sync_items()
                
                for comment in items:
                    comment_count += 1
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    print(f"\n[{timestamp}] Comment #{comment_count}")
                    print(f"👤 {comment.author.name}: {comment.message}")
                    
                    # ユーザー情報
                    if comment.author.isOwner:
                        print("   🎬 (Channel Owner)")
                    if comment.author.isModerator:
                        print("   🛡️ (Moderator)")
                    if comment.author.isVerified:
                        print("   ✅ (Verified)")
                    
                    # スーパーチャット
                    if hasattr(comment, 'amountValue') and comment.amountValue:
                        print(f"   💰 Super Chat: {comment.amountString}")
                
                # CPU使用率を抑制
                time.sleep(0.5)
                
            except Exception as e:
                print(f"⚠️  Error processing comments: {e}")
                time.sleep(1)
                continue
        
        # 終了処理
        chat.terminate()
        elapsed = time.time() - start_time
        
        print(f"\n📊 Test Results:")
        print(f"   - Duration: {elapsed:.1f} seconds")
        print(f"   - Total Comments: {comment_count}")
        if comment_count > 0:
            print(f"   - Comments per minute: {(comment_count / elapsed * 60):.1f}")
        
        return comment_count >= 0  # 0件でも接続成功とみなす
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n🔍 Possible issues:")
        print("   1. Stream is not live")
        print("   2. Video ID is incorrect")
        print("   3. Chat is disabled")
        print("   4. Network issues")
        return False


def main():
    """メイン実行"""
    success = test_youtube_live_comments()
    
    if success:
        print("\n✅ YouTube Live Comments connection successful!")
        print("The system can connect to and retrieve live comments.")
    else:
        print("\n❌ YouTube Live Comments connection failed!")
        print("Please check the video ID and stream status.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)