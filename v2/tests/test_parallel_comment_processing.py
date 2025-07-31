#!/usr/bin/env python3
"""
並行コメント処理のテストスクリプト
発話中にコメントが来た際の並行処理を検証
"""

import time
import threading
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from v2.core.event_queue import EventQueue
from v2.core.events import AppStarted, NewCommentReceived, SpeechPlaybackCompleted
from v2.state.state_manager import StateManager, SystemState
from v2.controllers.main_controller import MainController


def test_parallel_comment_processing():
    """並行コメント処理のテスト"""
    print("=== 並行コメント処理テスト ===")
    
    # 1. コンポーネント初期化
    event_queue = EventQueue()
    state_manager = StateManager()
    main_controller = MainController(event_queue, state_manager)
    
    print("✅ コンポーネント初期化完了")
    
    # 2. システムをSPEAKING状態にセット（発話中をシミュレート）
    state_manager.set_state(SystemState.SPEAKING, "speaking_task_123", "monologue")
    print(f"📢 システム状態: {state_manager.current_state.value}")
    
    # 3. 発話中にコメントが来た場合をシミュレート
    test_comments = [{
        "username": "並行テストユーザー",
        "message": "発話中に来たコメント",
        "timestamp": "2025-07-24 23:15:00",
        "user_id": "parallel_test_user",
        "message_id": "parallel_test_msg",
        "author": {
            "name": "並行テストユーザー",
            "channel_id": "parallel_test_channel",
            "is_owner": False,
            "is_moderator": False,
            "is_verified": False,
            "badge_url": None
        },
        "superchat": None
    }]
    
    # 4. NewCommentReceivedイベントを発行
    comment_event = NewCommentReceived(comments=test_comments)
    print(f"💬 コメントイベント発行: {test_comments[0]['message']}")
    
    # 5. MainControllerでイベント処理
    main_controller.handle_new_comment_received(comment_event)
    
    # 6. 結果確認
    print(f"📊 処理後システム状態: {state_manager.current_state.value}")
    print(f"📝 保留中コメント数: {len(state_manager.pending_comments)}")
    print(f"🎯 生成済み応答数: {len(getattr(state_manager, 'prepared_responses', []))}")
    
    # 7. イベントキューに並行処理コマンドが入っているか確認
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
    
    # 8. 発話完了をシミュレート
    print("\n--- 発話完了をシミュレート ---")
    speech_completed_event = SpeechPlaybackCompleted(task_id="speaking_task_123")
    main_controller.handle_speech_playback_completed(speech_completed_event)
    
    print(f"📊 完了後システム状態: {state_manager.current_state.value}")
    print(f"🎯 生成済み応答の確認: {state_manager.has_prepared_responses()}")
    
    # 9. 追加でキューに入った項目を確認
    additional_items = []
    try:
        while True:
            item = event_queue.get_nowait()
            additional_items.append(item)
    except:
        pass
    
    print(f"📦 追加キュー項目数: {len(additional_items)}")
    for i, item in enumerate(additional_items):
        print(f"   {i+1}. {type(item).__name__}")
    
    # 10. 結果評価
    success_criteria = [
        len(queued_items) > 0,  # 並行処理コマンドがキューに入った
        state_manager.has_pending_comments() or len(queued_items) > 0,  # コメントが適切に処理された
    ]
    
    success = all(success_criteria)
    
    print(f"\n=== テスト結果 ===")
    print(f"並行処理実装: {'✅ 成功' if success else '❌ 失敗'}")
    print(f"コマンドキューイング: {'✅' if len(queued_items) > 0 else '❌'}")
    print(f"状態管理: {'✅' if state_manager.current_state != SystemState.SPEAKING else '❌'}")
    
    return success


if __name__ == "__main__":
    try:
        success = test_parallel_comment_processing()
        print(f"\n🏁 {'テスト成功！' if success else 'テスト失敗'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)