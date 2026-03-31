#!/usr/bin/env python3
"""
終了挨拶機能の単体テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.handlers.greeting_handler import GreetingHandler
from murmur.core.event_queue import EventQueue
from murmur.core.events import PrepareEndingGreeting


def test_ending_greeting():
    """終了挨拶のテスト"""
    print("=== 終了挨拶テスト ===")
    
    try:
        # コンポーネント初期化
        event_queue = EventQueue()
        greeting_handler = GreetingHandler(event_queue)
        
        print("✅ GreetingHandler初期化完了")
        
        # 終了挨拶コマンドを作成
        ending_command = PrepareEndingGreeting(
            task_id="test_ending_001",
            bridge_text="今日のテストセッションはここまでとしましょう。",
            stream_summary="テスト機能について詳しく議論できました。"
        )
        
        print(f"📝 終了挨拶コマンド作成: {ending_command}")
        
        # 終了挨拶処理を実行
        greeting_handler.handle_prepare_ending_greeting(ending_command)
        
        print("✅ 終了挨拶処理開始")
        
        # 結果待機（最大10秒）
        import time
        for i in range(10):
            try:
                event = event_queue.get_nowait()
                print(f"📨 イベント受信: {type(event).__name__}")
                if hasattr(event, 'sentences'):
                    print(f"📝 生成された挨拶:")
                    for j, sentence in enumerate(event.sentences, 1):
                        print(f"  {j}. {sentence}")
                break
            except:
                time.sleep(1)
                print(f"⏳ 待機中... ({i+1}/10秒)")
        else:
            print("❌ タイムアウト: 終了挨拶が生成されませんでした")
            return False
        
        print("✅ テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ending_greeting()
    print(f"\n{'🎉 テスト成功' if success else '❌ テスト失敗'}")
    exit(0 if success else 1)