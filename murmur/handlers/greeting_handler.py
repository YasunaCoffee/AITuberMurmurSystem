import threading
import sys
import os
from typing import List

# プロジェクトルートをパスに追加してimportを可能にする
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from murmur.core.event_queue import EventQueue
from murmur.core.events import (
    PrepareInitialGreeting, PrepareEndingGreeting, 
    InitialGreetingReady, EndingGreetingReady
)
from murmur.services.prompt_manager import PromptManager
from murmur.handlers.master_prompt_manager import MasterPromptManager
from app.openai_adapter import OpenAIAdapter
from app.conversation_history import ConversationHistory
from app.memory_manager import MemoryManager
from config import config
from murmur.runtime.character_runtime import get_character, resolve_character_path, get_monologue_basename
from murmur.handlers.finetuned_prompt_builder import (
    FINETUNED_SYSTEM_PROMPT,
    build_initial_greeting,
    build_ending_greeting,
    extract_theme_label,
)
from murmur.quality.guarded import generate_speech


class GreetingHandler:
    """挨拶生成を担当するハンドラー。"""

    def __init__(self, event_queue: EventQueue, shared_master_prompt_manager: MasterPromptManager = None, shared_mode_manager = None):
        self.event_queue = event_queue
        
        # マスタープロンプト管理システム
        self.master_prompt_manager = shared_master_prompt_manager or MasterPromptManager()
        
        # モード管理システム（共有または独自インスタンス）
        self.mode_manager = shared_mode_manager
        if not self.mode_manager:
            # フォールバック: master_prompt_managerにmode_managerがある場合は使用
            if hasattr(self.master_prompt_manager, 'mode_manager'):
                self.mode_manager = self.master_prompt_manager.mode_manager
            else:
                print("[GreetingHandler] Warning: No mode_manager available, theme features will be limited")
                self.mode_manager = None
        
        # v1のコンポーネントを初期化
        try:
            # プロンプト管理の初期化
            self.prompt_manager = PromptManager(monologue_primary=get_monologue_basename())
            
            # OpenAI Adapterの初期化（hayate-ft 用: system は学習時の固定3行）
            self.openai_adapter = OpenAIAdapter(FINETUNED_SYSTEM_PROMPT, silent_mode=False)
            
            # 会話履歴管理の初期化
            self.conversation_history = ConversationHistory(self.openai_adapter)
            
            # メモリ管理の初期化
            self.memory_manager = MemoryManager(self.openai_adapter)
            self.memory_manager.set_auto_save_path(
                resolve_character_path(get_character().memory.memory_file)
            )
            
            print("[GreetingHandler] Initialized successfully with OpenAI adapter and PromptManager")
            
        except Exception as e:
            print(f"[GreetingHandler] Error during initialization: {e}")
            # 最小限のフォールバック
            self.prompt_manager = None
            self.openai_adapter = None
            self.conversation_history = None
            self.memory_manager = None

    def handle_prepare_initial_greeting(self, command: PrepareInitialGreeting):
        """開始時の挨拶生成コマンドを処理する"""
        print(f"[GreetingHandler] Received command: {command}")
        
        # バックグラウンドで実行
        thread = threading.Thread(
            target=self._execute_initial_greeting_in_background,
            args=(command,),
            daemon=True,
            name=f"InitialGreeting-{command.task_id}"
        )
        thread.start()

    def handle_prepare_ending_greeting(self, command: PrepareEndingGreeting):
        """終了時の挨拶生成コマンドを処理する"""
        print(f"[GreetingHandler] Received command: {command}")
        
        # バックグラウンドで実行
        thread = threading.Thread(
            target=self._execute_ending_greeting_in_background,
            args=(command,),
            daemon=True,
            name=f"EndingGreeting-{command.task_id}"
        )
        thread.start()

    def _execute_initial_greeting_in_background(self, command: PrepareInitialGreeting):
        """開始時の挨拶をバックグラウンドで生成"""
        try:
            print(f"[GreetingHandler] Processing initial greeting for task: {command.task_id}")
            
            # プロンプトを構築
            prompt = self._build_initial_greeting_prompt()

            # LLMで生成（品質ゲート付き: 検査→fatalなら自動リトライ→ログ記録）
            response, quality = generate_speech(
                self.openai_adapter, prompt, kind="initial_greeting",
                meta={"task_id": command.task_id},
            )
            if not response:
                raise ValueError(f"quality gate rejected: {quality.fatal}")
            print(f"[GreetingHandler] LLM response received: {response[:100]}...")

            # 文に分割
            sentences = self._split_into_sentences(response)
            
            # 完了イベントを発行
            event = InitialGreetingReady(task_id=command.task_id, sentences=sentences)
            self.event_queue.put(event)
            
        except Exception as e:
            print(f"[GreetingHandler] Error generating initial greeting: {e}")
            # エラー時のフォールバック
            fallback_sentences = [
                "あー、マイクチェック。",
                "本日も、皆さんとの思考セッションを開始します。",
                "今日はどんな発見があるでしょうか。"
            ]
            event = InitialGreetingReady(task_id=command.task_id, sentences=fallback_sentences)
            self.event_queue.put(event)

    def _execute_ending_greeting_in_background(self, command: PrepareEndingGreeting):
        """終了時の挨拶をバックグラウンドで生成"""
        try:
            print(f"[GreetingHandler] Processing ending greeting for task: {command.task_id}")
            
            # プロンプトを構築
            prompt = self._build_ending_greeting_prompt(command.bridge_text, command.stream_summary)

            # LLMで生成（品質ゲート付き: 検査→fatalなら自動リトライ→ログ記録）
            response, quality = generate_speech(
                self.openai_adapter, prompt, kind="ending_greeting",
                meta={"task_id": command.task_id},
            )
            if not response:
                raise ValueError(f"quality gate rejected: {quality.fatal}")
            print(f"[GreetingHandler] LLM response received: {response[:100]}...")

            # 文に分割
            sentences = self._split_into_sentences(response)
            
            # 完了イベントを発行
            event = EndingGreetingReady(task_id=command.task_id, sentences=sentences)
            self.event_queue.put(event)
            
        except Exception as e:
            print(f"[GreetingHandler] Error generating ending greeting: {e}")
            # エラー時のフォールバック
            fallback_sentences = [
                "今日の思考セッションは以上となります。",
                "皆さん、ありがとうございました。",
                "また次回、お会いしましょう。"
            ]
            event = EndingGreetingReady(task_id=command.task_id, sentences=fallback_sentences)
            self.event_queue.put(event)

    def _build_initial_greeting_prompt(self) -> str:
        """開始挨拶の user プロンプトを hayate-ft の学習形式で構築する。"""
        try:
            theme = "フリートーク"
            if self.mode_manager:
                theme = extract_theme_label(self.mode_manager.get_theme_content() or "")
            prompt = build_initial_greeting(theme)
            print(f"[GreetingHandler] FT initial greeting prompt: {prompt}")
            return prompt
        except Exception as e:
            print(f"[GreetingHandler] Error building initial greeting prompt: {e}")
            return build_initial_greeting("フリートーク")

    def _build_ending_greeting_prompt(self, bridge_text: str, stream_summary: str) -> str:
        """終了挨拶の user プロンプトを hayate-ft の学習形式で構築する。"""
        try:
            summary = (stream_summary or bridge_text or "").strip()
            if not summary:
                summary = "様々な問いについて皆さんと考えを深めた"
            prompt = build_ending_greeting(summary)
            print(f"[GreetingHandler] FT ending greeting prompt: {prompt}")
            return prompt
        except Exception as e:
            print(f"[GreetingHandler] Error building ending greeting prompt: {e}")
            return build_ending_greeting("様々な問いについて考えを深めた")

    def _split_into_sentences(self, text: str) -> List[str]:
        """テキストを文に分割する"""
        import re
        
        # 句読点で分割
        sentences = re.split(r'[。！？]', text)
        
        # 空文字列を除去し、句読点を復元
        result = []
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if sentence:
                # 最後以外は句読点を復元
                if i < len(sentences) - 1:
                    # 元のテキストから対応する句読点を探す
                    original_pos = text.find(sentence) + len(sentence)
                    if original_pos < len(text) and text[original_pos] in '。！？':
                        sentence += text[original_pos]
                result.append(sentence)
        
        return result if result else [text]

    def _get_current_theme_info(self) -> dict:
        """(このメソッドはMonologueHandlerに移行)"""
        pass

    def _build_themed_greeting_prompt(self, theme_info: dict) -> str:
        """(このメソッドはMonologueHandlerに移行)"""
        pass