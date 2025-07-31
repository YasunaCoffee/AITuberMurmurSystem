#!/usr/bin/env python3
"""
Test Main Module
テスト専用のメイン関数
"""

from v2.core.event_queue import EventQueue
from v2.core.events import (
    AppStarted,
    Command,
    PlaySpeech,
    PrepareMonologue,
    PrepareCommentResponse,
    PrepareInitialGreeting,
    PrepareEndingGreeting,
    PrepareDailySummary,
)
from v2.state.state_manager import StateManager
from v2.controllers.main_controller import MainController
from v2.services.audio_manager import AudioManager
from v2.services.integrated_comment_manager import IntegratedCommentManager
from v2.handlers.monologue_handler import MonologueHandler
from v2.handlers.comment_handler import CommentHandler
from v2.handlers.greeting_handler import GreetingHandler
from v2.handlers.daily_summary_handler import DailySummaryHandler
from v2.core.test_mode import test_mode_manager
import queue
import signal
import argparse


def test_main(argv=None):
    """
    テスト専用のメインエントリーポイント
    """
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(
        description='AI VTuber Monologue Agent v2 (Test Mode)'
    )
    parser.add_argument(
        '--theme',
        type=str,
        help='テーマファイルのパス (例: prompts/my_theme.txt)'
    )
    args = parser.parse_args(argv)
    
    # テストモード情報を表示
    current_mode = test_mode_manager.get_mode()
    print(f"Starting Monologue Agent v2... (Mode: {current_mode.value})")
    
    # テーマファイルが指定されている場合、設定を更新
    if args.theme:
        try:
            from config import config
            config.theme['current_theme_file'] = args.theme
            print(f"[TestMain] Theme file set to: {args.theme}")
        except Exception as e:
            print(f"[TestMain] Error setting theme file: {e}")
    
    # テストモード設定を表示
    if test_mode_manager.is_test_mode():
        config = test_mode_manager.get_config()
        print("[TestMode] Configuration:")
        print(f"  - Mock OpenAI: {config.use_mock_openai}")
        print(f"  - Mock Audio: {config.use_mock_audio}")
        print(f"  - Mock YouTube: {config.use_mock_youtube}")
        print(
            f"  - Auto Stop: {config.auto_stop_enabled} "
            f"({config.max_runtime_minutes}min)"
        )
        print(f"  - Dummy Comments: {config.dummy_comments_enabled}")

    # グローバル変数で参照可能にする
    global state_manager, audio_manager
    
    # シグナルハンドラーを設定
    def signal_handler(signum, frame):
        print(f"\n[TestMain] Signal {signum} received. Initiating shutdown...")
        if 'state_manager' in globals():
            state_manager.is_running = False
        # 音声処理を即座に停止
        if 'audio_manager' in globals():
            print("[TestMain] Stopping audio processing immediately...")
            audio_manager.stop()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 1. コアシステムの初期化
        event_queue = EventQueue()
        state_manager = StateManager()
        shutdown_event_queue = queue.Queue()

        # 2. サービスとハンドラーの初期化
        audio_manager = AudioManager(event_queue)
        monologue_handler = MonologueHandler(event_queue)
        
        # ModeManagerとMasterPromptManagerを共有してCommentHandlerを初期化
        comment_handler = CommentHandler(
            event_queue, 
            monologue_handler.mode_manager,
            monologue_handler.master_prompt_manager
        )
        greeting_handler = GreetingHandler(
            event_queue, monologue_handler.master_prompt_manager
        )
        
        # Daily Summary Handlerを初期化（memory_managerを共有）
        daily_summary_handler = DailySummaryHandler(
            event_queue, monologue_handler.memory_manager
        )
        comment_manager = IntegratedCommentManager(event_queue)

        # 3. コマンドとハンドラーのマッピングを定義
        command_handlers = {
            PlaySpeech: audio_manager.handle_play_speech,
            PrepareMonologue: monologue_handler.handle_prepare_monologue,
            PrepareCommentResponse: (
                comment_handler.handle_prepare_comment_response
            ),
            PrepareInitialGreeting: (
                greeting_handler.handle_prepare_initial_greeting
            ),
            PrepareEndingGreeting: (
                greeting_handler.handle_prepare_ending_greeting
            ),
            PrepareDailySummary: (
                daily_summary_handler.handle_prepare_daily_summary
            ),
        }

        # 4. メインコントローラーの初期化
        main_controller = MainController(
            event_queue, state_manager, daily_summary_handler,
            shutdown_event_queue
        )

        # 5. コメント監視と日次要約スケジューラーを開始
        comment_manager.start()
        daily_summary_handler.start_scheduler()

        # 6. 起動イベントをキューに追加
        print("[TestMain] Putting AppStarted event into queue...")
        event_queue.put(AppStarted())
        print("[TestMain] AppStarted event has been put into queue")

        # 7. メインループ（イベント/コマンドディスパッチャ）
        print("[TestMain] Starting main loop...")
        print("Press Ctrl+C to exit gracefully.")
        
        # フィラー関連の状態変数
        last_filler_time = None
        
        while state_manager.is_running:
            try:
                # タイムアウトを短くしてKeyboardInterruptの応答性を向上
                item = event_queue.get(timeout=0.1)
                
                if isinstance(item, Command):
                    handler = command_handlers.get(type(item))
                    if handler:
                        handler(item)
                    else:
                        item_name = type(item).__name__
                        print(
                            f"[TestMain] Warning: No handler for command "
                            f"{item_name}"
                        )
                else:  # It's an Event
                    main_controller.process_item(item)

            except queue.Empty:
                # タイムアウトの場合はループを継続
                continue

    except KeyboardInterrupt:
        print("\n[TestMain] KeyboardInterrupt received in main loop.")
        
    finally:
        print("[TestMain] Starting shutdown procedure...")
        
        # システムをシャットダウン
        if 'state_manager' in locals():
            state_manager.is_running = False
        
        # コンポーネントを適切にシャットダウン
        if 'comment_manager' in locals():
            comment_manager.stop()
        if 'daily_summary_handler' in locals():
            daily_summary_handler.stop_scheduler()
        if 'audio_manager' in locals():
            audio_manager.stop()
            
        # テストモードマネージャーのシャットダウン
        test_mode_manager.shutdown()
        
        print("[TestMain] Shutdown completed.")


if __name__ == "__main__":
    test_main() 