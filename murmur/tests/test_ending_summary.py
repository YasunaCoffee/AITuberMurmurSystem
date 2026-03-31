#!/usr/bin/env python3
"""
締めの挨拶完了時の日次要約機能テストスクリプト
"""

import sys
import os
import time

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from murmur.core.event_queue import EventQueue
from murmur.core.events import (
    EndingGreetingRequested, EndingGreetingReady, SpeechPlaybackCompleted,
    PrepareDailySummary, DailySummaryReady, PrepareEndingGreeting
)
from murmur.controllers.main_controller import MainController
from murmur.state.state_manager import StateManager, SystemState
from murmur.handlers.daily_summary_handler import DailySummaryHandler
from murmur.handlers.greeting_handler import GreetingHandler
from memory_manager import MemoryManager
from openai_adapter import OpenAIAdapter
from config import config


def test_ending_greeting_to_summary_flow():
    """締めの挨拶から日次要約までのフローテスト"""
    print("=== 締めの挨拶→日次要約フローテスト ===")
    
    try:
        # コンポーネント初期化
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        
        # MemoryManagerを初期化
        system_prompt_path = os.path.join(config.paths.prompts, "persona_prompt.txt")
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        openai_adapter = OpenAIAdapter(system_prompt, silent_mode=False)
        memory_manager = MemoryManager(openai_adapter)
        
        # DailySummaryHandlerを初期化
        daily_summary_handler = DailySummaryHandler(event_queue, memory_manager)
        greeting_handler = GreetingHandler(event_queue)
        
        print("✅ コンポーネント初期化完了")
        
        # コマンドハンドラーのマッピング
        command_handlers = {
            PrepareEndingGreeting: greeting_handler.handle_prepare_ending_greeting,
            PrepareDailySummary: daily_summary_handler.handle_prepare_daily_summary,
        }
        
        # 1. 終了時の挨拶を要求
        print("📢 終了時の挨拶を要求します...")
        ending_greeting_event = EndingGreetingRequested(
            bridge_text="それでは、今日の思考実験はここまでとしましょう。",
            stream_summary="本日も様々な哲学的問いについて考えを深めることができました。"
        )
        
        main_controller.handle_ending_greeting_requested(ending_greeting_event)
        print("✅ 終了時の挨拶要求を処理しました")
        
        # 2. PrepareEndingGreetingコマンドを処理
        item = event_queue.get()
        if isinstance(item, PrepareEndingGreeting):
            print(f"📋 PrepareEndingGreetingコマンドを受信: {item.task_id}")
            
            # 手動でコマンドを処理（通常はmainループで処理される）
            command_handlers[PrepareEndingGreeting](item)
            print("✅ 終了時の挨拶の準備を開始しました")
            
            # 3. EndingGreetingReadyイベントを待機・処理
            timeout = 10  # 10秒で待機
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    next_item = event_queue.get_nowait()
                    if isinstance(next_item, EndingGreetingReady):
                        print(f"🎤 終了時の挨拶が準備完了: {next_item.task_id}")
                        
                        # MainControllerで処理
                        main_controller.handle_ending_greeting_ready(next_item)
                        print("✅ 終了時の挨拶の再生を開始しました")
                        
                        # 4. 音声再生完了をシミュレート
                        print("🔊 音声再生完了をシミュレートします...")
                        playback_completed = SpeechPlaybackCompleted(task_id=next_item.task_id)
                        main_controller.handle_speech_playback_completed(playback_completed)
                        print("✅ 音声再生完了を処理しました")
                        
                        # 5. PrepareDailySummaryコマンドが生成されているかチェック
                        summary_timeout = 5
                        summary_start = time.time()
                        
                        while time.time() - summary_start < summary_timeout:
                            try:
                                summary_item = event_queue.get_nowait()
                                if isinstance(summary_item, PrepareDailySummary):
                                    print(f"📊 日次要約コマンドが生成されました: {summary_item.task_id}")
                                    
                                    # 日次要約コマンドを処理
                                    command_handlers[PrepareDailySummary](summary_item)
                                    print("✅ 日次要約の処理を開始しました")
                                    
                                    # 6. DailySummaryReadyイベントを待機
                                    result_timeout = 30
                                    result_start = time.time()
                                    
                                    while time.time() - result_start < result_timeout:
                                        try:
                                            result_item = event_queue.get_nowait()
                                            if isinstance(result_item, DailySummaryReady):
                                                if result_item.success:
                                                    print(f"🎉 日次要約が正常に生成されました！")
                                                    print(f"📄 ファイル: {result_item.file_path}")
                                                    print(f"📝 内容（先頭100文字）: {result_item.summary_text[:100]}...")
                                                    
                                                    # MainControllerで処理
                                                    main_controller.handle_daily_summary_ready(result_item)
                                                    return True
                                                else:
                                                    print(f"❌ 日次要約の生成に失敗: {result_item.summary_text}")
                                                    return False
                                        except:
                                            time.sleep(0.1)
                                    
                                    print("⏰ 日次要約の結果待機がタイムアウトしました")
                                    return False
                            except:
                                time.sleep(0.1)
                        
                        print("⏰ 日次要約コマンドの待機がタイムアウトしました")
                        return False
                except:
                    time.sleep(0.1)
            
            print("⏰ EndingGreetingReadyイベントの待機がタイムアウトしました")
            return False
        else:
            print(f"❌ 予期しないアイテムを受信: {type(item).__name__}")
            return False
            
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_manager_task_type():
    """StateManagerのtask_type追跡テスト"""
    print("\n=== StateManagerのtask_type追跡テスト ===")
    
    try:
        state_manager = StateManager()
        
        # 初期状態確認
        print(f"📊 初期状態: {state_manager.current_state.value}")
        print(f"📋 初期task_type: {state_manager.current_task_type}")
        
        # ending_greetingタスクをセット
        task_id = "test_ending_greeting_123"
        state_manager.set_state(SystemState.THINKING, task_id, "ending_greeting")
        
        print(f"✅ THINKING状態に変更: task_type={state_manager.current_task_type}")
        
        # SPEAKING状態に変更
        state_manager.set_state(SystemState.SPEAKING, task_id, "ending_greeting")
        
        print(f"✅ SPEAKING状態に変更: task_type={state_manager.current_task_type}")
        
        # task_typeが正しく追跡されているか確認
        if state_manager.current_task_type == "ending_greeting":
            print("✅ task_typeが正しく追跡されています")
            return True
        else:
            print(f"❌ task_typeの追跡に失敗: 期待値='ending_greeting', 実際値='{state_manager.current_task_type}'")
            return False
            
    except Exception as e:
        print(f"❌ StateManagerテストエラー: {e}")
        return False


def run_all_tests():
    """すべてのテストを実行"""
    print("🎬 締めの挨拶→日次要約機能テスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. StateManagerのtask_type追跡テスト
    test_results.append(test_state_manager_task_type())
    
    # 2. 締めの挨拶→日次要約フローテスト
    test_results.append(test_ending_greeting_to_summary_flow())
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "StateManager task_type追跡",
        "締めの挨拶→日次要約フロー"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:25s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ 締めの挨拶完了時の日次要約機能が正しく動作しています")
    else:
        print("\n⚠️  一部のテストが失敗しました")
        print("上記の失敗項目を確認してください")
    
    return success


if __name__ == "__main__":
    try:
        success = run_all_tests()
        print(f"\n🏁 {'テスト成功！' if success else 'テスト失敗'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)