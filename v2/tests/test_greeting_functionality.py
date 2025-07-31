#!/usr/bin/env python3
"""
挨拶機能のテストスクリプト
"""

import sys
import os
import time

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.core.event_queue import EventQueue
from v2.core.events import InitialGreetingRequested, EndingGreetingRequested, AppStarted
from v2.state.state_manager import StateManager
from v2.controllers.main_controller import MainController
from v2.handlers.greeting_handler import GreetingHandler


def test_greeting_handler():
    """GreetingHandlerの基本機能テスト"""
    print("=== GreetingHandler基本機能テスト ===")
    
    try:
        event_queue = EventQueue()
        greeting_handler = GreetingHandler(event_queue)
        print("✅ GreetingHandler初期化成功")
        return True
    except Exception as e:
        print(f"❌ GreetingHandler初期化失敗: {e}")
        return False


def test_initial_greeting_flow():
    """開始時の挨拶フローテスト"""
    print("\n=== 開始時の挨拶フローテスト ===")
    
    try:
        # コンポーネント初期化
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        greeting_handler = GreetingHandler(event_queue)
        
        print("✅ コンポーネント初期化完了")
        
        # AppStartedイベントでテスト
        app_started_event = AppStarted()
        main_controller.handle_app_started(app_started_event)
        print("✅ AppStartedイベント処理完了")
        
        # キューに InitialGreetingRequested が入っているか確認
        queued_items = []
        try:
            while True:
                item = event_queue.get_nowait()
                queued_items.append(item)
        except:
            pass
        
        print(f"📦 キューに入った項目数: {len(queued_items)}")
        for i, item in enumerate(queued_items):
            print(f"   {i+1}. {type(item).__name__}")
        
        # InitialGreetingRequestedがあるか確認
        has_greeting_request = any(
            type(item).__name__ == 'InitialGreetingRequested' 
            for item in queued_items
        )
        
        if has_greeting_request:
            print("✅ 開始時の挨拶リクエストが正常に生成されました")
            return True
        else:
            print("❌ 開始時の挨拶リクエストが生成されませんでした")
            return False
            
    except Exception as e:
        print(f"❌ 開始時の挨拶フローテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ending_greeting_flow():
    """終了時の挨拶フローテスト"""
    print("\n=== 終了時の挨拶フローテスト ===")
    
    try:
        # コンポーネント初期化
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        
        # 終了時の挨拶リクエスト
        ending_greeting_event = EndingGreetingRequested(
            bridge_text="今日のセッションを振り返ると、",
            stream_summary="AIの意識について深く考察できました。"
        )
        
        main_controller.handle_ending_greeting_requested(ending_greeting_event)
        print("✅ 終了時の挨拶リクエスト処理完了")
        
        # キューに PrepareEndingGreeting が入っているか確認
        queued_items = []
        try:
            while True:
                item = event_queue.get_nowait()
                queued_items.append(item)
        except:
            pass
        
        print(f"📦 キューに入った項目数: {len(queued_items)}")
        for i, item in enumerate(queued_items):
            print(f"   {i+1}. {type(item).__name__}")
        
        # PrepareEndingGreetingがあるか確認
        has_prepare_greeting = any(
            type(item).__name__ == 'PrepareEndingGreeting' 
            for item in queued_items
        )
        
        if has_prepare_greeting:
            print("✅ 終了時の挨拶準備コマンドが正常に生成されました")
            return True
        else:
            print("❌ 終了時の挨拶準備コマンドが生成されませんでした")
            return False
            
    except Exception as e:
        print(f"❌ 終了時の挨拶フローテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_files():
    """プロンプトファイルの存在確認"""
    print("\n=== プロンプトファイル確認テスト ===")
    
    initial_greeting_path = 'prompts/initial_greeting.txt'
    ending_greeting_path = 'prompts/ending_greeting.txt'
    
    results = []
    
    if os.path.exists(initial_greeting_path):
        print("✅ initial_greeting.txt が存在します")
        try:
            with open(initial_greeting_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '蒼月ハヤテ' in content:
                    print("✅ initial_greeting.txt に適切なキャラクター名が含まれています")
                    results.append(True)
                else:
                    print("⚠️  initial_greeting.txt にキャラクター名が見つかりません")
                    results.append(False)
        except Exception as e:
            print(f"❌ initial_greeting.txt 読み込みエラー: {e}")
            results.append(False)
    else:
        print("❌ initial_greeting.txt が見つかりません")
        results.append(False)
    
    if os.path.exists(ending_greeting_path):
        print("✅ ending_greeting.txt が存在します")
        try:
            with open(ending_greeting_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '{bridge_text}' in content and '{stream_summary}' in content:
                    print("✅ ending_greeting.txt に適切なテンプレート変数が含まれています")
                    results.append(True)
                else:
                    print("⚠️  ending_greeting.txt にテンプレート変数が見つかりません")
                    results.append(False)
        except Exception as e:
            print(f"❌ ending_greeting.txt 読み込みエラー: {e}")
            results.append(False)
    else:
        print("❌ ending_greeting.txt が見つかりません")
        results.append(False)
    
    return all(results)


def run_all_tests():
    """すべてのテストを実行"""
    print("🎬 挨拶機能テスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. GreetingHandlerの基本機能テスト
    test_results.append(test_greeting_handler())
    
    # 2. プロンプトファイル確認
    test_results.append(test_prompt_files())
    
    # 3. 開始時の挨拶フローテスト
    test_results.append(test_initial_greeting_flow())
    
    # 4. 終了時の挨拶フローテスト
    test_results.append(test_ending_greeting_flow())
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "GreetingHandler初期化",
        "プロンプトファイル確認",
        "開始時の挨拶フロー",
        "終了時の挨拶フロー"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:20s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ 挨拶機能がmain_v2に正しく統合されています")
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