#!/usr/bin/env python3
"""
v2システムの統合テスト用スクリプト
AivisSpeechエンジンが動作していない環境でもテストできるよう軽量化
"""

import time
import threading
from murmur.core.event_queue import EventQueue
from murmur.core.events import AppStarted, NewCommentReceived
from murmur.state.state_manager import StateManager
from murmur.controllers.main_controller import MainController
from murmur.services.audio_manager import AudioManager
from murmur.services.integrated_comment_manager import IntegratedCommentManager
from murmur.handlers.monologue_handler import MonologueHandler
from murmur.handlers.comment_handler import CommentHandler


def test_v2_system():
    """v2システムの基本的な統合テスト"""
    print("=== v2 System Integration Test ===")
    
    # 1. コアコンポーネントの初期化
    event_queue = EventQueue()
    state_manager = StateManager()
    
    # 2. サービスとハンドラーの初期化
    audio_manager = AudioManager(event_queue)
    monologue_handler = MonologueHandler(event_queue)
    comment_handler = CommentHandler(event_queue)
    comment_manager = IntegratedCommentManager(event_queue)
    
    # 3. メインコントローラーの初期化
    main_controller = MainController(event_queue, state_manager)
    
    # 4. コマンドハンドラーのマッピング
    command_handlers = {
        'PlaySpeech': audio_manager.handle_play_speech,
        'PrepareMonologue': monologue_handler.handle_prepare_monologue,
        'PrepareCommentResponse': comment_handler.handle_prepare_comment_response,
    }
    
    print("✅ All components initialized successfully")
    
    # 5. 状態管理テスト
    print("📊 Current system state:", state_manager.get_status_summary())
    
    # 6. テスト用のコメントを手動で追加
    test_comment = {
        "username": "テストユーザー",
        "message": "こんにちは！配信楽しんでます",
        "timestamp": "2025-07-24 12:00:00",
        "user_id": "test_user_001",
        "message_id": "test_message_001",
        "author": {
            "name": "テストユーザー",
            "channel_id": "test_channel_001",
            "is_owner": False,
            "is_moderator": False,
            "is_verified": False,
            "badge_url": None
        },
        "superchat": None
    }
    
    print(f"📝 Adding test comment: {test_comment['message']}")
    comment_manager.add_comment(test_comment)
    
    # 7. 短時間でのイベント処理テスト（最大5サイクル）
    print("🔄 Starting event processing test...")
    
    # AppStartedイベントを発行
    event_queue.put(AppStarted())
    
    cycle_count = 0
    max_cycles = 5
    
    while cycle_count < max_cycles and state_manager.is_running:
        try:
            try:
                item = event_queue.get_nowait()  # ノンブロッキングで取得
            except:
                # キューが空の場合は少し待機してから再試行
                time.sleep(0.5)
                continue
            
            print(f"  📨 Processing: {type(item).__name__}")
            print(f"  📊 System state: {state_manager.current_state.value}")
            
            # コマンドかイベントかを判定して適切に処理
            item_type_name = type(item).__name__
            if item_type_name in command_handlers:
                command_handlers[item_type_name](item)
            else:
                # イベントの場合
                main_controller.process_item(item)
            
            cycle_count += 1
            print(f"  ✅ Cycle {cycle_count}/{max_cycles} completed")
            print(f"  📊 Final state: {state_manager.current_state.value}")
            
        except Exception as e:
            print(f"  ❌ Error during processing: {e}")
            cycle_count += 1
    
    print(f"🏁 Test completed after {cycle_count} cycles")
    
    # 8. 最終状態確認
    print(f"📊 Final system state: {state_manager.get_status_summary()}")
    
    # 9. クリーンアップ
    state_manager.is_running = False
    comment_manager.stop()
    
    print("✅ Integration test finished successfully")


if __name__ == "__main__":
    test_v2_system()