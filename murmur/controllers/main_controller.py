import queue
import time
import uuid
from typing import Optional
from murmur.core.event_queue import EventQueue, QueueItem
from murmur.state.state_manager import StateManager, SystemState
from murmur.core.logger import get_logger
from murmur.core.events import (
    Event, Command, AppStarted, PlaySpeech, SpeechPlaybackCompleted,
    PrepareMonologue, MonologueReady, NewCommentReceived, CommentResponseReady,
    PrepareCommentResponse, InitialGreetingRequested, EndingGreetingRequested,
    InitialGreetingReady, EndingGreetingReady, PrepareInitialGreeting,
    PrepareEndingGreeting, DailySummaryReady,
    StreamEnded, MonologueFromThemeRequested
)
from murmur.services.obs_text_manager import OBSTextManager


class MainController:
    """
    イベントキューを監視し、イベントに基づいてコマンドを発行する、
    アプリケーションの「頭脳」。
    """
    def __init__(
        self,
        event_queue: EventQueue,
        state_manager: StateManager,
        daily_summary_handler=None,
        shutdown_event_queue: Optional[queue.Queue] = None,
        mode_manager=None,  # ModeManagerを受け取る
        audio_manager=None,  # AudioManagerを受け取る
        theme_file: Optional[str] = None # テーマファイルのパスを受け取る
    ):
        self.event_queue = event_queue
        self.state_manager = state_manager
        self.logger = get_logger("MainController")
        self.daily_summary_handler = daily_summary_handler  # DailySummaryHandlerの参照を保持
        self.shutdown_event_queue = shutdown_event_queue
        self.mode_manager = mode_manager  # ModeManagerを保存
        self.audio_manager = audio_manager  # AudioManagerを保存
        self.theme_file = theme_file # テーマファイルを保存
        
        # --- 追加: 挨拶後コメント返信カウンター ---
        self.post_greeting_response_count = 0
        
        # OBSテキストマネージャーの初期化
        self.obs_text_manager = OBSTextManager(event_queue, audio_manager)
        if self.audio_manager:
            self.audio_manager.set_obs_text_manager(self.obs_text_manager)
        
        # 朗読制御フラグ：テーマ朗読を1回限りに制限
        self.theme_reading_completed = False
        
        # プリフェッチシステムの初期化
        self.prefetch_queue_size = 2
        self.prefetched_monologues = queue.Queue(maxsize=self.prefetch_queue_size)
        self.is_prefetching = False # プリフェッチ中フラグ
        self.command_handlers = {}  # MainControllerはコマンドを直接処理しない

        # キューイングシステムの初期化
        self.queued_comment_responses = []  # 保留中のコメント応答

        # 配信時間追跡
        self.stream_start_time = time.time()
        
        self.event_handlers = {
            AppStarted: self.handle_app_started,
            MonologueFromThemeRequested: self.handle_monologue_from_theme_requested,
            SpeechPlaybackCompleted: self.handle_speech_playback_completed,
            MonologueReady: self.handle_monologue_ready,
            NewCommentReceived: self.handle_new_comment_received,
            CommentResponseReady: self.handle_comment_response_ready,
            InitialGreetingRequested: self.handle_initial_greeting_requested,
            EndingGreetingRequested: self.handle_ending_greeting_requested,
            InitialGreetingReady: self.handle_initial_greeting_ready,
            EndingGreetingReady: self.handle_ending_greeting_ready,
            DailySummaryReady: self.handle_daily_summary_ready,
            StreamEnded: self.handle_stream_ended,
        }

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        テキストを文に分割する。
        句点「。」と改行「\n」を区切り文字として使用する。
        """
        # まず改行で分割
        lines = text.split('\n')
        
        sentences = []
        for line in lines:
            # 各行をさらに句点で分割
            parts = line.split("。")
            for i, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue
                
                # 分割された部分が元の文の末尾でない場合、句点を再度追加
                if i < len(parts) - 1:
                    sentences.append(part + "。")
                else:
                    sentences.append(part)
        
        # 最終的に空の文字列を除去
        result = [s for s in sentences if s]
        
        # もし分割されなかった場合、元のテキストを返す
        if not result:
            return [text]
            
        return result

    def clear_prefetch_queue(self):
        """プリフェッチされたモノローグのキューをクリアする。"""
        while not self.prefetched_monologues.empty():
            try:
                self.prefetched_monologues.get_nowait()
            except queue.Empty:
                break
        self.logger.info("Prefetch queue has been cleared.")

    def run(self):
        """メインのイベントループ。"""
        while self.state_manager.is_running:
            try:
                self.run_once(blocking=True)
            except KeyboardInterrupt:
                print("KeyboardInterrupt received, shutting down.")
                self.state_manager.is_running = False
                break
        print("Main event loop finished.")

    def run_once(self, blocking: bool = False):
        """
        イベントループを1回だけ実行する。
        テストのために、ブロッキングとノンブロッキングを切り替えられるようにする。
        """
        try:
            if blocking:
                item = self.event_queue.get()
            else:
                item = self.event_queue.get_nowait()
            self.process_item(item)
        except queue.Empty:
            # ノンブロッキングモードでキューが空の場合は何もしない
            pass
            
    def process_item(self, item: QueueItem):
        """イベントまたはコマンドを処理する。"""
        item_type = type(item).__name__
        
        if isinstance(item, Event):
            self.logger.log_event(item_type, {"item_data": str(item)})
            handler = self.event_handlers.get(type(item))
            if handler:
                try:
                    handler(item)
                    self.logger.debug(
                        f"Event {item_type} handled successfully",
                        event_type="event_handled",
                        event_name=item_type
                    )
                except Exception as e:
                    self.logger.log_error_with_context(
                        e,
                        {"event": item_type, "item_data": str(item)}
                    )
                    raise
            else:
                self.logger.warning(
                    f"No handler for event {item_type}",
                    event_type="unhandled_event",
                    event_name=item_type
                )
        elif isinstance(item, Command):
            # コマンドの場合は何もしない（main_v2.pyのディスパッチャが処理）
            self.logger.log_command(item_type, {"item_data": str(item)})

    # --- Prefetch System ---
    
    def start_prefetch_if_needed(self):
        """必要に応じてプリフェッチを開始"""
        if (self.prefetched_monologues.qsize() < self.prefetch_queue_size and 
            not self.is_prefetching):
            
            self.is_prefetching = True
            prefetch_task_id = f"prefetch_{uuid.uuid4()}"
            
            print(f"[MainController] 🔄 Starting prefetch (queue: {self.prefetched_monologues.qsize()}/{self.prefetch_queue_size}, task: {prefetch_task_id})")
            self.logger.info("Starting prefetch", 
                           task_id=prefetch_task_id,
                           queue_size=self.prefetched_monologues.qsize())
            
            # プリフェッチ用の独り言生成コマンドを発行
            command = PrepareMonologue(task_id=prefetch_task_id)
            self.event_queue.put(command)
    
    def consume_prefetch_if_available(self) -> Optional[dict]:
        """プリフェッチされた独り言があれば取得"""
        if not self.prefetched_monologues.empty():
            prefetched = self.prefetched_monologues.get_nowait()
            print(f"[MainController] ⚡ Using prefetched monologue: {prefetched['task_id']} (remaining: {self.prefetched_monologues.qsize()})")
            self.logger.info("Consuming prefetched monologue",
                           task_id=prefetched['task_id'],
                           remaining_queue_size=self.prefetched_monologues.qsize())
            return prefetched
        else:
            print("[MainController] ⏳ No prefetched monologue available, generating new one...")
        return None
    
    def add_to_prefetch_queue(self, task_id: str, sentences: list):
        """プリフェッチキューに独り言を追加"""
        prefetched_item = {
            'task_id': task_id,
            'sentences': sentences,
            'created_at': time.time()
        }
        try:
            self.prefetched_monologues.put_nowait(prefetched_item)
            self.is_prefetching = False
            
            print(f"[MainController] ✅ Added to prefetch queue: {task_id} (queue size: {self.prefetched_monologues.qsize()}/{self.prefetch_queue_size})")
            self.logger.info("Added to prefetch queue",
                            task_id=task_id,
                            queue_size=self.prefetched_monologues.qsize())
        except queue.Full:
            self.logger.warning("Prefetch queue is full. Discarding prefetched item.",
                               task_id=task_id)
            self.is_prefetching = False # キューが満杯でもフラグはリセット
        
        # 次のプリフェッチを開始
        self.start_prefetch_if_needed()

    # --- Event Handlers ---

    def handle_app_started(self, event: AppStarted):
        """アプリケーション開始時の処理"""
        self.logger.info("Handling AppStarted event.")
        # 1. 開始の挨拶を要求
        self.event_queue.put(InitialGreetingRequested())
        print("[MainController] InitialGreetingRequested has been put into queue")
        
        # 2. 挨拶完了後に独り言のプリフェッチを開始するようにスケジュール
        # テーマ朗読は挨拶の再生完了後に行う
        print("[MainController] 📋 Initial prefetch and theme reading will start after greeting completion.")

    def handle_monologue_from_theme_requested(self, event: MonologueFromThemeRequested):
        """特定のテーマファイルからモノローグを開始する。"""
        self.logger.info(f"Handling MonologueFromThemeRequested: {event.theme_file}")
        
        task_id = str(uuid.uuid4())
        self.state_manager.set_state(SystemState.THINKING, task_id, "monologue_from_theme")
        self.logger.log_state_change("idle", "thinking", task_id=task_id, task_type="monologue_from_theme")
        
        command = PrepareMonologue(task_id=task_id, theme_file=event.theme_file)
        self.event_queue.put(command)

    def handle_speech_playback_completed(self, event: SpeechPlaybackCompleted):
        """音声再生完了時の処理"""
        # --- 修正: タスクIDのミスマッチを最初にチェック ---
        if event.task_id != self.state_manager.current_task_id:
            self.logger.warning(
                "Mismatched task ID in SpeechPlaybackCompleted event. Ignoring.",
                event_task_id=event.task_id,
                current_task_id=self.state_manager.current_task_id
            )
            return

        current_task_type = self.state_manager.current_task_type
        self.logger.info(
            f"Speech playback completed for task type: {current_task_type}"
        )

        # --- 修正: まずキューイングされたコメント応答をチェック ---
        if self.queued_comment_responses:
            response = self.queued_comment_responses.pop(0)
            task_id = response['task_id']
            sentences = response['sentences']
            # --- 修正: 保存されたタスクタイプを使用 ---
            task_type = response.get('task_type', 'comment_response')
            self.logger.info("Playing queued comment response", task_id=task_id, task_type=task_type)
            self.state_manager.set_state(SystemState.SPEAKING, task_id, task_type)
            self.event_queue.put(PlaySpeech(task_id=task_id, sentences=sentences))
            return

        if current_task_type == "initial_greeting":
            self.logger.info("Initial greeting finished. Processing comments or starting theme reading.")
            comments_processed = self._process_queued_comments(task_type="post_greeting_comment_response")
            if not comments_processed:
                self.logger.info("No comments after greeting, starting theme reading.")
                self._start_theme_reading()
            return

        if current_task_type == "post_greeting_comment_response":
            self.post_greeting_response_count += 1
            self.logger.info(
                "Post-greeting comment response finished.",
                count=self.post_greeting_response_count
            )
            # 2回までコメント処理を続け、その後テーマ朗読へ
            if self.post_greeting_response_count < 2:
                comments_processed = self._process_queued_comments(task_type="post_greeting_comment_response")
                if not comments_processed:
                    self.logger.info("No more pending comments, starting theme reading early.")
                    self._start_theme_reading()
            else:
                self.logger.info("Reached post-greeting response limit (2). Starting theme reading.")
                self._start_theme_reading()
            return

        if current_task_type == "theme_intro_reading":
            self.logger.info("Theme reading completed. Checking for pending comments before prefetch.")
            self.theme_reading_completed = True
            comments_processed = self._process_queued_comments()
            if not comments_processed:
                self.logger.info("No pending comments, starting prefetch.")
                self.start_prefetch_if_needed()
                # やることがないのでIDLEに
                self.state_manager.finish_task()
            return

        if current_task_type == "comment_response":
            self.logger.info("Comment response finished. Checking for more comments.")
            comments_processed = self._process_queued_comments()
            if not comments_processed:
                self.logger.info("No more pending comments, starting prefetch if needed.")
                self.start_prefetch_if_needed()
                # やることがないのでIDLEに
                self.state_manager.finish_task()
            return
        
        if current_task_type == "monologue":
            self.logger.info("Monologue finished. Idling.")
            self.state_manager.finish_task()
            return

        # もしどのタスクタイプにも当てはまらない場合（フィラーなど）、タスクを完了させる
        self.state_manager.finish_task()

    def _process_queued_comments(self, task_type: str = "comment_response") -> bool:
        """キューイングされたコメントを処理し、処理したかどうかを返す"""
        if self.state_manager.has_pending_comments():
            self.logger.info("Processing queued comments.", task_type=task_type)
            comments = self.state_manager.get_pending_comments(clear=True)
            task_id = str(uuid.uuid4())
            # 挨拶直後のコメント返信であることをタスクタイプで示す
            self.state_manager.set_state(SystemState.THINKING, task_id, task_type)
            self.event_queue.put(PrepareCommentResponse(task_id=task_id, comments=comments))
            return True
        return False

    def _start_theme_reading(self):
        """テーマファイルの導入部分のみを読み上げる"""
        try:
            self.mode_manager.ensure_theme_loaded()

            # 1. テーマ導入部を生成・再生
            intro_sentences = self.mode_manager.get_theme_intro()
            if intro_sentences:
                self.logger.info("Starting theme introduction reading.")
                # --- 修正: 一意のタスクIDを生成し、共有する ---
                task_id = f"theme_intro_{uuid.uuid4()}"
                self.state_manager.set_state(SystemState.SPEAKING, task_id, "theme_intro_reading")
                self.audio_manager.handle_play_speech(PlaySpeech(task_id=task_id, sentences=intro_sentences))
            else:
                # 導入部がない場合は、すぐにプリフェッチを開始
                self.logger.info("No theme introduction found. Moving to prefetch.")
                self.state_manager.set_state(SystemState.IDLE)
                self.theme_reading_completed = True
                self.start_prefetch_if_needed()

        except Exception as e:
            self.logger.error(f"Failed to start theme reading: {e}")
            self.state_manager.set_state(SystemState.IDLE)

    def _schedule_next_action(self):
        """次のアクション（プリフェッチされた独り言の再生など）をスケジュールする"""
        try:
            # テーマ朗読完了後で、まだプリフェッチがない場合
            if self.theme_reading_completed and self.prefetched_monologues.empty():
                self.logger.info("Theme reading is complete, generating monologue based on the theme.")
                theme_content = self.mode_manager.get_theme_content()
                if theme_content:
                    next_task_id = str(uuid.uuid4())
                    self.state_manager.set_state(SystemState.THINKING, next_task_id, "monologue_from_theme")
                    command = PrepareMonologue(task_id=next_task_id, theme_content=theme_content)
                    self.event_queue.put(command)
                    # テーマベースの独り言を生成したら、フラグをリセットして通常の独り言モードに戻す
                    # self.theme_reading_completed = False 
                    return
            
            if self.prefetched_monologues.empty():
                # プリフェッチされた独り言がない場合は、通常の独り言生成を試みる
                next_task_id = str(uuid.uuid4())
                self.state_manager.set_state(SystemState.THINKING, next_task_id, "monologue")
                self.logger.log_state_change(
                    "idle", "thinking",
                    task_id=next_task_id,
                    task_type="monologue"
                )
                
                command = PrepareMonologue(task_id=next_task_id)
                self.event_queue.put(command)
                return
            
            # プリフェッチされた独り言があればそれを使用
            prefetched = self.consume_prefetch_if_available()
            if prefetched:
                self.logger.info(
                    "Using prefetched monologue", 
                    task_id=prefetched['task_id'],
                    processing_mode="prefetched"
                )
                
                self.state_manager.set_state(SystemState.SPEAKING, prefetched['task_id'], "monologue")
                self.logger.log_state_change(
                    "idle", "speaking", 
                    task_id=prefetched['task_id'], 
                    task_type="prefetched_monologue"
                )
                
                command = PlaySpeech(task_id=prefetched['task_id'], sentences=prefetched['sentences'])
                self.event_queue.put(command)
            else:
                # プリフェッチがない場合は通常の独り言生成
                next_task_id = str(uuid.uuid4())
                self.state_manager.set_state(SystemState.THINKING, next_task_id, "monologue")
                self.logger.log_state_change(
                    "idle", "thinking",
                    task_id=next_task_id,
                    task_type="monologue"
                )
                
                command = PrepareMonologue(task_id=next_task_id)
                self.event_queue.put(command)
            
            # 新しいプリフェッチを開始
            self.start_prefetch_if_needed()

        except Exception as e:
            self.logger.error(f"Failed to schedule monologue or filler: {e}")
            self.state_manager.set_state(SystemState.IDLE)

    def handle_monologue_ready(self, event: MonologueReady):
        """独り言の準備が完了した時の処理。"""
        task_id = event.task_id
        
        # プリフェッチタスクかどうかを判定
        if task_id.startswith("prefetch_"):
            # プリフェッチキューに追加
            print(f"[MainController] 🎯 Prefetched monologue ready: {task_id}")
            self.add_to_prefetch_queue(task_id, event.sentences)
            return
        
        print(f"[MainController] MonologueReady for task: {task_id}")
        
        # THINKING状態からSPEAKING状態に変更
        self.state_manager.set_state(SystemState.SPEAKING, task_id, "monologue")
        
        # OBSに字幕を表示
        self.obs_text_manager.handle_play_speech(PlaySpeech(task_id=task_id, sentences=event.sentences))
        
        # 準備できた文章を再生するコマンドを発行
        command = PlaySpeech(task_id=task_id, sentences=event.sentences)
        self.event_queue.put(command)

    def handle_new_comment_received(self, event: NewCommentReceived):
        """新しいコメントを受信した時の処理。"""
        comment_count = len(event.comments)
        current_state = self.state_manager.current_state.value
        
        self.logger.info("New comments received", 
                        comment_count=comment_count, 
                        current_state=current_state,
                        can_handle=self.state_manager.can_handle_comment())
        
        # 現在の状態を確認して適切に処理
        if self.state_manager.can_handle_comment():
            # すぐに処理可能な場合（IDLE状態）
            if self.state_manager.is_idle():
                self.logger.info("Processing comments immediately", 
                               processing_mode="immediate", current_state="idle")
                
                task_id = str(uuid.uuid4())
                self.state_manager.set_state(SystemState.THINKING, task_id, "comment_response")
                self.logger.log_state_change("idle", "thinking", task_id=task_id, task_type="comment_response")
                
                command = PrepareCommentResponse(task_id=task_id, comments=event.comments)
                self.event_queue.put(command)
                
            elif self.state_manager.current_state == SystemState.SPEAKING:
                # 発話中でも応答生成を並行開始
                self.logger.info("System is speaking, starting parallel comment processing", 
                               processing_mode="parallel", current_state="speaking")
                
                # 応答生成を並行して開始（状態は変更しない）
                task_id = str(uuid.uuid4())
                self.logger.info("Starting background comment response generation",
                               task_id=task_id, background_processing=True)
                
                command = PrepareCommentResponse(task_id=task_id, comments=event.comments)
                self.event_queue.put(command)
                
                # 同時に、後で適切なタイミングで再生するためキューにも追加
                for comment in event.comments:
                    self.state_manager.add_pending_comment(comment)
            
        else:
            # THINKING状態（思考中）の場合は処理待ちキューに追加
            self.logger.info("System is busy thinking, queuing comments", 
                           processing_mode="queued", reason="thinking")
            for comment in event.comments:
                self.state_manager.add_pending_comment(comment)

    def handle_comment_response_ready(self, event: CommentResponseReady):
        """コメント応答の準備が完了した時の処理。"""
        task_id = event.task_id
        current_state = self.state_manager.current_state
        
        self.logger.info("Comment response ready", 
                        task_id=task_id, current_state=current_state.value)
        
        if current_state == SystemState.THINKING:
            # 通常の処理（THINKING→SPEAKING）
            self.logger.info("Transitioning from thinking to speaking", task_id=task_id)
            
            # スマートなプリフェッチキュークリア条件
            should_clear_prefetch = self._should_clear_prefetch_on_comment_response()
            if should_clear_prefetch:
                self.clear_prefetch_queue()
                print("[MainController] Cleared prefetch queue due to context change")
            else:
                print("[MainController] Preserving prefetch queue (theme mode or minor context change)")
            
            # --- 修正: ハードコードされたタスクタイプをやめ、現在のタスクタイプを維持する ---
            current_task_type = self.state_manager.current_task_type
            self.state_manager.set_state(SystemState.SPEAKING, task_id, current_task_type)
            
            command = PlaySpeech(task_id=task_id, sentences=event.sentences)
            self.event_queue.put(command)
            
        elif current_state == SystemState.SPEAKING:
            # 並行処理で生成された応答：待機キューに保存して後で再生
            self.logger.info("Background response ready, queuing for later playback", 
                           task_id=task_id, background_processing=True)
            
            # 生成された応答を待機キューに保存
            self.queued_comment_responses.append({
                'task_id': task_id,
                'sentences': event.sentences,
                'task_type': self.state_manager.current_task_type
            })
            print(f"[MainController] Queued background comment response: {task_id} (queue size: {len(self.queued_comment_responses)})")
            
        else:
            self.logger.warning("Unexpected state for comment response", 
                              task_id=task_id, 
                              current_state=current_state.value,
                              expected_states=["THINKING", "SPEAKING"])

    def _should_clear_prefetch_on_comment_response(self) -> bool:
        """コメント応答時にプリフェッチキューをクリアすべきかを判定する
        
        Returns:
            True: プリフェッチをクリアすべき
            False: プリフェッチを保持すべき
        """
        try:
            # ModeManagerの現在のモードを確認
            if hasattr(self, 'mode_manager'):
                from murmur.handlers.mode_manager import ConversationMode
                current_mode = self.mode_manager.get_current_mode()
                
                # テーマモードの場合は基本的に保持（テーマに沿った内容を継続）
                if current_mode == ConversationMode.THEMED_MONOLOGUE:
                    print("[MainController] 🎯 Theme mode detected: preserving prefetch queue")
                    return False
                
                # 他のモードでも、アクティブなテーマがある場合は保持
                if hasattr(self.mode_manager, 'active_theme_content') and self.mode_manager.active_theme_content:
                    print("[MainController] 📖 Active theme detected: preserving prefetch queue")
                    return False
            
            # プリフェッチキューの年齢をチェック（古いものは無効化）
            prefetch_age_limit = 300  # 5分
            current_time = time.time()
            
            # キューの内容を確認し、古いものがあればクリア
            if not self.prefetched_monologues.empty():
                # キューの先頭要素の年齢をチェック（古い順に並んでいる前提）
                try:
                    # 一時的に取得してチェック（戻す）
                    temp_queue = []
                    old_items_found = False
                    
                    while not self.prefetched_monologues.empty():
                        item = self.prefetched_monologues.get_nowait()
                        item_age = current_time - item.get('created_at', 0)
                        
                        if item_age > prefetch_age_limit:
                            old_items_found = True
                            print(f"[MainController] ⏰ Discarding old prefetch item: {item['task_id']} (age: {item_age:.1f}s)")
                        else:
                            temp_queue.append(item)
                    
                    # 有効なアイテムを戻す
                    for item in temp_queue:
                        self.prefetched_monologues.put_nowait(item)
                    
                    if old_items_found:
                        print(f"[MainController] ♻️ Cleaned prefetch queue: {len(temp_queue)} items remaining")
                    
                except queue.Empty:
                    pass
            
            # 通常モードでは、キューサイズが小さい場合は保持（再生成コストを避ける）
            queue_size = self.prefetched_monologues.qsize()
            if queue_size <= 1:
                print(f"[MainController] 💡 Small prefetch queue ({queue_size}): preserving to avoid regeneration cost")
                return False
            
            # デフォルトは保持（従来の無条件クリアから変更）
            print("[MainController] 🤔 Normal mode with sufficient queue: preserving prefetch (optimized behavior)")
            return False
            
        except Exception as e:
            print(f"[MainController] Error in prefetch clear decision: {e}")
            # エラー時は安全のためクリア
            return True

    def handle_initial_greeting_requested(self, event: InitialGreetingRequested):
        """開始時の挨拶が要求された時の処理"""
        self.logger.info("Initial greeting requested")
        
        task_id = str(uuid.uuid4())
        self.state_manager.set_state(SystemState.THINKING, task_id, "initial_greeting")
        self.logger.log_state_change("idle", "thinking", task_id=task_id, task_type="initial_greeting")
        
        command = PrepareInitialGreeting(task_id=task_id)
        self.event_queue.put(command)

    def handle_ending_greeting_requested(self, event: EndingGreetingRequested):
        """終了時の挨拶が要求された時の処理"""
        self.logger.info("Ending greeting requested", 
                        bridge_text=event.bridge_text[:50] + "..." if len(event.bridge_text) > 50 else event.bridge_text,
                        stream_summary=event.stream_summary[:50] + "..." if len(event.stream_summary) > 50 else event.stream_summary)
        
        task_id = str(uuid.uuid4())
        self.state_manager.set_state(SystemState.THINKING, task_id, "ending_greeting")
        self.logger.log_state_change("idle", "thinking", task_id=task_id, task_type="ending_greeting")
        
        command = PrepareEndingGreeting(
            task_id=task_id,
            bridge_text=event.bridge_text,
            stream_summary=event.stream_summary
        )
        self.event_queue.put(command)

    def handle_initial_greeting_ready(self, event: InitialGreetingReady):
        """開始時の挨拶準備完了時の処理"""
        task_id = event.task_id
        self.logger.info("Initial greeting ready", task_id=task_id)
        
        # THINKING状態からSPEAKING状態に変更
        self.state_manager.set_state(
            SystemState.SPEAKING, task_id, "initial_greeting"
        )
        
        # 準備できた挨拶を再生するコマンドを発行
        command = PlaySpeech(task_id=task_id, sentences=event.sentences)
        self.event_queue.put(command)

    def handle_ending_greeting_ready(self, event: EndingGreetingReady):
        """終了時の挨拶準備完了時の処理"""
        task_id = event.task_id
        self.logger.info("Ending greeting ready", task_id=task_id)
        
        # THINKING状態からSPEAKING状態に変更
        self.state_manager.set_state(SystemState.SPEAKING, task_id, "ending_greeting")
        
        # 準備できた挨拶を再生するコマンドを発行
        command = PlaySpeech(task_id=task_id, sentences=event.sentences)
        self.event_queue.put(command)

    def handle_daily_summary_ready(self, event: DailySummaryReady):
        """日次要約準備完了イベントを処理する"""
        task_id = event.task_id
        self.logger.info(f"Daily summary ready. Content: {event.summary_text[:100]}...")
        
        if event.success:
            self.logger.info("Daily summary successfully generated", 
                           task_id=task_id, file_path=event.file_path)
            print(f"[MainController] 📊 日次要約が生成されました: {event.file_path}")
            print(f"[MainController] 要約内容（最初の200文字）: {event.summary_text[:200]}...")
        else:
            self.logger.error("Daily summary generation failed", 
                            task_id=task_id, error_message=event.summary_text)
            print(f"[MainController] ⚠️ 日次要約の生成に失敗しました: {event.summary_text}")
        
        # 日次要約は独立したプロセスなので、状態変更は行わない
        # 必要に応じて通知やログ出力のみ行う
    
    def handle_stream_ended(self, event: StreamEnded):
        """配信終了イベントの処理"""
        self.logger.info("Stream ended event received", 
                        stream_duration_minutes=event.stream_duration_minutes,
                        ending_reason=event.ending_reason)
        
        print(f"[MainController] 📺 配信終了イベントを受信: {event.ending_reason} ({event.stream_duration_minutes}分)")
        
        # DailySummaryHandlerに転送
        if self.daily_summary_handler:
            self.daily_summary_handler.handle_stream_ended(event)
        else:
            print("[MainController] ⚠️ DailySummaryHandler not available for stream ended event") 
    
# MainControllerでは、ModeManagerの統一テーマ管理メソッドを使用
    # _get_current_theme_file() メソッドはModeManagerに移行済み