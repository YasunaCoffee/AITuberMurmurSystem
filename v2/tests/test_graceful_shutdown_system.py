#!/usr/bin/env python3
"""
優雅なシャットダウンシーケンステスト
終了挨拶のタイムアウト問題を詳しく調査
"""

import sys
import os
import time
import threading
from unittest.mock import patch, MagicMock

# パスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from v2.core.event_queue import EventQueue
from v2.core.events import PlaySpeech, PrepareEndingGreeting
from v2.services.audio_manager import AudioManager
from v2.handlers.greeting_handler import GreetingHandler
from v2.core.test_mode import test_mode_manager, TestMode
import queue


def test_ending_greeting_with_timeout():
    """終了挨拶のタイムアウト問題をテスト"""
    print("=== 終了挨拶タイムアウト問題調査 ===")
    
    try:
        # テストモード設定
        test_mode_manager.set_mode(TestMode.UNIT)
        
        # コンポーネント初期化
        event_queue = EventQueue()
        audio_manager = AudioManager(event_queue)
        greeting_handler = GreetingHandler(event_queue)
        
        print("✅ コンポーネント初期化完了")
        
        # 終了挨拶コマンドを準備
        ending_command = PrepareEndingGreeting(
            task_id="shutdown_test_001",
            bridge_text="それでは、テストセッションはここまでとしましょう。",
            stream_summary="テスト機能について詳しく議論できました。"
        )
        
        print(f"📝 終了挨拶コマンド準備完了: {ending_command}")
        
        # 同期キューを作成
        sync_queue = queue.Queue()
        
        # _generate_ending_comment 相当の処理を手動で実行
        print("🚀 終了挨拶生成開始...")
        
        # Step 1: 終了挨拶プロンプトの構築
        try:
            with open('prompts/ending_greeting.txt', 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            print("✅ プロンプトファイル読み込み完了")
        except Exception as e:
            print(f"❌ プロンプトファイル読み込みエラー: {e}")
            return False
        
        # Step 2: プロンプト生成と LLM 呼び出し
        print("📡 LLM API呼び出し中...")
        start_time = time.time()
        
        try:
            ending_greeting_prompt = prompt_template.format(
                bridge_text=ending_command.bridge_text,
                stream_summary=ending_command.stream_summary
            )
            
            final_prompt = greeting_handler.master_prompt_manager.wrap_task_with_master_prompt(
                specific_task_prompt=ending_greeting_prompt,
                current_mode="ending_greeting"
            )
            
            response = greeting_handler.openai_adapter.create_chat_for_response(final_prompt)
            llm_time = time.time() - start_time
            print(f"✅ LLM応答受信完了 ({llm_time:.2f}秒)")
            print(f"   応答内容: {response[:200]}...")
            
        except Exception as e:
            print(f"❌ LLM呼び出しエラー: {e}")
            return False
        
        # Step 3: 音声合成と再生
        print("🎤 音声合成・再生開始...")
        synthesis_start_time = time.time()
        
        try:
            sentences = greeting_handler._split_into_sentences(response)
            print(f"📝 文章分割完了: {len(sentences)}文")
            
            if not sentences:
                print("❌ 分割された文章がありません")
                return False
            
            # PlaySpeechコマンドを作成（同期キューつき）
            play_command = PlaySpeech(
                task_id=f"ending_speech_test",
                sentences=sentences,
                sync_queue=sync_queue
            )
            
            print(f"🎵 音声再生コマンド作成完了: {len(sentences)}文")
            
            # 音声マネージャーで処理
            audio_manager.handle_play_speech(play_command)
            print("🔄 音声処理開始")
            
            # 同期待機（タイムアウトつき）
            print("⏰ 音声再生完了待機中（最大60秒）...")
            timeout_duration = 60.0
            wait_start_time = time.time()
            
            try:
                result = sync_queue.get(timeout=timeout_duration)
                wait_time = time.time() - wait_start_time
                total_time = time.time() - synthesis_start_time
                
                print(f"✅ 音声再生完了 (待機時間: {wait_time:.2f}秒, 総処理時間: {total_time:.2f}秒)")
                print(f"   同期結果: {result}")
                
            except queue.Empty:
                wait_time = time.time() - wait_start_time
                print(f"❌ 音声再生タイムアウト ({wait_time:.2f}秒)")
                print("   この問題が実際のシャットダウンでの60秒タイムアウトの原因です！")
                
                # AudioManagerの状態を確認
                print("\n🔍 AudioManager状態調査:")
                print(f"   - synthesis_queue size: {audio_manager.synthesis_queue.qsize()}")
                print(f"   - playback_queue size: {audio_manager.playback_queue.qsize()}")
                print(f"   - active_tasks: {list(audio_manager.active_tasks.keys())}")
                print(f"   - synthesis_worker alive: {audio_manager.synthesis_worker.is_alive() if hasattr(audio_manager, 'synthesis_worker') else 'N/A'}")
                print(f"   - playback_worker alive: {audio_manager.playback_worker.is_alive() if hasattr(audio_manager, 'playback_worker') else 'N/A'}")
                
                return False
                
        except Exception as e:
            print(f"❌ 音声処理エラー: {e}")
            return False
        
        print("✅ 終了挨拶処理完全成功")
        return True
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # クリーンアップ
        try:
            if 'audio_manager' in locals():
                audio_manager.stop()
            test_mode_manager.shutdown()
        except Exception as e:
            print(f"⚠️ クリーンアップエラー: {e}")


def test_audio_manager_threading():
    """AudioManagerのスレッド動作をテスト"""
    print("\n=== AudioManagerスレッド動作テスト ===")
    
    try:
        test_mode_manager.set_mode(TestMode.UNIT)
        
        event_queue = EventQueue()
        audio_manager = AudioManager(event_queue)
        
        print("✅ AudioManager初期化完了")
        
        # ワーカースレッドの状態確認
        if hasattr(audio_manager, 'synthesis_worker'):
            print(f"🧵 synthesis_worker status: {audio_manager.synthesis_worker.is_alive()}")
        if hasattr(audio_manager, 'playback_worker'):
            print(f"🧵 playback_worker status: {audio_manager.playback_worker.is_alive()}")
        
        # 簡単な音声テスト
        sync_queue = queue.Queue()
        test_command = PlaySpeech(
            task_id="thread_test_001",
            sentences=["これはスレッドテストです。"],
            sync_queue=sync_queue
        )
        
        print("🎵 簡単な音声テスト開始...")
        audio_manager.handle_play_speech(test_command)
        
        try:
            result = sync_queue.get(timeout=10.0)
            print(f"✅ 簡単な音声テスト成功: {result}")
        except queue.Empty:
            print("❌ 簡単な音声テストもタイムアウト")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ スレッドテストエラー: {e}")
        return False
        
    finally:
        try:
            if 'audio_manager' in locals():
                audio_manager.stop()
        except Exception as e:
            print(f"⚠️ クリーンアップエラー: {e}")


if __name__ == "__main__":
    print("🔧 優雅なシャットダウンシーケンステスト開始")
    print("=" * 60)
    
    # Test 1: 終了挨拶タイムアウト問題調査
    test1_success = test_ending_greeting_with_timeout()
    
    # Test 2: AudioManagerスレッド動作テスト  
    test2_success = test_audio_manager_threading()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    print(f"終了挨拶タイムアウト調査: {'✅ 成功' if test1_success else '❌ 失敗'}")
    print(f"AudioManagerスレッド動作: {'✅ 成功' if test2_success else '❌ 失敗'}")
    
    if test1_success and test2_success:
        print("\n🎉 すべてのテストが成功しました")
        print("   終了挨拶機能は正常に動作しています")
    else:
        print("\n❌ 問題が発見されました")
        print("   終了挨拶のタイムアウト問題を詳しく調査する必要があります")
    
    exit(0 if (test1_success and test2_success) else 1)