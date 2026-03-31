#!/usr/bin/env python3
"""
KeyboardInterrupt機能のテスト
Ctrl+Cで正常にシステムが停止するかを確認
"""

import sys
import os
import time
import signal
import threading

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.event_queue import EventQueue
from murmur.state.state_manager import StateManager
from murmur.services.integrated_comment_manager import IntegratedCommentManager

print("=== KeyboardInterrupt機能テスト ===")

def test_keyboard_interrupt():
    """KeyboardInterrupt処理のテスト"""
    
    print("🔧 システム初期化中...")
    
    # システム初期化
    event_queue = EventQueue()
    state_manager = StateManager()
    
    # CommentManagerを初期化（テストモード）
    os.environ['CHAT_TEST_MODE'] = 'true'
    comment_manager = IntegratedCommentManager(event_queue)
    
    print("✅ システム初期化完了")
    
    # シグナルハンドラーを設定
    def signal_handler(signum, frame):
        print(f"\n🛑 Signal {signum} received. Initiating shutdown...")
        state_manager.is_running = False
        comment_manager.stop()
        print("💾 Graceful shutdown completed.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # サービス開始
        print("🚀 サービス開始...")
        comment_manager.start()
        
        print("\n" + "="*60)
        print("📋 KeyboardInterruptテスト開始")
        print("="*60)
        print("⌨️  Ctrl+C を押してシステムを停止してください")
        print("⏱️  10秒後に自動停止します")
        print("🔍 応答性をテスト中...")
        
        start_time = time.time()
        while state_manager.is_running and (time.time() - start_time) < 10:
            try:
                # 短いタイムアウトでキューチェック
                time.sleep(0.1)
                print(".", end="", flush=True)
            except KeyboardInterrupt:
                print("\n✅ KeyboardInterrupt捕捉成功！")
                break
        
        if time.time() - start_time >= 10:
            print("\n⏰ 10秒経過。自動停止します...")
            
    except KeyboardInterrupt:
        print("\n✅ メインループでKeyboardInterrupt捕捉成功！")
    
    finally:
        print("\n🛑 終了処理中...")
        state_manager.is_running = False
        comment_manager.stop()
        
        # 停止確認
        time.sleep(1)
        if not comment_manager.running:
            print("✅ CommentManager正常停止")
        else:
            print("⚠️ CommentManager停止に問題")
        
        print("🎯 KeyboardInterruptテスト完了")

if __name__ == "__main__":
    print("キーボード割り込みテストを開始します...")
    print("注意: このテストはCtrl+Cで停止できることを確認します")
    
    try:
        test_keyboard_interrupt()
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)