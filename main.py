import os
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
import queue
import signal
import argparse
import datetime


def log_message(message):
    """コンソールと txt/output_text_history.txt の両方にログを出力"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    
    print(formatted_message)
    
    try:
        os.makedirs("txt", exist_ok=True)
        with open("txt/output_text_history.txt", "a", encoding="utf-8") as f:
            f.write(formatted_message + "\n")
    except Exception as e:
        print(f"[LOG ERROR] Could not write to output_text_history.txt: {e}")


def main(argv=None):
    """
    アプリケーションのメインエントリーポイント。
    """
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(
        description='AI VTuber Monologue Agent v2'
    )
    parser.add_argument(
        '--theme',
        type=str,
        help='テーマファイルのパス (例: prompts/my_theme.txt)'
    )
    # 渡された引数リスト（argv）をパースする。Noneの場合はsys.argv[1:]が使われる。
    args = parser.parse_args(argv)
    
    log_message("Starting AITuberぶつぶつシステム v2... (Production Mode)")
    
    # テーマファイルが指定されている場合、設定を更新
    if args.theme:
        try:
            from config import config
            config.theme['current_theme_file'] = args.theme
            log_message(f"[Main] Theme file set to: {args.theme}")
        except Exception as e:
            log_message(f"[Main] Error setting theme file: {e}")

    # グローバル変数を宣言（シグナルハンドラーからアクセス可能にする）
    global state_manager, audio_manager
    
    # 1. コアコンポーネントの初期化
    event_queue = EventQueue()
    state_manager = StateManager()
    shutdown_event_queue = queue.Queue()  # シャットダウン同期用キュー

    # 2. サービスとハンドラーの初期化
    audio_manager = AudioManager(event_queue)
    
    # シグナルハンドラーを設定（変数定義後に設定）
    def signal_handler(signum, frame):
        log_message(f"\n[Main] Signal {signum} received. Initiating shutdown...")
        # グローバル変数として直接アクセス
        state_manager.is_running = False
        # 音声処理を即座に停止
        log_message("[Main] Stopping audio processing immediately...")
        audio_manager.stop()
        # KeyboardInterrupt例外を発生させて、メインループのexcept節で処理する
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    monologue_handler = MonologueHandler(event_queue)
    
    # ModeManagerとMasterPromptManagerを共有してCommentHandlerを初期化
    comment_handler = CommentHandler(
        event_queue, 
        monologue_handler.mode_manager,
        monologue_handler.master_prompt_manager
    )
    greeting_handler = GreetingHandler(
        event_queue, 
        monologue_handler.master_prompt_manager,
        monologue_handler.mode_manager  # mode_managerも共有
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
        PrepareCommentResponse: comment_handler.handle_prepare_comment_response,
        PrepareInitialGreeting: greeting_handler.handle_prepare_initial_greeting,
        PrepareEndingGreeting: greeting_handler.handle_prepare_ending_greeting,
        PrepareDailySummary: daily_summary_handler.handle_prepare_daily_summary,
    }

    # 4. メインコントローラーの初期化（DailySummaryHandlerとshutdown_event_queueを渡す）
    main_controller = MainController(
        event_queue, state_manager, daily_summary_handler, shutdown_event_queue,
        monologue_handler.mode_manager,  # ModeManagerも渡す
        audio_manager,  # AudioManagerを渡す
        theme_file=args.theme # テーマファイルのパスを渡す
    )

    # 5. コメント監視と日次要約スケジューラーを開始
    comment_manager.start()
    daily_summary_handler.start_scheduler()

    # 6. 起動イベントをキューに追加
    print("[Main] Putting AppStarted event into queue...")
    event_queue.put(AppStarted())
    print("[Main] AppStarted event has been put into queue")

    # 7. メインループ（イベント/コマンドディスパッチャ）
    print("[Main] Starting main loop...")
    print("Press Ctrl+C to exit gracefully.")
    
    # シャットダウンチェック用のカウンター
    event_counter = 0
    shutdown_check_interval = 1  # 毎イベント処理ごとにシャットダウンをチェック（応答性向上）
    
    try:
        while state_manager.is_running:
            try:
                # タイムアウトを短くしてKeyboardInterruptの応答性を向上
                item = event_queue.get(timeout=0.1)
                
                # フィラー状態をリセット（フィラーフレーズ以外のイベント/コマンドが処理される場合）
                if not _is_filler_event(item):
                    _reset_filler_state()
                
                if isinstance(item, Command):
                    handler = command_handlers.get(type(item))
                    if handler:
                        handler(item)
                    else:
                        item_name = type(item).__name__
                        log_message(
                            f"[Main] Warning: No handler for command {item_name}"
                        )
                else:  # It's an Event
                    main_controller.process_item(item)
                
                # 定期的なシャットダウンチェック
                event_counter += 1
                if event_counter >= shutdown_check_interval:
                    event_counter = 0
                    if _check_shutdown_request():
                        log_message("\n[Main] Shutdown request file detected. Starting graceful shutdown with farewell...")
                        # 終了シーケンスを開始
                        _start_shutdown_sequence(
                            main_controller,
                            greeting_handler,
                            audio_manager,
                            shutdown_event_queue
                        )
                        break

            except queue.Empty:
                # タイムアウトの場合はループを継続（KeyboardInterruptをチェック）
                # キューが空の時は毎回シャットダウンをチェック
                if _check_shutdown_request():
                    log_message("\n[Main] Shutdown request file detected. Starting graceful shutdown with farewell...")
                    # 終了シーケンスを開始
                    _start_shutdown_sequence(
                        main_controller,
                        greeting_handler,
                        audio_manager,
                        shutdown_event_queue
                    )
                    break
                # つなぎフレーズの処理
                _handle_empty_queue_filler(main_controller, audio_manager)
                continue
            except KeyboardInterrupt:
                log_message("\n[Main] KeyboardInterrupt received in main loop.")
                # 終了シーケンスを開始
                _start_shutdown_sequence(
                    main_controller,
                    greeting_handler,
                    audio_manager,
                    shutdown_event_queue
                )
                break
    
    except KeyboardInterrupt:
        log_message("\n[Main] KeyboardInterrupt received. Initiating graceful shutdown...")
        # 終了シーケンスを開始
        _start_shutdown_sequence(
            main_controller,
            greeting_handler,
            audio_manager,
            shutdown_event_queue
        )

    finally:
        # 8. シャットダウン処理
        log_message("[Main] Setting is_running to False to stop all threads...")
        state_manager.is_running = False
        
        # 関連コンポーネントの停止処理
        log_message("[Main] Stopping comment manager...")
        try:
            comment_manager.stop()
        except Exception as e:
            log_message(f"[Main] Error stopping comment manager: {e}")
            
        log_message("[Main] Stopping daily summary handler...")
        try:
            daily_summary_handler.stop_scheduler()
        except Exception as e:
            log_message(f"[Main] Error stopping daily summary handler: {e}")
            
        log_message("[Main] Stopping audio manager...")
        try:
            audio_manager.stop()
        except Exception as e:
            log_message(f"[Main] Error stopping audio manager: {e}")
        
        log_message("[Main] Waiting for components to shut down...")
        # 強制終了のタイムアウトを設定
        import time
        time.sleep(1)  # 1秒待機してコンポーネントの停止を待つ
        
        log_message("Monologue Agent v2 has shut down gracefully.")


def _handle_empty_queue_filler(main_controller, audio_manager):
    """キューが空の時のつなぎフレーズ処理"""
    import random
    import time
    
    # 静的変数として最後のつなぎフレーズ時刻とフラグを記録
    if not hasattr(_handle_empty_queue_filler, 'last_filler_time'):
        _handle_empty_queue_filler.last_filler_time = 0
        _handle_empty_queue_filler.filler_interval = 10.0  # 10秒間隔に延長
        _handle_empty_queue_filler.filler_played = False  # フィラー再生フラグ
        _handle_empty_queue_filler.silence_start_time = 0  # 無音開始時刻
    
    current_time = time.time()
    
    # 無音状態の開始時刻を記録
    if _handle_empty_queue_filler.silence_start_time == 0:
        _handle_empty_queue_filler.silence_start_time = current_time
        return
    
    # 無音状態が一定時間続いた場合のみフィラーを再生
    silence_duration = current_time - _handle_empty_queue_filler.silence_start_time
    
    # 前回のフィラーから一定時間経過し、かつまだ今回の無音でフィラーを再生していない場合
    filler_time_elapsed = (
        current_time - _handle_empty_queue_filler.last_filler_time >= 
        _handle_empty_queue_filler.filler_interval
    )
    if (filler_time_elapsed and
            silence_duration >= 3.0 and  # 3秒間無音が続いた場合
            not _handle_empty_queue_filler.filler_played):
        try:
            # つなぎフレーズのリスト
            filler_phrases = [
                "えーっと。",
                "そうですね。",
                "ちょっとまってくださいね",
            ]
            
            # ランダムにつなぎフレーズを選択
            selected_phrase = random.choice(filler_phrases)
            
            log_message(f"[Main] Playing filler phrase: {selected_phrase}")
            
            # 音声再生
            from v2.core.events import PlaySpeech
            import uuid
            
            play_speech_event = PlaySpeech(
                task_id=str(uuid.uuid4()),
                sentences=[selected_phrase]
            )
            
            audio_manager.handle_play_speech(play_speech_event)
            
            # 最後のつなぎフレーズ時刻を更新
            _handle_empty_queue_filler.last_filler_time = current_time
            
            # フィラー再生フラグを設定
            _handle_empty_queue_filler.filler_played = True
            
            # 次のつなぎフレーズまでの間隔をランダムに変更（15-30秒）
            _handle_empty_queue_filler.filler_interval = random.uniform(15.0, 30.0)
            
        except Exception as e:
            log_message(f"[Main] Error playing filler phrase: {e}")
    
def _is_filler_event(item):
    """アイテムがフィラーフレーズ関連のイベントかどうかを判定"""
    from v2.core.events import PlaySpeech
    if isinstance(item, PlaySpeech):
        # task_idに基づいてフィラーフレーズかどうかを判定
        # フィラーフレーズのsentencesを確認
        filler_phrases = [
            "うーん。",
            "うんうん。", 
            "えーっと。",
            "そうですね。",
            "どうだろうか。"
        ]
        if len(item.sentences) == 1 and item.sentences[0] in filler_phrases:
            return True
    return False

def _reset_filler_state():
    """フィラー状態をリセットする"""
    if hasattr(_handle_empty_queue_filler, 'silence_start_time'):
        _handle_empty_queue_filler.silence_start_time = 0
        _handle_empty_queue_filler.filler_played = False


def _check_shutdown_request():
    """終了リクエストファイルの存在をチェック"""
    shutdown_file = "shutdown_request.txt"
    if os.path.exists(shutdown_file):
        log_message(f"[Main] DEBUG: Shutdown request file found: {shutdown_file}")
        # ファイルを削除（一回限りのリクエスト）
        try:
            os.remove(shutdown_file)
            log_message("[Main] DEBUG: Shutdown request file removed successfully")
            return True
        except Exception as e:
            log_message(f"[Main] Warning: Could not remove shutdown file: {e}")
            return True
    return False


def _start_shutdown_sequence(
    main_controller, greeting_handler, audio_manager, shutdown_event_queue
):
    """Graceful shutdownシーケンスを開始する"""
    log_message("[Main] Starting shutdown sequence...")
    
    # 1. まず終了挨拶を最優先でキューに追加（AudioManagerの新規停止前）
    log_message("[Main] Generating and queuing farewell greeting...")
    _generate_ending_comment(
        main_controller, greeting_handler, audio_manager, shutdown_event_queue
    )
    
    # 2. 終了挨拶完了後、新しい音声処理を停止
    try:
        audio_manager.stop_new_audio_processing()
        log_message("[Main] New audio processing stopped after farewell greeting...")
    except AttributeError:
        log_message("[Main] Note: audio_manager does not support selective stopping")
    
    # 3. すべての音声キューが空になるまで待機（十分な時間を確保）
    log_message("[Main] Waiting for all audio queues to complete...")
    try:
        # タイムアウトを5分に延長（長い音声でも対応）
        if audio_manager.wait_for_current_audio_completion(timeout=300):
            log_message("[Main] ✅ All audio processing completed successfully.")
        else:
            log_message("[Main] ⚠️ Audio completion timeout after 5 minutes, proceeding with shutdown...")
            # タイムアウト時でも現在の状況をログ出力
            try:
                with audio_manager.lock:
                    active_count = len(audio_manager.active_tasks)
                    synthesis_empty = audio_manager.synthesis_queue.empty()
                    playback_empty = audio_manager.playback_queue.empty()
                    log_message(f"[Main] Audio status - Active tasks: {active_count}, Synthesis queue empty: {synthesis_empty}, Playback queue empty: {playback_empty}")
            except Exception as debug_error:
                log_message(f"[Main] Error getting audio status: {debug_error}")
    except AttributeError:
        log_message("[Main] Note: audio_manager does not support queue monitoring")
        # フォールバック: 固定時間待機
        log_message("[Main] Using fallback: waiting 60 seconds for audio completion...")
        import time
        time.sleep(60)

def _generate_ending_comment(
    main_controller, greeting_handler, audio_manager, shutdown_event_queue
):
    """終了時の振り返りコメントを生成（メインループ外から呼び出し可能）"""
    try:
        from v2.core.events import PlaySpeech
        from v2.core.test_mode import test_mode_manager
        import uuid

        # 1. 要約テキストの生成
        conversation_history = greeting_handler.conversation_history
        recent_conversations = []
        if conversation_history:
            recent_conversations = (
                conversation_history.get_recent_conversations("general", limit=10)
            )

        stream_summary = "本日の対話を通じて、多くのことを学びました。"  # デフォルトサマリー
        if recent_conversations:
            # 簡単な要約ロジック
            topics = [
                conv.get('responses', [{}])[0].get('content', '').split('。')[0]
                for conv in recent_conversations[-3:]
            ]
            if topics:
                stream_summary = (
                    f"特に「{topics[0]}」などについて話せたのが印象的でした。"
                )

        bridge_text = "それでは、本日の詩的言語探索はここまでとしましょう。"

        # 2. 終了挨拶プロンプトの構築とLLM呼び出し
        with open(
            'prompts/ending_greeting.txt',
            'r',
            encoding='utf-8'
        ) as f:
            prompt_template = f.read()
        
        ending_greeting_prompt = prompt_template.format(
            bridge_text=bridge_text,
            stream_summary=stream_summary
        )
        
        final_prompt = greeting_handler.master_prompt_manager.wrap_task_with_master_prompt(
            specific_task_prompt=ending_greeting_prompt,
            current_mode="ending_greeting"
        )
        
        response = greeting_handler.openai_adapter.create_chat_for_response(
            final_prompt
        )
        print(f"[Main] Generated ending comment: {response[:100]}...")
        
        # 3. 音声再生と同期的な待機
        sentences = greeting_handler._split_into_sentences(response)
        if not sentences:
            print("[Main] No sentences to play for ending comment.")
            return

        sync_queue = queue.Queue()
        play_command = PlaySpeech(
            task_id=f"ending_speech_{uuid.uuid4()}",
            sentences=sentences,
            sync_queue=sync_queue
        )
        audio_manager.handle_play_speech(play_command)

        # 音声再生完了を待機（タイムアウトなし）
        try:
            print("[Main] Waiting for ending audio playback to complete (no timeout)...")
            sync_queue.get()  # タイムアウトなしで自然な完了を待機
            print("[Main] Ending audio playback completed successfully.")
        except Exception as e:
            print(f"[Main] Unexpected error during ending audio playback: {e}")
            # AudioManagerの状態をデバッグ出力
            try:
                with audio_manager.lock:
                    active_count = len(audio_manager.active_tasks)
                    log_message(f"[Main] DEBUG: Active audio tasks: {active_count}")
                    if audio_manager.active_tasks:
                        for task_id, task_info in audio_manager.active_tasks.items():
                            log_message(f"[Main] DEBUG: Task {task_id}: {task_info}")
            except Exception as debug_error:
                log_message(f"[Main] Error during debug output: {debug_error}")
            log_message("[Main] Proceeding with shutdown despite error.")
            
    except Exception as e:
        log_message(f"[Main] Error in _generate_ending_comment: {e}")
        log_message("[Main] Proceeding with shutdown despite error.")


if __name__ == "__main__":
    main() 