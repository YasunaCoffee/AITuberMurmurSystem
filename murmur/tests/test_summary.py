#!/usr/bin/env python3
"""
日次要約機能のテストスクリプト

StreamEndedイベントを手動で発行してサマリー生成をテストする
"""

import sys
import os
import time

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.core.events import StreamEnded
from murmur.handlers.daily_summary_handler import DailySummaryHandler
from memory_manager import MemoryManager
from openai_adapter import OpenAIAdapter


def test_summary_generation():
    """サマリー生成機能をテスト"""
    print("=== 日次要約機能テスト ===")
    
    # 1. 必要なコンポーネントを初期化
    print("🔧 コンポーネント初期化中...")
    
    event_queue = EventQueue()
    
    # OpenAIAdapter初期化（サマリー生成に必要）
    openai_adapter = OpenAIAdapter("テスト用システムプロンプト", silent_mode=False)
    
    # MemoryManager初期化
    memory_manager = MemoryManager(openai_adapter)
    
    # DailySummaryHandler初期化
    daily_summary_handler = DailySummaryHandler(event_queue, memory_manager)
    
    print("✅ 初期化完了")
    
    # 2. テスト用の記憶データを追加
    print("📝 テスト用記憶データを追加中...")
    
    test_conversations = [
        "AI VTuberの意識について議論しました",
        "中原中也の詩について語りました", 
        "視聴者との対話で哲学的な話題が出ました",
        "今日は小説の創作について考えていました"
    ]
    
    for conversation in test_conversations:
        memory_manager.add_utterance(conversation, "蒼月ハヤテ")
        print(f"  - 追加: {conversation}")
    
    # 3. StreamEndedイベントを手動発行
    print("🎯 StreamEndedイベントを発行...")
    
    stream_ended_event = StreamEnded(
        stream_duration_minutes=45,  # 45分の配信
        ending_reason="test"
    )
    
    # DailySummaryHandlerに直接イベントを送信
    daily_summary_handler.handle_stream_ended(stream_ended_event)
    
    # 4. サマリー生成完了を待機
    print("⏳ サマリー生成完了を待機中...")
    
    # サマリー生成は別スレッドで実行されるため、少し待機
    max_wait_time = 30  # 最大30秒待機
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            # イベントキューをチェック
            event = event_queue.get_nowait()
            print(f"📨 イベント受信: {type(event).__name__}")
            
            # PrepareDailySummaryコマンドが来たら処理する
            if hasattr(event, 'task_id') and 'daily_summary' in str(event.task_id):
                print(f"🔄 サマリー生成コマンドを処理中: {event.task_id}")
                daily_summary_handler.handle_prepare_daily_summary(event)
                continue
            
            # DailySummaryReadyイベントが来たら成功
            if hasattr(event, 'success') and type(event).__name__ == 'DailySummaryReady':
                if event.success:
                    print(f"✅ サマリー生成成功!")
                    print(f"📄 ファイル: {event.file_path}")
                    print(f"📝 内容: {event.summary_text[:200]}...")
                else:
                    print(f"❌ サマリー生成失敗: {event.summary_text}")
                break
                
        except:
            # キューが空の場合は少し待機
            time.sleep(0.1)
            continue
    else:
        print("⚠️ サマリー生成がタイムアウトしました")
    
    # 5. 生成されたファイルを確認
    summary_dir = daily_summary_handler.summary_dir
    print(f"📁 サマリーディレクトリ: {summary_dir}")
    
    if os.path.exists(summary_dir):
        files = os.listdir(summary_dir)
        if files:
            print("📋 生成されたファイル:")
            for file in sorted(files):
                file_path = os.path.join(summary_dir, file)
                file_size = os.path.getsize(file_path)
                print(f"  - {file} ({file_size} bytes)")
                
                # 最新のファイル内容を表示
                if file.endswith('.md'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        print(f"📄 内容（最初の300文字）:")
                        print(content[:300])
                        if len(content) > 300:
                            print("...")
        else:
            print("📭 サマリーファイルが見つかりませんでした")
    else:
        print(f"📭 サマリーディレクトリが存在しません: {summary_dir}")
    
    print("\n🎯 日次要約機能テスト完了")


if __name__ == "__main__":
    try:
        test_summary_generation()
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)