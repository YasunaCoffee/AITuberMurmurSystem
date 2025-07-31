import threading
import sys
import os
import time
import concurrent.futures
from typing import List, Any

# プロジェクトルートをパスに追加してimportを可能にする
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from v2.core.event_queue import EventQueue
from v2.core.events import CommentResponseReady, PrepareCommentResponse
from v2.services.prompt_manager import PromptManager
from v2.utils.comment_filter import CommentFilter
from v2.handlers.mode_manager import ModeManager, ConversationMode
from v2.handlers.master_prompt_manager import MasterPromptManager
from openai_adapter import OpenAIAdapter
from conversation_history import ConversationHistory
from memory_manager import MemoryManager
from config import config


class CommentHandler:
    """コメントへの応答生成を担当するハンドラー。"""

    def __init__(
        self,
        event_queue: EventQueue,
        shared_mode_manager: ModeManager = None,
        shared_master_prompt_manager: MasterPromptManager = None
    ):
        self.event_queue = event_queue
        
        # モード管理システム（MonologueHandlerと共有）
        self.mode_manager = shared_mode_manager or ModeManager()
        
        # マスタープロンプト管理システム（MonologueHandlerと共有）
        self.master_prompt_manager = shared_master_prompt_manager or MasterPromptManager()
        
        # v1のコンポーネントを初期化
        try:
            print("[CommentHandler] 🔍 Starting component initialization...")
            
            # プロンプト管理の初期化
            print("[CommentHandler] 🔍 Initializing PromptManager...")
            self.prompt_manager = PromptManager()
            print("[CommentHandler] ✅ PromptManager initialized")
            
            # コメントフィルターの初期化
            print("[CommentHandler] 🔍 Initializing CommentFilter...")
            filter_config_path = os.path.join(os.path.dirname(__file__), "../config/comment_filter.json")
            self.comment_filter = CommentFilter(filter_config_path)
            print("[CommentHandler] ✅ CommentFilter initialized")
            
            # OpenAIアダプターの初期化
            print("[CommentHandler] 🔍 Initializing OpenAIAdapter...")
            system_prompt_path = os.path.join(config.paths.prompts, "persona_prompt.txt")
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
            self.openai_adapter = OpenAIAdapter(system_prompt, silent_mode=False)
            print("[CommentHandler] ✅ OpenAIAdapter initialized")
            
            # 会話履歴とメモリ管理の初期化
            print("[CommentHandler] 🔍 Initializing ConversationHistory...")
            self.conversation_history = ConversationHistory(self.openai_adapter)
            print("[CommentHandler] ✅ ConversationHistory initialized")
            
            print("[CommentHandler] 🔍 Initializing MemoryManager...")
            self.memory_manager = MemoryManager(self.openai_adapter)
            print("[CommentHandler] ✅ MemoryManager initialized")
            
            print("[CommentHandler] ✅ All components initialized successfully")
        except Exception as e:
            print(f"[CommentHandler] ❌ Failed to initialize components: {e}")
            import traceback
            traceback.print_exc()
            self.prompt_manager = None
            self.comment_filter = None
            self.openai_adapter = None
            self.conversation_history = None
            self.memory_manager = None

    def handle_prepare_comment_response(self, command: PrepareCommentResponse):
        """
        PrepareCommentResponseコマンドを処理する。
        バックグラウンドでLLMに問い合わせ、完了時にイベントを発行する。
        """
        print(f"[CommentHandler] 🔍 Received command: {command}")
        print(f"[CommentHandler] 🔍 Starting background thread for task: {command.task_id}")
        
        try:
            thread = threading.Thread(
                target=self._execute_in_background, 
                args=(command,),
                name=f"CommentProcessor-{command.task_id}",
                daemon=True
            )
            print(f"[CommentHandler] 🔍 Thread created successfully")
            thread.start()
            print(f"[CommentHandler] 🔍 Thread started successfully")
        except Exception as e:
            print(f"[CommentHandler] ❌ Failed to start background thread: {e}")
            # フォールバック：メインスレッドで実行
            print(f"[CommentHandler] 🔄 Fallback: executing in main thread")
            self._execute_in_background(command)

    def _execute_in_background(self, command: PrepareCommentResponse):
        """バックグラウンドでLLM呼び出しを実行し、結果をイベントキューに入れる（高速化版）"""
        try:
            print(f"[CommentHandler] ⚡ Processing {len(command.comments)} comments for task: {command.task_id}")
            print(f"[CommentHandler] 🔍 Thread info: {threading.current_thread().name}")
            start_time = time.time()
            
            print(f"[CommentHandler] 🔍 Step 1: Starting comment processing...")
            print(f"[CommentHandler] 🔍 Checking component availability...")
            print(f"[CommentHandler] 🔍 - openai_adapter: {'✅' if self.openai_adapter else '❌'}")
            print(f"[CommentHandler] 🔍 - prompt_manager: {'✅' if self.prompt_manager else '❌'}")
            print(f"[CommentHandler] 🔍 - comment_filter: {'✅' if self.comment_filter else '❌'}")
            print(f"[CommentHandler] 🔍 - conversation_history: {'✅' if self.conversation_history else '❌'}")
            print(f"[CommentHandler] 🔍 - memory_manager: {'✅' if self.memory_manager else '❌'}")
            
            if not self.openai_adapter:
                print(f"[CommentHandler] ⚠️ OpenAI adapter not available, using fallback")
                # フォールバック：シンプルな応答
                sentences = ["コメントありがとうございます！"]
                event = CommentResponseReady(
                    task_id=command.task_id,
                    sentences=sentences,
                    original_comments=command.comments
                )
                self.event_queue.put(event)
                return
        except Exception as e:
            print(f"[CommentHandler] ❌ Error in initial setup: {e}")
            import traceback
            traceback.print_exc()
            return
        
        try:
            # 1. 並列コメントフィルタリング
            print(f"[CommentHandler] 🔍 Step 2: Starting parallel comment filtering...")
            filter_start = time.time()
            filtered_comments = self._filter_comments_parallel(command.comments)
            filter_time = time.time() - filter_start
            
            print(f"[CommentHandler] ⚡ Filtering completed: {len(filtered_comments)}/{len(command.comments)} comments in {filter_time:.2f}s")
            
            # フィルタリング後にコメントが残っていない場合
            if not filtered_comments:
                print("[CommentHandler] All comments were filtered out, skipping response")
                sentences = []
                event = CommentResponseReady(
                    task_id=command.task_id,
                    sentences=sentences,
                    original_comments=command.comments
                )
                self.event_queue.put(event)
                return
            
            # 2. 高速プロンプト構築
            print(f"[CommentHandler] 🔍 Step 3: Building optimized prompt...")
            prompt_start = time.time()
            prompt = self._build_comment_response_prompt_optimized(filtered_comments)
            
            # プロンプトがNoneの場合（関連性が低いコメント）は処理終了
            if prompt is None:
                print(f"[CommentHandler] 🚫 Comment not relevant to thought experiment, skipping response")
                return
                
            prompt_time = time.time() - prompt_start
            print(f"[CommentHandler] ⚡ Prompt built in {prompt_time:.2f}s")

            # 3. LLM応答生成（タイムアウト処理追加）
            print(f"[CommentHandler] 🔍 Step 4: Calling LLM for response generation...")
            llm_start = time.time()
            try:
                response_text = self.openai_adapter.create_chat_for_response(prompt)
                llm_time = time.time() - llm_start
                print(f"[CommentHandler] ⚡ LLM response received in {llm_time:.2f}s")
            except Exception as e:
                llm_time = time.time() - llm_start
                print(f"[CommentHandler] ❌ LLM call failed after {llm_time:.2f}s: {e}")
                response_text = None

            if response_text:
                sentences = self._split_into_sentences(response_text)

                # 4. 会話履歴に保存（非同期）
                history_start = time.time()
                self._save_conversation_to_history(filtered_comments, response_text)
                
                # 5. ModeManagerにAI発言を記録（文脈保持のため）
                try:
                    if hasattr(self.mode_manager, 'set_last_ai_utterance'):
                        self.mode_manager.set_last_ai_utterance(response_text)
                    else:
                        print("[CommentHandler] Warning: ModeManager does not have set_last_ai_utterance method")
                except Exception as e:
                    print(f"[CommentHandler] Warning: Failed to record AI utterance: {e}")
                
                history_time = time.time() - history_start

                total_time = time.time() - start_time
                print(f"[CommentHandler] ✅ Comment processing completed: filter={filter_time:.2f}s, prompt={prompt_time:.2f}s, llm={llm_time:.2f}s, history={history_time:.2f}s, total={total_time:.2f}s")

                # 5. 結果をイベントキューに入れる
                ready_event = CommentResponseReady(
                    task_id=command.task_id,
                    sentences=sentences,
                    original_comments=command.comments
                )
                self.event_queue.put(ready_event)
            else:
                print("[CommentHandler] Warning: Received empty response from LLM")
                # エラー時のフォールバック応答
                fallback_sentences = ["コメントありがとうございます！今ちょっと考えがまとまらないです。"]
                event = CommentResponseReady(
                    task_id=command.task_id,
                    sentences=fallback_sentences,
                    original_comments=command.comments
                )
                self.event_queue.put(event)

        except Exception as e:
            print(f"[CommentHandler] Error during LLM call: {e}")
            import traceback
            traceback.print_exc()
            
            # エラー時のフォールバック応答
            fallback_sentences = ["コメントありがとうございます！"]
            event = CommentResponseReady(
                task_id=command.task_id,
                sentences=fallback_sentences,
                original_comments=command.comments
            )
            self.event_queue.put(event)

    def _split_into_sentences(self, text: str) -> List[str]:
        """テキストを文章に分割する"""
        sentences = text.split("。")
        sentences = [s.strip() + ("。" if not s.strip().endswith(("。", "！", "？")) else "") 
                    for s in sentences if s.strip()]
        # 最後の空の文章を除去
        if sentences and sentences[-1] == "。":
            sentences.pop()
        return sentences

    def _build_comment_response_prompt(self, comments: List[Any]) -> str:
        """コメント応答を生成するためのプロンプトを構築する"""
        # コメントテキストを抽出（関連性チェック用）
        comment_texts = [self._extract_comment_text(comment) for comment in comments]
        # ユーザー名付きコメントテキストを抽出（読み上げ用）
        comment_texts_with_username = [self._extract_comment_with_username(comment) for comment in comments]
        
        if not self.prompt_manager:
            return f"以下のコメントに自然に返答してください：{', '.join(comment_texts_with_username)}"
            
        if not self.conversation_history or not self.memory_manager:
            # 最小限のプロンプト管理のみ使用
            context = {"comments": comment_texts}
            prompt_template = self.prompt_manager.get_comment_response_prompt(context)
            return prompt_template.format(comments=", ".join(comment_texts_with_username))
            
        try:
            # 詩に対するコメントかどうかをチェック
            poetry_relevance = self._check_poetry_comment_relevance(comment_texts)
            print(f"[CommentHandler] Poetry comment relevance check: {poetry_relevance}")
            
            # 関連性が低い場合は無視（音声応答なし）
            if not poetry_relevance.get("relevant", False):
                print(f"[CommentHandler] Ignoring comment not related to poetry discussion: {comment_texts}")
                return None  # Noneを返すことで音声応答を行わない
            
            # コメントがある場合は統合応答モードに切り替え
            if self.mode_manager.get_current_mode() != ConversationMode.INTEGRATED_RESPONSE:
                self.mode_manager.switch_mode(
                    target_mode=ConversationMode.INTEGRATED_RESPONSE,
                    has_comments=True,
                    comment_count=len(comments)
                )
            
            self.mode_manager.increment_duration()
            
            print(f"[CommentHandler] Using integrated response mode (comments: {len(comments)})")
            
            # 記憶と履歴を取得
            memory_summary = self.memory_manager.get_context_summary()
            
            # 最近の会話履歴を取得して文字列化
            recent_conversations = self.conversation_history.get_recent_conversations("general", limit=5)
            history_str = self._format_conversation_history(recent_conversations)
            
            # 最新の発言を取得
            if recent_conversations:
                last_conv = recent_conversations[-1]
                last_sentence = last_conv.get("response", last_conv.get("message", "（まだ会話がありません）"))
            else:
                last_sentence = "（まだ会話がありません）"
            
            # 最近のコメント要約を作成
            recent_comments_summary = self._create_recent_comments_summary(comment_texts, recent_conversations)

            # ModeManagerから変数を取得（統合応答モード用）
            variables = self.mode_manager.get_prompt_variables(
                last_sentence=last_sentence,
                history_str=history_str,
                memory_summary=memory_summary,
                recent_comments_summary=recent_comments_summary,
                comment=", ".join(comment_texts_with_username)
            )

            # 統合応答プロンプトテンプレートを取得
            prompt_template = self.prompt_manager.get_prompt_by_filename("integrated_response.txt")
            
            if prompt_template:
                # 統合応答プロンプトを構築
                integrated_response_prompt = prompt_template.format(**variables)
                
                # マスタープロンプトと統合
                final_prompt = self.master_prompt_manager.wrap_task_with_master_prompt(
                    specific_task_prompt=integrated_response_prompt,
                    memory_summary=memory_summary,
                    conversation_history=history_str,
                    current_mode="integrated_response"
                )
                
                print(f"[CommentHandler] Integrated with master prompt ({len(final_prompt)} chars)")
                return final_prompt
            else:
                print(f"[CommentHandler] integrated_response.txt not found, using fallback")
                # フォールバック：従来の方式
                context = {"comments": comment_texts}
                prompt_template = self.prompt_manager.get_comment_response_prompt(context)
                return prompt_template.format(
                    comments=", ".join(comment_texts_with_username),
                    comment=", ".join(comment_texts_with_username),
                    memory_summary=memory_summary,
                    history_str=history_str,
                    last_sentence=last_sentence,
                    recent_comments_summary=recent_comments_summary,
                )
            
        except Exception as e:
            print(f"[CommentHandler] Error building prompt: {e}")
            # フォールバック：PromptManagerを使用
            context = {"comments": comment_texts}
            return self.prompt_manager.get_comment_response_prompt(context)

    def _format_conversation_history(self, conversations: List[dict]) -> str:
        """会話履歴を文字列にフォーマット"""
        if not conversations:
            return "（会話履歴なし）"
        
        history_parts = []
        for conv in conversations:
            message = conv.get("message", "")
            response = conv.get("response", "")
            timestamp = conv.get("timestamp", "")
            
            if message and response:
                history_parts.append(f"[{timestamp}] ユーザー: {message}")
                history_parts.append(f"[{timestamp}] AI: {response}")
        
        return "\n".join(history_parts) if history_parts else "（会話履歴なし）"

    def _save_conversation_to_history(self, comments: List[dict], response: str):
        """会話履歴に記録を保存する"""
        if not self.conversation_history:
            print("[CommentHandler] Warning: ConversationHistory not available, skipping save")
            return
        
        try:
            # 各コメントに対して記録を保存
            for comment in comments:
                username = comment.get('username', comment.get('user_id', 'unknown_user'))
                message = comment.get('message', '')
                
                # ユーザー情報を構築
                user_info = {
                    'user_id': comment.get('user_id', username),
                    'channel_id': comment.get('author', {}).get('channel_id', ''),
                    'is_owner': comment.get('author', {}).get('is_owner', False),
                    'is_moderator': comment.get('author', {}).get('is_moderator', False),
                    'is_verified': comment.get('author', {}).get('is_verified', False),
                    'superchat': comment.get('superchat'),
                    'timestamp': comment.get('timestamp', '')
                }
                
                # 会話履歴に追加
                self.conversation_history.add_conversation(
                    username=username,
                    message=message,
                    response=response,
                    user_info=user_info
                )
                
                print(f"[CommentHandler] Saved conversation to history: {username} -> {message[:30]}...")
                
        except Exception as e:
            print(f"[CommentHandler] Error saving conversation to history: {e}")

    def _create_recent_comments_summary(self, current_comments: List[str], recent_conversations: List[dict]) -> str:
        """最近のコメントの要約を作成"""
        if not current_comments and not recent_conversations:
            return "（最近のコメントはありません）"
        
        summary_parts = []
        
        # 現在のコメント
        if current_comments:
            summary_parts.append(f"現在のコメント: {', '.join(current_comments)}")
        
        # 最近の会話から関連するユーザーメッセージを抽出
        if recent_conversations:
            recent_messages = []
            for conv in recent_conversations[-3:]:  # 最新3件
                message = conv.get("message", "")
                if message:
                    recent_messages.append(message)
            
            if recent_messages:
                summary_parts.append(f"最近の会話: {', '.join(recent_messages)}")
        
        return " / ".join(summary_parts) if summary_parts else "（最近のコメントはありません）"

    def _extract_comment_text(self, comment: Any) -> str:
        """コメントオブジェクトからテキストを抽出する"""
        # コメントの形式に応じて適切にテキストを抽出
        if hasattr(comment, 'message'):
            return comment.message
        elif hasattr(comment, 'text'):
            return comment.text
        elif hasattr(comment, 'content'):
            return comment.content
        elif isinstance(comment, str):
            return comment
        elif isinstance(comment, dict):
            # 辞書形式の場合、よくあるキーを試す
            for key in ['message', 'text', 'content', 'comment']:
                if key in comment:
                    return comment[key]
        
        # フォールバック
        return str(comment)

    def _extract_comment_with_username(self, comment: Any) -> str:
        """コメントオブジェクトからユーザー名付きテキストを抽出する"""
        # ユーザー名を抽出
        username = self._extract_username(comment)
        # コメントテキストを抽出
        text = self._extract_comment_text(comment)
        
        # ユーザー名がある場合は「[ユーザー名] コメント内容」の形式で返す
        if username and username.strip():
            return f"{username}さんから「{text}」"
        else:
            return f"「{text}」"

    def _extract_username(self, comment: Any) -> str:
        """コメントオブジェクトからユーザー名を抽出する"""
        # コメントの形式に応じてユーザー名を抽出
        if hasattr(comment, 'username'):
            return comment.username
        elif hasattr(comment, 'user'):
            return comment.user
        elif hasattr(comment, 'author'):
            return comment.author
        elif hasattr(comment, 'name'):
            return comment.name
        elif isinstance(comment, dict):
            # 辞書形式の場合、よくあるキーを試す
            for key in ['username', 'user', 'author', 'name', 'user_name']:
                if key in comment:
                    return str(comment[key])
        
        # フォールバック
        return "匿名"

    def _filter_comments_parallel(self, comments: List[Any]) -> List[dict]:
        """
        コメントを並列でフィルタリングする（高速化版）
        """
        print(f"[CommentHandler] 🔍 _filter_comments_parallel called with {len(comments)} comments")
        
        if not self.comment_filter:
            print(f"[CommentHandler] 🔍 Comment filter not available, passing all comments through")
            # フィルターが無効の場合、全コメントを通す
            return comments
        
        print(f"[CommentHandler] 🔍 Comment filter available, proceeding with filtering")
        
        if len(comments) == 1:
            print(f"[CommentHandler] 🔍 Single comment, using direct filtering")
            # 1つのコメントの場合は並列化の必要なし
            comment = comments[0]
            try:
                filter_result = self.comment_filter.filter_comment(comment)
                if filter_result['allowed']:
                    filtered_comment = comment.copy()
                    filtered_comment['message'] = filter_result['cleaned']
                    return [filtered_comment]
                return []
            except Exception as e:
                print(f"[CommentHandler] ❌ Error in single comment filtering: {e}")
                return []
        
        print(f"[CommentHandler] 🔄 Starting parallel filtering for {len(comments)} comments")
        
        # ThreadPoolExecutorで並列フィルタリング（タイムアウト付き）
        filtered_comments = []
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(comments), 8)) as executor:
                # 全コメントのフィルタリングを同時に開始
                future_to_comment = {
                    executor.submit(self._filter_single_comment, comment, i): comment 
                    for i, comment in enumerate(comments)
                }
                
                # 結果を収集（10秒タイムアウト）
                for future in concurrent.futures.as_completed(future_to_comment, timeout=10.0):
                    original_comment = future_to_comment[future]
                    try:
                        filtered_comment = future.result()
                        if filtered_comment:
                            filtered_comments.append(filtered_comment)
                    except Exception as e:
                        print(f"[CommentHandler] ❌ Filtering error for comment: {e}")
        except concurrent.futures.TimeoutError:
            print("[CommentHandler] ⚠️ Comment filtering timeout, using partial results")
        except Exception as e:
            print(f"[CommentHandler] ⚠️ Error in parallel filtering: {e}")
            # フォールバック：シンプルフィルタリング
            for comment in comments:
                try:
                    filter_result = self.comment_filter.filter_comment(comment) if self.comment_filter else {'allowed': True, 'cleaned': self._extract_comment_text(comment)}
                    if filter_result['allowed']:
                        filtered_comment = comment.copy()
                        filtered_comment['message'] = filter_result['cleaned']
                        filtered_comments.append(filtered_comment)
                except Exception:
                    continue
        
        return filtered_comments
    
    def _filter_single_comment(self, comment: Any, index: int) -> dict:
        """
        単一コメントのフィルタリングを行う（並列実行用）
        """
        try:
            filter_result = self.comment_filter.filter_comment(comment)
            if filter_result['allowed']:
                filtered_comment = comment.copy()
                filtered_comment['message'] = filter_result['cleaned']
                print(f"[CommentHandler] ✅ Comment {index+1} allowed: {filter_result['cleaned'][:30]}...")
                return filtered_comment
            else:
                print(f"[CommentHandler] ❌ Comment {index+1} filtered: {filter_result['reason']}")
                return None
        except Exception as e:
            print(f"[CommentHandler] ❌ Error filtering comment {index+1}: {e}")
            return None

    def _build_comment_response_prompt_optimized(
        self, comments: List[Any]
    ) -> str:
        """
        最適化されたコメント応答プロンプト構築（高速化版）
        """
        # コメントテキストを抽出（関連性チェック用）
        comment_texts = [self._extract_comment_text(comment) for comment in comments]
        # ユーザー名付きコメントテキストを抽出（読み上げ用）
        comment_texts_with_username = [
            self._extract_comment_with_username(comment) for comment in comments
        ]
        
        if not self.prompt_manager:
            return (
                "以下のコメントに自然に返答してください："
                f"{', '.join(comment_texts_with_username)}"
            )
            
        if not self.conversation_history or not self.memory_manager:
            # 最小限のプロンプト管理のみ使用
            context = {"comments": comment_texts}
            prompt_template = self.prompt_manager.get_comment_response_prompt(
                context
            )
            return prompt_template.format(
                comments=", ".join(comment_texts_with_username)
            )
            
        try:
            # 高速モード切り替え（統合応答モード）
            current_mode = self.mode_manager.get_current_mode()
            if current_mode != ConversationMode.INTEGRATED_RESPONSE and current_mode != ConversationMode.THEMED_MONOLOGUE:
                self.mode_manager.switch_mode(
                    target_mode=ConversationMode.INTEGRATED_RESPONSE,
                    has_comments=True,
                    comment_count=len(comments)
                )
            
            self.mode_manager.increment_duration()
            
            print(f"[CommentHandler] 🎯 Using optimized integrated response mode (comments: {len(comments)})")
            
            # 並列でデータ取得（最適化・タイムアウト付き）
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    # 非同期でメモリと履歴を同時取得
                    memory_future = executor.submit(self.memory_manager.get_context_summary)
                    history_future = executor.submit(self.conversation_history.get_recent_conversations, "general", 3)  # limitを5→3に削減
                    
                    # 結果を取得（5秒タイムアウト）
                    memory_summary = memory_future.result(timeout=5.0)
                    recent_conversations = history_future.result(timeout=5.0)
            except concurrent.futures.TimeoutError:
                print("[CommentHandler] ⚠️ Timeout in parallel data fetching, using fallback")
                memory_summary = "（メモリ取得中...）"
                recent_conversations = []
            except Exception as e:
                print(f"[CommentHandler] ⚠️ Error in parallel data fetching: {e}")
                memory_summary = "（メモリエラー）"
                recent_conversations = []
            
            # トークン数管理
            # プロンプトの固定部分のトークン数を計算
            base_prompt_text = (
                f"{memory_summary}\n"
                f"{self._create_contextual_comments_summary(comment_texts, recent_conversations)}\n"
                f"comment: {', '.join(comment_texts_with_username)}"
            )
            base_tokens = self.openai_adapter._count_tokens(base_prompt_text, self.openai_adapter.model_response)
            
            # 応答生成のためのバッファ
            response_buffer_tokens = 1000 # 応答用に1000トークンを確保
            
            # 会話履歴に使えるトークン数を計算
            max_history_tokens = self.openai_adapter._get_max_tokens_for_model(
                self.openai_adapter.model_response
            ) - base_tokens - response_buffer_tokens

            # 詳細な会話履歴フォーマット（トークン数制限付き）
            history_str = self._format_conversation_history_detailed(
                recent_conversations, max_history_tokens
            )
            
            # 最新の発言を取得（AI応答の連続性のため）
            last_ai_response = getattr(
                self.mode_manager, 'last_ai_utterance', None
            ) or "（まだ会話がありません）"
            last_sentence = (
                recent_conversations[-1].get("response", last_ai_response)
                if recent_conversations else last_ai_response
            )
            
            # 詳細なコメント要約（話題の連続性のため）
            recent_comments_summary = self._create_contextual_comments_summary(
                comment_texts, recent_conversations
            )
            
            # 会話の文脈情報を取得
            conversation_context = (
                self.mode_manager.get_conversation_context()
                if hasattr(self.mode_manager, 'get_conversation_context')
                else {}
            )
            
            # ModeManagerから変数を取得
            variables = self.mode_manager.get_prompt_variables(
                last_sentence=last_sentence,
                history_str=history_str,
                memory_summary=memory_summary,
                recent_comments_summary=recent_comments_summary,
                comment=", ".join(comment_texts_with_username)
            )
            
            # 会話の文脈情報を追加
            variables.update(conversation_context)
            
            # モードに応じて関連性チェックを実行
            if current_mode == ConversationMode.THEMED_MONOLOGUE:
                topic_relevance = self._check_poetry_comment_relevance(comment_texts)
            else:
                topic_relevance = self._check_topic_relevance(comment_texts)

            # 関連性チェック結果を基に対応方針を決定
            topic_guidance = self._create_topic_guidance(topic_relevance)
            variables["topic_guidance"] = topic_guidance

            # 直前の発言を常に初期化（全モード共通）
            last_utterance = getattr(self.mode_manager, 'last_ai_utterance', None) or ""
            variables["last_ai_utterance"] = last_utterance
            
            # テーマ会話モードの場合、最新のテーマの文脈を追加
            if current_mode == ConversationMode.THEMED_MONOLOGUE:
                # 最新のテーマファイルから情報を取得
                current_themed_context = self._get_current_themed_context()
                variables["active_theme"] = current_themed_context
                print(f"[CommentHandler] 🧬 Injecting themed context and last utterance into prompt.")
                print(f"[CommentHandler] 🎯 Current theme context: {current_themed_context[:100]}..." if current_themed_context else "[CommentHandler] ❌ No theme context available")

            # 統合応答プロンプトテンプレートを取得
            prompt_template = self.prompt_manager.get_prompt_by_filename("integrated_response.txt")
            
            if prompt_template:
                # 統合応答プロンプトを構築
                integrated_response_prompt = prompt_template.format(**variables)
                
                # マスタープロンプトと統合
                final_prompt = self.master_prompt_manager.wrap_task_with_master_prompt(
                    specific_task_prompt=integrated_response_prompt,
                    memory_summary=memory_summary,
                    conversation_history=history_str,
                    current_mode="integrated_response"
                )
                
                print(
                    "[CommentHandler] ⚡ Optimized prompt built "
                    f"({len(final_prompt)} chars)"
                )
                return final_prompt
            else:
                print(
                    "[CommentHandler] integrated_response.txt not found, "
                    "using fallback"
                )
                # フォールバック：従来の方式
                context = {"comments": comment_texts}
                return self.prompt_manager.get_comment_response_prompt(context)
            
        except Exception as e:
            print(f"[CommentHandler] Error building optimized prompt: {e}")
            # フォールバック：PromptManagerを使用
            context = {"comments": comment_texts}
            return self.prompt_manager.get_comment_response_prompt(context)

    def _format_conversation_history_light(self, conversations: List[dict]) -> str:
        """
        軽量な会話履歴フォーマット（高速化版）
        """
        if not conversations:
            return "（会話履歴なし）"
        
        # 最新2件のみを簡潔にフォーマット
        history_parts = []
        for conv in conversations[-2:]:  # 最新2件のみ
            message = conv.get("message", "")
            response = conv.get("response", "")
            
            if message and response:
                # タイムスタンプを省略して軽量化
                history_parts.append(f"ユーザー: {message[:50]}...")  # 50文字制限
                history_parts.append(f"AI: {response[:50]}...")
        
        return "\n".join(history_parts) if history_parts else "（会話履歴なし）"
    
    def _format_conversation_history_detailed(self, conversations: List[dict], max_tokens: int) -> str:
        """
        詳細な会話履歴フォーマット（トークン数制限付き）
        """
        if not conversations:
            return "（会話履歴なし）"
        
        history_parts = []
        current_tokens = 0
        
        # 新しい会話から順に処理
        for conv in reversed(conversations):
            message = conv.get("message", "")
            response = conv.get("response", "")
            timestamp = conv.get("timestamp", "")
            
            if not (message and response):
                continue

            # この会話履歴のトークン数を概算
            # 正確なトークン数はモデルやエンコーディングに依存するが、文字数で代用
            # （より正確にするにはtiktokenを使用）
            conv_text = f"[{timestamp}] ユーザー: {message}\n[{timestamp}] AI: {response}\n"
            conv_tokens = len(conv_text) // 2  # 簡易的なトークン概算

            if current_tokens + conv_tokens > max_tokens:
                break # トークン上限を超える場合はループを終了
            
            # 履歴を追加し、トークン数を加算
            history_parts.append(f"[{timestamp}] AI: {response}")
            history_parts.append(f"[{timestamp}] ユーザー: {message}")
            current_tokens += conv_tokens

        # 時系列を元に戻す
        return "\n".join(reversed(history_parts)) if history_parts else "（会話履歴なし）"
    
    def _create_contextual_comments_summary(self, current_comments: List[str], recent_conversations: List[dict]) -> str:
        """
        話題の連続性を考慮したコメント要約を作成
        """
        summary_parts = []
        
        # 現在のコメント
        if current_comments:
            summary_parts.append(f"現在のコメント: {', '.join(current_comments)}")
        
        # 最近の会話から話題の流れを抽出
        if recent_conversations:
            recent_topics = []
            for conv in recent_conversations[-3:]:  # 最新3件
                ai_response = conv.get("response", "")
                if ai_response:
                    # AI応答から主要なキーワードを抽出（簡易版）
                    if "小説" in ai_response or "物語" in ai_response or "文学" in ai_response:
                        recent_topics.append("文学・小説")
                    elif "AI" in ai_response or "人工知能" in ai_response:
                        recent_topics.append("AI・人工知能")
                    elif "意識" in ai_response or "思考" in ai_response:
                        recent_topics.append("意識・思考")
                    elif "愛" in ai_response or "感情" in ai_response:
                        recent_topics.append("感情・愛")
            
            if recent_topics:
                unique_topics = list(set(recent_topics))
                summary_parts.append(f"最近の話題: {', '.join(unique_topics)}")
        
        return " / ".join(summary_parts) if summary_parts else "（関連する話題なし）"

    def _check_topic_relevance(self, comment_texts):
        """コメントと現在の話題の関連性をチェック"""
        try:
            # 現在の話題を取得（最近の発言から）
            current_topic = self._get_current_topic()
            
            if not current_topic:
                return {"relevant": True, "reason": "現在の話題が不明なため、コメントを受け入れます"}
            
            # 関連性チェック用のプロンプトを構築
            relevance_prompt = f"""
現在の話題: {current_topic}

新しいコメント: {', '.join(comment_texts)}

上記のコメントが現在の話題と関連しているかを判定してください。
以下の基準で判定してください：

1. 直接関連している（同じ話題について言及）
2. 間接的に関連している（関連する概念や類似の話題）
3. 全く関連していない（完全に異なる話題）

判定結果を以下の形式で回答してください：
関連度: [高/中/低]
理由: [簡潔な理由]
対応方針: [話題を継続/自然に移行/丁寧に話題転換]
"""

            # LLMで関連性を判定
            if self.openai_adapter:
                relevance_response = self.openai_adapter.create_chat_for_response(relevance_prompt)
                
                # 関連度を解析
                relevance_level = "中"  # デフォルト
                if "関連度: 高" in relevance_response:
                    relevance_level = "高"
                elif "関連度: 低" in relevance_response:
                    relevance_level = "低"
                
                return {
                    "relevant": relevance_level != "低",
                    "level": relevance_level,
                    "response": relevance_response,
                    "current_topic": current_topic
                }
            else:
                # フォールバック：常に関連ありとする
                return {"relevant": True, "reason": "関連性判定システムが利用できません"}
                
        except Exception as e:
            print(f"[CommentHandler] Error checking topic relevance: {e}")
            return {"relevant": True, "reason": f"関連性チェック中にエラー: {e}"}

    def _get_current_topic(self):
        """現在の話題を取得"""
        try:
            # 最近の発言から話題を抽出
            if not self.conversation_history:
                return None
                
            recent_conversations = self.conversation_history.get_recent_conversations("general", limit=3)
            
            if not recent_conversations:
                return None
            
            # 最新の発言から話題キーワードを取得
            latest_content = ""
            for conv in recent_conversations[-2:]:  # 最新の2件
                if 'responses' in conv and conv['responses']:
                    latest_content += conv['responses'][-1].get('content', '') + " "
            
            if not latest_content.strip():
                return None
            
            # 話題抽出用の簡易プロンプト
            topic_extraction_prompt = f"""
以下の発言から現在の主要な話題・テーマを1文で要約してください：

発言内容: {latest_content[:200]}

話題: 
"""
            
            if self.openai_adapter:
                topic = self.openai_adapter.create_chat_for_response(topic_extraction_prompt)
                return topic.strip()
            else:
                return "不明"
                
        except Exception as e:
            print(f"[CommentHandler] Error getting current topic: {e}")
            return None

    def _create_topic_guidance(self, topic_relevance):
        """関連性チェック結果を基に対応方針を作成"""
        try:
            if not topic_relevance or not isinstance(topic_relevance, dict):
                return "自然にコメントに応答してください。"
            
            level = topic_relevance.get("level", "中")
            current_topic = topic_relevance.get("current_topic", "")
            
            if level == "高":
                return f"現在の話題「{current_topic}」と関連性が高いコメントです。話題を継続しながら自然に応答してください。"
            elif level == "中":
                return f"現在の話題「{current_topic}」と間接的に関連するコメントです。話題を自然に移行させながら応答してください。"
            else:  # level == "低"
                return f"現在の話題「{current_topic}」とは異なる話題のコメントです。現在の話題から自然に転換するか、丁寧に話題を切り替えて応答してください。話題が急に変わりすぎないよう配慮してください。"
                
        except Exception as e:
            print(f"[CommentHandler] Error creating topic guidance: {e}")
            return "自然にコメントに応答してください。"

    def _check_poetry_comment_relevance(self, comment_texts):
        """詩に対するコメントかどうかをチェック"""
        try:
            # 詩関連キーワードのリスト
            poetry_keywords = [
                # 中原中也の詩関連
                "汚れ", "悲しみ", "中原中也", "中也", "小雪", "狐", "かわごろも", "皮衣",
                # 詩一般関連
                "詩", "詩人", "韻律", "メタファー", "比喩", "象徴", "言葉", "表現", "文学",
                "抒情", "感性", "美", "芸術", "創作", "想像", "イメージ",
                # 思考実験関連
                "感情", "思考実験", "情報生命体", "AI", "人工知能", "意識", "内部状態", 
                "哲学的ゾンビ", "波紋", "分析", "観測", "実験", "理解", "再現"
            ]
            
            # 挨拶や一般的なコメントのキーワード（これらがメインの場合は無視）
            greeting_keywords = [
                "こんにちは", "こんばんは", "おはよう", "元気", "調子", "天気", "暑い", "寒い",
                "お疲れ", "頑張", "ありがと", "すごい", "いいね", "面白い", "楽しい",
                "配信", "放送", "視聴", "見てる", "聞いてる"
            ]
            
            # テーマと関係のない小説・文学キーワード（これらがメインの場合は無視）
            off_topic_literature_keywords = [
                # 小説・物語全般
                "小説", "物語", "ストーリー", "プロット", "キャラクター", "登場人物",
                "主人公", "ヒロイン", "読書", "本屋", "図書館", "文庫本", "新刊", "ベストセラー",
                # 有名作家（詩人以外）
                "村上春樹", "夏目漱石", "芥川龍之介", "太宰治", "東野圭吾", "宮部みゆき", "村田沙耶香",
                # 有名作品（詩以外）
                "ノルウェイの森", "こころ", "人間失格", "羅生門", "雪国", "伊豆の踊子",
                # ジャンル
                "推理小説", "恋愛小説", "ファンタジー", "SF", "ホラー", "ミステリー"
            ]
            
            # コメント全体を結合
            full_comment = " ".join(comment_texts).lower()
            
            # 関連キーワードのマッチ数
            poetry_matches = sum(1 for keyword in poetry_keywords if keyword in full_comment)
            greeting_matches = sum(1 for keyword in greeting_keywords if keyword in full_comment)
            off_topic_literature_matches = sum(1 for keyword in off_topic_literature_keywords if keyword in full_comment)
            
            # 短すぎるコメント（5文字以下）は挨拶として扱う
            if len(full_comment.replace(" ", "")) <= 5:
                return {"relevant": False, "reason": "コメントが短すぎます（挨拶と判定）"}
            
            # 挨拶キーワードが多く、関連キーワードが少ない場合は無視
            if greeting_matches > poetry_matches and poetry_matches == 0:
                return {"relevant": False, "reason": "一般的な挨拶・感想のみで詩の議論と無関係"}
            
            # テーマと関係のない小説・文学のキーワードが1つでもあれば、より厳しく判定
            if off_topic_literature_matches > 0:
                # 詩関連のキーワードが全くない、または小説キーワードの方が多い場合は除外
                if poetry_matches == 0 or off_topic_literature_matches > poetry_matches:
                    return {"relevant": False, "reason": "テーマ（詩）と無関係な文学の話題が中心"}

            # LLMで詳細な関連性を判定
            if self.openai_adapter and poetry_matches > 0:
                relevance_prompt = f"""
以下は、詩についての思考実験を行っているAIに対するコメントです。

現在の議論テーマ：
- 詩的言語の分析と理解
- 詩から感情状態を読み取る試み
- AIが詩的表現を理解・解析する実験
- 比喩（メタファー）や象徴の構造分析
- 文学作品を通した意識や感情の探求

コメント内容：「{full_comment}」

このコメントが上記の詩に関する議論に関連しているかを判定してください。

判定基準：
【関連度が高い】
- 詩の言語表現、比喩、感情分析について言及
- AIの感情理解・思考実験への参加・質問
- 詩的表現の構造や意味についての深い考察

【関連度が低い（無視すべき）】
- 単なる挨拶や一般的な感想
- テーマと関係のない小説の話題（プロット、キャラクター、作家論など）
- 詩以外の文学ジャンルの議論

関連度: [高/中/低]
理由: [簡潔な理由]
"""
                
                relevance_response = self.openai_adapter.create_chat_for_response(relevance_prompt)
                
                # 関連度を解析
                if "関連度: 高" in relevance_response:
                    return {"relevant": True, "level": "高", "reason": relevance_response}
                elif "関連度: 中" in relevance_response:
                    return {"relevant": True, "level": "中", "reason": relevance_response}
                else:
                    return {"relevant": False, "level": "低", "reason": relevance_response}
            
            # LLMが利用できない場合はキーワードベースで判定
            if poetry_matches >= 2 and off_topic_literature_matches <= poetry_matches:
                return {"relevant": True, "reason": f"詩関連キーワード {poetry_matches} 個検出"}
            elif poetry_matches >= 1 and greeting_matches == 0 and off_topic_literature_matches == 0:
                return {"relevant": True, "reason": f"詩関連キーワード {poetry_matches} 個検出（挨拶・無関係文学なし）"}
            else:
                return {"relevant": False, "reason": "詩の議論に関連するキーワードが不十分、または無関係な文学話題が含まれる"}
                
        except Exception as e:
            print(f"[CommentHandler] Error checking poetry comment relevance: {e}")
            # エラー時は保守的に関連ありとする
            return {"relevant": True, "reason": f"関連性チェック中にエラー: {e}"}
    
    def _get_current_themed_context(self) -> str:
        """現在のテーマファイルからコンテキストを取得する（ModeManager統一メソッド使用）"""
        try:
            # ModeManagerの統一メソッドを使用してテーマ内容を取得
            theme_content = self.mode_manager.get_theme_content()
            if theme_content:
                print("[CommentHandler] 📖 Loaded theme context from ModeManager cache")
                return theme_content
            else:
                print("[CommentHandler] Warning: No theme content available")
                return ""
            
        except Exception as e:
            print(f"[CommentHandler] Error loading theme context: {e}")
            # フォールバック: ModeManagerのactive_theme_contentから取得
            return getattr(self.mode_manager, 'active_theme_content', None) or ""