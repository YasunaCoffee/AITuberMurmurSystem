#!/usr/bin/env python3
"""
配信終了後サマリー生成システムのテスト
"""

import sys
import os
import time
import threading

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.handlers.daily_summary_handler import DailySummaryHandler
from murmur.core.events import StreamEnded, DailySummaryReady
from app.memory_manager import MemoryManager

print("=== 配信終了後サマリー生成テスト ===")

def test_post_stream_summary():
    """配信終了後のサマリー生成テスト"""
    
    # システム初期化
    event_queue = EventQueue()
    
    # MemoryManagerを初期化（サマリー生成に必要）
    try:
        from app.openai_adapter import OpenAIAdapter
        system_prompt = "システムプロンプト"
        openai_adapter = OpenAIAdapter(system_prompt, silent_mode=True)
        memory_manager = MemoryManager(openai_adapter)
        print("✅ MemoryManager初期化成功")
    except Exception as e:
        print(f"⚠️ MemoryManager初期化失敗: {e}")
        memory_manager = None
    
    # DailySummaryHandler初期化
    summary_handler = DailySummaryHandler(event_queue, memory_manager)
    
    # 配信終了イベントをシミュレート
    stream_end_event = StreamEnded(
        stream_duration_minutes=45,
        ending_reason="normal"
    )
    
    print("📺 配信終了をシミュレート...")
    print(f"   配信時間: {stream_end_event.stream_duration_minutes}分")
    print(f"   終了理由: {stream_end_event.ending_reason}")
    
    # 応答監視
    summary_completed = False
    summary_result = None
    processing_completed = threading.Event()
    
    def monitor_summary():
        nonlocal summary_completed, summary_result
        timeout = 60  # 60秒でタイムアウト
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                item = event_queue.get_nowait()
                if isinstance(item, DailySummaryReady):
                    summary_result = item
                    summary_completed = True
                    processing_completed.set()
                    return
            except:
                pass
            time.sleep(0.5)
        
        print("⏰ サマリー生成タイムアウト")
        processing_completed.set()
    
    # 監視開始
    monitor_thread = threading.Thread(target=monitor_summary, daemon=True)
    monitor_thread.start()
    
    # 配信終了イベントを処理
    test_start = time.time()
    summary_handler.handle_stream_ended(stream_end_event)
    
    # 完了待機
    processing_completed.wait()
    test_duration = time.time() - test_start
    
    # 結果表示
    print("\n" + "="*60)
    print("📊 配信終了後サマリーテスト結果")
    print("="*60)
    print(f"⏱️  処理時間: {test_duration:.2f}秒")
    print(f"✅ サマリー生成: {'成功' if summary_completed else '失敗'}")
    
    # ハンドラーの状態確認
    status = summary_handler.get_summary_status()
    print(f"\n📋 サマリーハンドラー状態:")
    print(f"   配信終了後生成: {'有効' if status['post_stream_enabled'] else '無効'}")
    print(f"   今日のサマリー: {'存在' if status['today_summary_exists'] else '未作成'}")
    print(f"   最終生成日: {status['last_summary_date'] or '未生成'}")
    print(f"   保存ディレクトリ: {status['summary_directory']}")
    
    if summary_completed and summary_result:
        print(f"\n📄 サマリー結果:")
        print(f"   成功: {'はい' if summary_result.success else 'いいえ'}")
        if summary_result.file_path:
            print(f"   ファイルパス: {summary_result.file_path}")
        print(f"   内容プレビュー: {summary_result.summary_text[:200]}...")
    
    # システムの改善点を確認
    improvements = []
    if summary_completed:
        improvements.append("✅ 配信終了後の自動サマリー生成")
    else:
        improvements.append("❌ サマリー生成失敗")
        
    if test_duration < 30:
        improvements.append("✅ 適切な処理時間")
    else:
        improvements.append("⚠️ 処理時間が長い")
        
    print(f"\n📈 システム評価:")
    for improvement in improvements:
        print(f"   {improvement}")
    
    return summary_completed

if __name__ == "__main__":
    # 環境変数設定
    os.environ['CHAT_TEST_MODE'] = 'true'
    
    try:
        success = test_post_stream_summary()
        print(f"\n🎯 総合評価: {'成功' if success else '要改善'}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  テスト中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)