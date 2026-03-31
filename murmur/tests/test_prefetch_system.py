#!/usr/bin/env python3
"""
プリフェッチシステムのテストスクリプト
"""

import sys
import os
import time
import queue
from unittest.mock import Mock, MagicMock

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from murmur.core.event_queue import EventQueue
from murmur.state.state_manager import StateManager, SystemState
from murmur.controllers.main_controller import MainController
from murmur.core.events import (
    AppStarted, MonologueReady, SpeechPlaybackCompleted, 
    PrepareMonologue, PlaySpeech
)


class MockLogger:
    """テスト用のモックLogger"""
    def info(self, message, **kwargs):
        print(f"[MOCK LOG] INFO: {message} | {kwargs}")
    
    def log_state_change(self, old_state, new_state, **kwargs):
        print(f"[MOCK LOG] STATE: {old_state} → {new_state} | {kwargs}")


def test_prefetch_initialization():
    """プリフェッチシステムの初期化テスト"""
    print("=== プリフェッチシステム初期化テスト ===")
    
    try:
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        
        # モックLoggerを設定
        main_controller.logger = MockLogger()
        
        # 初期状態の確認
        print(f"✅ プリフェッチキューサイズ: {len(main_controller.prefetch_queue)}")
        print(f"✅ プリフェッチ中フラグ: {main_controller.is_prefetching}")
        print(f"✅ 最大プリフェッチサイズ: {main_controller.max_prefetch_size}")
        
        # プリフェッチ開始のテスト
        main_controller.start_prefetch_if_needed()
        
        # キューにPrepareMonologueコマンドが追加されているかチェック
        try:
            item = event_queue.get_nowait()
            if isinstance(item, PrepareMonologue) and item.task_id.startswith("prefetch_"):
                print(f"✅ プリフェッチコマンド生成成功: {item.task_id}")
            else:
                print(f"❌ 予期しないコマンド: {type(item)} - {item}")
                return False
        except queue.Empty:
            print("❌ プリフェッチコマンドが生成されていません")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 初期化テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prefetch_queue_management():
    """プリフェッチキュー管理のテスト"""
    print("\n=== プリフェッチキュー管理テスト ===")
    
    try:
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        main_controller.logger = MockLogger()
        
        # プリフェッチキューに独り言を追加
        test_sentences = ["これはテスト用の独り言です。", "プリフェッチシステムが正常に動作しています。"]
        main_controller.add_to_prefetch_queue("prefetch_test_1", test_sentences)
        
        print(f"✅ キューサイズ: {len(main_controller.prefetch_queue)}")
        print(f"✅ プリフェッチ中フラグ: {main_controller.is_prefetching}")
        
        # プリフェッチされた独り言を取得
        prefetched = main_controller.consume_prefetch_if_available()
        
        if prefetched:
            print(f"✅ プリフェッチ取得成功: {prefetched['task_id']}")
            print(f"✅ 文章数: {len(prefetched['sentences'])}")
            print(f"✅ 残りキューサイズ: {len(main_controller.prefetch_queue)}")
        else:
            print("❌ プリフェッチが取得できませんでした")
            return False
        
        # 空のキューから取得テスト
        empty_prefetch = main_controller.consume_prefetch_if_available()
        if empty_prefetch is None:
            print("✅ 空キューからの取得は正常にNoneを返しました")
        else:
            print("❌ 空キューから予期しない値が返されました")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ キュー管理テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_monologue_ready_handling():
    """MonologueReadyイベントの処理テスト"""
    print("\n=== MonologueReadyイベント処理テスト ===")
    
    try:
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        main_controller.logger = MockLogger()
        
        # 通常の独り言イベント
        normal_sentences = ["通常の独り言です。", "これはすぐに再生されます。"]
        normal_event = MonologueReady(task_id="normal_123", sentences=normal_sentences)
        
        # プリフェッチ用の独り言イベント
        prefetch_sentences = ["プリフェッチされた独り言です。", "これはキューに保存されます。"]
        prefetch_event = MonologueReady(task_id="prefetch_456", sentences=prefetch_sentences)
        
        # プリフェッチイベントの処理
        main_controller.handle_monologue_ready(prefetch_event)
        
        if len(main_controller.prefetch_queue) == 1:
            print("✅ プリフェッチイベントがキューに追加されました")
            queued_item = main_controller.prefetch_queue[0]
            print(f"✅ キューアイテム: {queued_item['task_id']}")
        else:
            print(f"❌ プリフェッチキューサイズが期待値と異なります: {len(main_controller.prefetch_queue)}")
            return False
        
        # 通常イベントの処理（状態管理のモック）
        state_manager.set_state(SystemState.THINKING, "normal_123", "monologue")
        
        initial_queue_size = event_queue.qsize()
        main_controller.handle_monologue_ready(normal_event)
        
        # PlaySpeechコマンドが生成されているかチェック
        if event_queue.qsize() > initial_queue_size:
            try:
                play_command = event_queue.get_nowait()
                if isinstance(play_command, PlaySpeech):
                    print(f"✅ PlaySpeechコマンド生成成功: {play_command.task_id}")
                else:
                    print(f"❌ 予期しないコマンド: {type(play_command)}")
                    return False
            except queue.Empty:
                print("❌ PlaySpeechコマンドが見つかりません")
                return False
        else:
            print("❌ 新しいコマンドが生成されませんでした")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ MonologueReadyテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_speech_completion_flow():
    """音声再生完了フローのテスト"""
    print("\n=== 音声再生完了フローテスト ===")
    
    try:
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        main_controller.logger = MockLogger()
        
        # プリフェッチキューに独り言を事前追加
        prefetch_sentences = ["事前にプリフェッチされた独り言です。", "これが優先的に使用されます。"]
        main_controller.add_to_prefetch_queue("prefetch_ready", prefetch_sentences)
        
        print(f"初期プリフェッチキューサイズ: {len(main_controller.prefetch_queue)}")
        
        # 音声再生完了イベントをシミュレート
        state_manager.set_state(SystemState.SPEAKING, "completed_task", "monologue")
        completion_event = SpeechPlaybackCompleted(task_id="completed_task")
        
        initial_queue_size = event_queue.qsize()
        main_controller.handle_speech_playback_completed(completion_event)
        
        # プリフェッチされた独り言が使用されているかチェック
        commands_generated = []
        while event_queue.qsize() > initial_queue_size:
            try:
                command = event_queue.get_nowait()
                commands_generated.append(command)
            except queue.Empty:
                break
        
        # PlaySpeechコマンドが生成され、プリフェッチされた内容が使用されているかチェック
        play_speech_found = False
        for command in commands_generated:
            if isinstance(command, PlaySpeech):
                print(f"✅ PlaySpeechコマンド生成: {command.task_id}")
                if command.task_id == "prefetch_ready":
                    print("✅ プリフェッチされた独り言が使用されました")
                    play_speech_found = True
                break
        
        if not play_speech_found:
            print("❌ プリフェッチされた独り言が使用されませんでした")
            print(f"生成されたコマンド: {[type(c).__name__ for c in commands_generated]}")
            return False
        
        # プリフェッチキューが消費されているかチェック
        if len(main_controller.prefetch_queue) == 0:
            print("✅ プリフェッチキューが正常に消費されました")
        else:
            print(f"❌ プリフェッチキューが消費されていません: {len(main_controller.prefetch_queue)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 音声再生完了フローテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_continuous_conversation_simulation():
    """連続会話シミュレーション"""
    print("\n=== 連続会話シミュレーション ===")
    
    try:
        event_queue = EventQueue()
        state_manager = StateManager()
        main_controller = MainController(event_queue, state_manager)
        main_controller.logger = MockLogger()
        
        conversation_log = []
        
        # 10回の会話サイクルをシミュレート
        for cycle in range(5):
            print(f"\n--- サイクル {cycle + 1} ---")
            
            # プリフェッチされた独り言を用意
            sentences = [f"サイクル{cycle + 1}の独り言です。", f"これは{cycle + 1}回目の発言です。"]
            prefetch_task_id = f"prefetch_cycle_{cycle}"
            
            # プリフェッチキューに追加
            main_controller.add_to_prefetch_queue(prefetch_task_id, sentences)
            
            # 音声再生完了をシミュレート
            state_manager.set_state(SystemState.SPEAKING, f"speaking_task_{cycle}", "monologue")
            completion_event = SpeechPlaybackCompleted(task_id=f"speaking_task_{cycle}")
            
            # イベント処理
            main_controller.handle_speech_playback_completed(completion_event)
            
            # 生成されたコマンドを確認
            commands_in_cycle = []
            try:
                while True:
                    command = event_queue.get_nowait()
                    commands_in_cycle.append(command)
            except queue.Empty:
                pass
            
            # PlaySpeechコマンドが生成されているかチェック
            play_speech_commands = [c for c in commands_in_cycle if isinstance(c, PlaySpeech)]
            
            if play_speech_commands:
                play_cmd = play_speech_commands[0]
                conversation_log.append(f"サイクル{cycle + 1}: {play_cmd.task_id} ({len(play_cmd.sentences)}文)")
                print(f"✅ 次の音声再生準備完了: {play_cmd.task_id}")
            else:
                conversation_log.append(f"サイクル{cycle + 1}: 音声生成なし")
                print("⚠️  音声再生コマンドが生成されませんでした")
        
        print("\n会話ログ:")
        for log in conversation_log:
            print(f"  {log}")
        
        # 継続性の評価
        successful_cycles = len([log for log in conversation_log if "音声生成なし" not in log])
        print(f"\n📈 成功した会話サイクル: {successful_cycles}/5")
        
        if successful_cycles >= 4:
            print("✅ 連続会話シミュレーション成功")
            return True
        else:
            print("❌ 連続会話シミュレーション失敗")
            return False
        
    except Exception as e:
        print(f"❌ 連続会話シミュレーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """すべてのテストを実行"""
    print("🚀 プリフェッチシステムテスト開始")
    print("=" * 60)
    
    test_results = []
    
    # 1. 初期化テスト
    test_results.append(test_prefetch_initialization())
    
    # 2. キュー管理テスト
    test_results.append(test_prefetch_queue_management())
    
    # 3. MonologueReadyハンドリングテスト
    test_results.append(test_monologue_ready_handling())
    
    # 4. 音声再生完了フローテスト
    test_results.append(test_speech_completion_flow())
    
    # 5. 連続会話シミュレーション
    test_results.append(test_continuous_conversation_simulation())
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    
    test_names = [
        "プリフェッチシステム初期化",
        "プリフェッチキュー管理",
        "MonologueReadyイベント処理",
        "音声再生完了フロー",
        "連続会話シミュレーション"
    ]
    
    for name, result in zip(test_names, test_results):
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name:25s}: {status}")
    
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n📈 合計: {passed_tests}/{total_tests} テスト成功")
    
    success = all(test_results)
    
    if success:
        print("\n🎉 すべてのテストが成功しました！")
        print("✅ プリフェッチシステムが正しく実装されています")
        print("\n⚡ 期待される効果:")
        print("   - 会話間の空白時間の大幅短縮")
        print("   - LLM応答待ち時間の並列化")
        print("   - 連続的でスムーズな会話フロー")
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