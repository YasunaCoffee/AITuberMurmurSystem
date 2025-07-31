import time
import threading
import queue

try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print(
        "[AudioManager] Warning: sounddevice or numpy not available, "
        "using simulation mode"
    )

from v2.core.event_queue import EventQueue
from v2.core.events import PlaySpeech, SpeechPlaybackCompleted
from aivis_speech_adapter import AivisSpeechAdapter
import os
import datetime


def log_speech_output(text):
    """音声出力された文字をtxt/output_text_history.txtに記録"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"[{timestamp}] 🎤 {text}"
    
    try:
        os.makedirs("txt", exist_ok=True)
        with open("txt/output_text_history.txt", "a", encoding="utf-8") as f:
            f.write(formatted_text + "\n")
    except Exception as e:
        print(f"[LOG ERROR] Could not write speech to output_text_history.txt: {e}")


class AudioManager:
    """
    音声の合成と再生をパイプライン処理で行うサービス。
    PlaySpeechコマンドを受け取り、合成と再生を非同期で実行し、
    完了後にSpeechPlaybackCompletedイベントを発行する。
    """
    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        
        # --- キューの初期化 ---
        # (task_id, sentence_text, sentence_index, total_sentences)
        self.synthesis_queue = queue.Queue()
        # (task_id, audio_data, sample_rate, sentence_index, total_sentences)
        self.playback_queue = queue.Queue()
        
        # --- 状態管理 ---
        self.active_tasks = {}  # task_id -> { "total": int, "completed": int }
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self._stop_new_tasks = False  # 新しいタスクの受付停止フラグ
        self.current_text = ""  # 現在再生中のテキスト

        # --- アダプタとワーカーの初期化 ---
        self.aivis_adapter = None
        self.audio_enabled = self._initialize_adapter()

        # 音声出力デバイスの設定
        self._setup_audio_device()

        self.synthesis_worker = threading.Thread(
            target=self._synthesis_worker, daemon=True
        )
        self.playback_worker = threading.Thread(
            target=self._playback_worker, daemon=True
        )
        
        self.synthesis_worker.start()
        self.playback_worker.start()
        
        # OBSテキストマネージャー
        self.obs_text_manager = None

    def _initialize_adapter(self) -> bool:
        """AivisSpeechAdapterを初期化する"""
        try:
            self.aivis_adapter = AivisSpeechAdapter()
            print("[AudioManager] AivisSpeech adapter initialized successfully")
            return True
        except Exception as e:
            print(
                "[AudioManager] Warning: AivisSpeech adapter initialization "
                f"failed: {e}"
            )
            return False

    def handle_play_speech(self, command: PlaySpeech):
        """音声再生コマンドを処理する"""
        if self._stop_new_tasks:
            print(f"New audio processing is stopped. Ignoring task: {command.task_id}")
            return

        if not self.audio_enabled:
            print("Audio not enabled, simulating playback")
            time.sleep(len(command.sentences) * 1.0)
            completed_event = SpeechPlaybackCompleted(task_id=command.task_id)
            self.event_queue.put(completed_event)
            return

        with self.lock:
            if not command.sentences:
                print(f"PlaySpeech command for task {command.task_id} has no sentences. Completing immediately.")
                completed_event = SpeechPlaybackCompleted(task_id=command.task_id)
                self.event_queue.put(completed_event)
                return

            self.active_tasks[command.task_id] = {
                "total": len(command.sentences),
                "completed_synthesis": 0,
                "completed_playback": 0,
            }

        for i, sentence in enumerate(command.sentences):
            self.synthesis_queue.put((command.task_id, sentence, i, len(command.sentences)))
            print(f"Queued sentence {i+1}/{len(command.sentences)} for task {command.task_id}")

    def _synthesis_worker(self):
        """音声合成キューを監視し、音声合成を実行して再生キューに入れる"""
        while not self.stop_event.is_set():
            try:
                task_item = self.synthesis_queue.get(timeout=1)
                
                # 停止シグナルをチェック
                if task_item[0] is None:
                    break

                task_id, sentence, index, total = task_item
                
                if not self.audio_enabled or not self.aivis_adapter:
                    # シミュレーションモード
                    audio_data, sample_rate = (None, 0)
                else:
                    try:
                        print(
                            f"🎵 Synthesizing ({index+1}/{total}): "
                            f"{sentence[:30]}..."
                        )
                        audio_data, sample_rate = self.aivis_adapter.get_voice(
                            sentence, 1
                        )
                    except Exception as e:
                        print(
                            f"❌ Synthesis failed for sentence {index+1}: {e}"
                        )
                        audio_data, sample_rate = (
                            np.zeros(1000, dtype=np.float32), 24000
                        )

                self.playback_queue.put(
                    (task_id, audio_data, sample_rate, sentence, index, total)
                )
                
                with self.lock:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id]["completed_synthesis"] += 1
                
                self.synthesis_queue.task_done()
            except queue.Empty:
                continue

    def _playback_worker(self):
        """再生キューを監視し、音声を再生する"""
        while not self.stop_event.is_set():
            try:
                task_item = self.playback_queue.get(timeout=1)

                # 停止シグナルをチェック
                if task_item[0] is None:
                    break
                
                (
                    task_id, audio_data, sample_rate, text, index, total
                ) = task_item

                print(f"🔊 Playing ({index+1}/{total}) for task: {task_id}")
                print(f"[DEBUG AudioManager] Playing audio for text: {text[:30]}...")

                # 音声データから再生時間を計算
                if audio_data is not None and isinstance(audio_data, np.ndarray) and sample_rate > 0:
                    duration = len(audio_data) / sample_rate
                else:
                    # シミュレーション用のデフォルト時間
                    duration = 1.0

                # 発話内容をログに出力
                log_speech_output(text)

                # 字幕を表示（音声再生前）
                if self.obs_text_manager:
                    try:
                        play_speech = PlaySpeech(task_id=task_id, sentences=[text])
                        self.obs_text_manager.handle_play_speech(play_speech, duration)
                    except Exception as e:
                        print(f"[AudioManager] Failed to display subtitle: {e}")

                # 音声を再生
                if audio_data is not None and sample_rate > 0:
                    sd.play(audio_data, sample_rate)
                    sd.wait()  # 再生完了まで待機

                # 字幕をクリア（音声再生後）
                if self.obs_text_manager:
                    try:
                        completed_event = SpeechPlaybackCompleted(task_id=task_id)
                        self.obs_text_manager.handle_speech_completed(completed_event)
                    except Exception as e:
                        print(f"[AudioManager] Failed to clear subtitle: {e}")

                print(f"[DEBUG AudioManager] Completed playback for sentence {index+1}/{total}")
                
                # タスクの完了をチェック
                self._check_task_completion(task_id)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[AudioManager] Playback error: {e}")
                continue

    def _check_task_completion(self, task_id: str):
        """タスクの全音声が再生完了したかチェックし、完了ならイベントを発行"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task["completed_playback"] += 1
                
                print(f"[DEBUG AudioManager] Task {task_id}: {task['completed_playback']}/{task['total']} completed")

                if task["completed_playback"] == task["total"]:
                    print(f"✅ Speech completed for task: {task_id}")
                    print(f"[DEBUG AudioManager] Emitting SpeechPlaybackCompleted for task: {task_id}")
                    event = SpeechPlaybackCompleted(task_id=task_id)
                    self.event_queue.put(event)

                    # 同期キューにも完了を通知
                    if task.get("sync_queue"):
                        task["sync_queue"].put(True)

                    del self.active_tasks[task_id]

    def stop(self):
        """全ワーカーを停止する"""
        print("[AudioManager] Stopping...")
        self.stop_event.set()
        # キューにダミーデータをいれてワーカーを終了させる
        self.synthesis_queue.put((None, None, None, None))
        self.playback_queue.put((None, None, None, None, None, None))
        
        self.synthesis_worker.join(timeout=2)
        self.playback_worker.join(timeout=2)
        print("[AudioManager] Stopped.")

    def is_audio_queue_empty(self):
        """現在の音声キューが空で、処理中のタスクがないかを確認"""
        with self.lock:
            synthesis_empty = self.synthesis_queue.empty()
            playback_empty = self.playback_queue.empty()
            no_active_tasks = len(self.active_tasks) == 0
            
            return synthesis_empty and playback_empty and no_active_tasks
    
    def wait_for_current_audio_completion(self, timeout=60):
        """現在キューにある音声の再生完了を待機"""
        print("[AudioManager] Waiting for current audio queue to complete...")
        start_time = time.time()
        
        while not self.is_audio_queue_empty():
            if time.time() - start_time > timeout:
                print(f"[AudioManager] Timeout ({timeout}s) waiting for audio completion")
                return False
            
            # アクティブなタスクの状況を表示
            with self.lock:
                if self.active_tasks:
                    task_count = len(self.active_tasks)
                    print(f"[AudioManager] Still processing {task_count} audio tasks...")
            
            time.sleep(1)
        
        print("[AudioManager] All current audio tasks completed!")
        return True

    def stop_new_audio_processing(self):
        """新しい音声処理は停止するが、現在のキューは完了まで処理"""
        print("[AudioManager] Stopping new audio processing (current queue will complete)...")
        # 新しいタスクの受付を停止するフラグを設定
        # ここでは単にログを出力（実際の停止は handle_play_speech で制御）
        self._stop_new_tasks = True

    def clear_audio_queues(self):
        """Clears the synthesis and playback queues and stops current playback."""
        print("[AudioManager] Clearing audio queues for shutdown...")
        # Stop any currently playing audio
        try:
            sd.stop()
        except Exception as e:
            print(f"[AudioManager] Error stopping sounddevice: {e}")

        # Clear synthesis queue
        while not self.synthesis_queue.empty():
            try:
                self.synthesis_queue.get_nowait()
            except queue.Empty:
                break
        print("[AudioManager] Synthesis queue cleared.")

        # Clear playback queue
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
            except queue.Empty:
                break
        print("[AudioManager] Playback queue cleared.")

    def _prioritize_ending_speech(self):
        """終了挨拶を優先するため、他の進行中タスクをクリアする"""
        print("[AudioManager] 🎯 Prioritizing ending speech: clearing other tasks...")
        
        # 🎵 現在再生中の音声は最後まで再生（強制停止しない）
        print("[AudioManager] 🎵 Current audio will complete naturally before ending speech")
        
        with self.lock:
            # 進行中のタスクから終了挨拶以外を削除（ただし現在再生中は保持）
            ending_tasks = {}
            cleared_count = 0
            
            for task_id, task_info in list(self.active_tasks.items()):
                if task_id.startswith('ending_speech'):
                    ending_tasks[task_id] = task_info
                elif task_info["completed_playback"] < task_info["total"]:
                    # 再生中のタスクは保持（自然完了を待つ）
                    ending_tasks[task_id] = task_info
                    print(f"[AudioManager] 🎵 Keeping active task for natural completion: {task_id}")
                else:
                    cleared_count += 1
                    # sync_queueがある場合は完了通知を送信
                    if task_info.get("sync_queue"):
                        try:
                            task_info["sync_queue"].put(False)  # 失敗を通知
                        except Exception as e:
                            print(f"[AudioManager] Warning: sync_queue notification failed: {e}")
            
            self.active_tasks = ending_tasks
            print(f"[AudioManager] 🧹 Cleared {cleared_count} non-active tasks")
        
        # 新しいタスク（プリフェッチなど）のキューをクリア
        self._clear_new_task_queues()
        print("[AudioManager] 🎯 Ready for natural transition to ending speech")



    def _clear_new_task_queues(self):
        """新しいタスク（現在再生中以外）のキューアイテムをクリア"""
        with self.lock:
            active_task_ids = set(self.active_tasks.keys())
        
        # 合成キューのクリア（アクティブタスクは保持）
        cleared_synthesis = 0
        temp_items = []
        
        while not self.synthesis_queue.empty():
            try:
                item = self.synthesis_queue.get_nowait()
                if item[0] and item[0] in active_task_ids:
                    temp_items.append(item)
                else:
                    cleared_synthesis += 1
            except queue.Empty:
                break
        
        # アクティブタスクのみを戻す
        for item in temp_items:
            self.synthesis_queue.put(item)
        
        # 再生キューのクリア（アクティブタスクは保持）
        cleared_playback = 0
        temp_items = []
        
        while not self.playback_queue.empty():
            try:
                item = self.playback_queue.get_nowait()
                if item[0] and item[0] in active_task_ids:
                    temp_items.append(item)
                else:
                    cleared_playback += 1
            except queue.Empty:
                break
        
        # アクティブタスクのみを戻す
        for item in temp_items:
            self.playback_queue.put(item)
        
        print(f"[AudioManager] 🗑️ Cleared {cleared_synthesis} synthesis + {cleared_playback} new task items")

    def set_obs_text_manager(self, obs_text_manager):
        """OBSTextManagerを設定する"""
        self.obs_text_manager = obs_text_manager

    def _setup_audio_device(self):
        """音声出力デバイスを設定する"""
        # 利用可能なデバイスを表示
        print("\n利用可能な音声出力デバイス:")
        print(sd.query_devices())
        
        # Cable Inputを探す
        cable_input_idx = None
        for idx, device in enumerate(sd.query_devices()):
            if 'CABLE Input' in device['name']:
                cable_input_idx = idx
                break
        
        if cable_input_idx is not None:
            # Cable Inputをデフォルトの出力デバイスとして設定
            sd.default.device = None, cable_input_idx  # 入力はデフォルト、出力はCable Input
            print(f"\n✅ Cable Input (デバイスID: {cable_input_idx}) を出力デバイスとして設定しました")
        else:
            print("\n⚠️ Cable Inputが見つかりませんでした。デフォルトの出力デバイスを使用します")