#!/usr/bin/env python3
"""
pytchatのAuthor属性を調査するデバッグスクリプト
"""

import os
from dotenv import load_dotenv
load_dotenv()

try:
    import pytchat
    
    video_id = os.getenv('YOUTUBE_VIDEO_ID')
    if not video_id:
        print("YOUTUBE_VIDEO_ID環境変数が設定されていません")
        exit(1)
    
    print(f"pytchatバージョン: {pytchat.__version__}")
    print(f"ビデオID: {video_id}")
    
    # YouTubeチャットに接続
    chat = pytchat.create(video_id=video_id)
    
    if not chat.is_alive():
        print("チャットが利用できません（配信が停止中の可能性）")
        exit(1)
    
    print("チャットに接続成功。コメントを監視中...")
    
    # 10秒間だけ監視
    import time
    start_time = time.time()
    
    while time.time() - start_time < 10:
        try:
            for comment in chat.get().sync_items():
                print(f"\n=== コメント発見 ===")
                print(f"メッセージ: {comment.message}")
                print(f"ユーザー名: {comment.author.name}")
                
                # Authorオブジェクトの属性を調査
                author = comment.author
                print(f"\nAuthor属性一覧:")
                for attr in dir(author):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(author, attr)
                            if not callable(value):
                                print(f"  {attr}: {value}")
                        except Exception as e:
                            print(f"  {attr}: エラー - {e}")
                
                chat.terminate()
                exit(0)
                
            time.sleep(1)
        except Exception as e:
            print(f"エラー: {e}")
            break
    
    chat.terminate()
    print("コメントが見つかりませんでした")
    
except ImportError:
    print("pytchatがインストールされていません")
except Exception as e:
    print(f"エラーが発生しました: {e}")