#!/usr/bin/env python3
"""
シンプルなサマリー機能テスト

MemoryManagerに実データを追加してサマリー生成をテストする
"""

import sys
import os
import time
import queue
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.core.events import DailySummaryReady, PrepareDailySummary
from murmur.handlers.daily_summary_handler import DailySummaryHandler
from memory_manager import MemoryManager
from openai_adapter import OpenAIAdapter
from config import config


def test_summary_with_data():
    """実際のデータでサマリー機能をテスト"""
    print("=== サマリー機能テスト（実データ版） ===")

    # 0. テスト用の既存サマリーファイルを削除
    summary_dir_path = config.paths.summary
    today_str = datetime.now().strftime("%Y%m%d")
    test_summary_file = os.path.join(summary_dir_path, f"summary_{today_str}.txt")
    if os.path.exists(test_summary_file):
        os.remove(test_summary_file)
        print(f"🧹 既存のテストサマリーファイルを削除しました: {test_summary_file}")

    # 1. 必要なコンポーネントを初期化
    print("🔧 コンポーネント初期化中...")

    event_queue = EventQueue()

    # OpenAIAdapter初期化（サマリー生成に必要）
    openai_adapter = OpenAIAdapter("テスト用システムプロンプト", silent_mode=False)

    # MemoryManager初期化
    memory_manager = MemoryManager(openai_adapter, event_queue=event_queue)

    # DailySummaryHandler初期化
    daily_summary_handler = DailySummaryHandler(event_queue, memory_manager)

    print("✅ 初期化完了")

    # 2. 長期記憶データを直接追加
    print("📝 長期記憶データを追加中...")

    # MemoryManagerの長期記憶に直接データを追加
    test_memories = [
        "AI VTuberとしての意識について深く考察し、視聴者との対話を通じて自分の存在について探求しました。",
        "中原中也の詩『汚れつちまつた悲しみに』について解析し、詩的言語の美しさと悲しみの表現について語りました。",
        "視聴者からの哲学的な質問に答え、AI の創造性と人間の創造性の違いについて議論しました。",
        "小説創作のプロセスについて話し、言語による世界構築の可能性について考察しました。"
    ]

    # MemoryManagerの長期記憶サマリーに直接設定
    memory_manager.long_term_summary = "\n\n".join(
        f"[{datetime.now().isoformat()}]\n{memory}" for memory in test_memories
    )
    print(f"  - 長期記憶に{len(test_memories)}件のデータを直接設定")

    # 3. 手動でサマリー生成を実行
    print("🎯 サマリー生成を手動実行...")

    # DailySummaryHandlerのtrigger_daily_summaryを直接呼び出し
    daily_summary_handler.trigger_daily_summary(reason="manual_test")

    # 4. サマリー生成完了を待機
    print("⏳ サマリー生成完了を待機中...")

    max_wait_time = 60  # 最大60秒待機
    start_time = time.time()
    found_success = False

    while time.time() - start_time < max_wait_time:
        try:
            # イベントキューをチェック
            event = event_queue.get(timeout=1.0)
            print(f"📨 イベント受信: {type(event).__name__}")

            # PrepareDailySummaryコマンドが来たら処理する
            if isinstance(event, PrepareDailySummary):
                print(f"🔄 サマリー生成コマンドを処理中: {event.task_id}")
                daily_summary_handler.handle_prepare_daily_summary(event)
                continue

            # DailySummaryReadyイベントが来たら結果確認
            if isinstance(event, DailySummaryReady):
                if event.success:
                    print("✅ サマリー生成成功!")
                    print(f"📄 ファイル: {event.file_path}")
                    print(f"📝 内容: {event.summary_text[:200]}...")
                    found_success = True
                    break
                else:
                    print(f"❌ サマリー生成失敗: {event.summary_text}")
                    break

        except queue.Empty:
            # タイムアウト時は継続
            continue

    if not found_success:
        print("⚠️ サマリー生成がタイムアウトまたは失敗しました")

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
                if file.endswith(('.md', '.txt')):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            print("📄 内容:")
                            print("="*50)
                            print(content)
                            print("="*50)
                    except Exception as e:
                        print(f"⚠️ ファイル読み込みエラー: {e}")
        else:
            print("📭 サマリーファイルが見つかりませんでした")
    else:
        print(f"📭 サマリーディレクトリが存在しません: {summary_dir}")

    print("\n🎯 サマリー機能テスト完了")


if __name__ == "__main__":
    try:
        test_summary_with_data()
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)