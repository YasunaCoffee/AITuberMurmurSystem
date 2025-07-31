import threading
import sys
import os
from typing import List

# プロジェクトルートをパスに追加してimportを可能にする
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from v2.core.event_queue import EventQueue
from v2.core.events import (
    PrepareInitialGreeting, PrepareEndingGreeting, 
    InitialGreetingReady, EndingGreetingReady
)
from v2.services.prompt_manager import PromptManager
from v2.handlers.master_prompt_manager import MasterPromptManager
from openai_adapter import OpenAIAdapter
from conversation_history import ConversationHistory
from memory_manager import MemoryManager
from config import config


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
            self.prompt_manager = PromptManager()
            
            # OpenAI Adapterの初期化
            system_prompt_path = os.path.join(config.paths.prompts, "persona_prompt.txt")
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
            self.openai_adapter = OpenAIAdapter(system_prompt, silent_mode=False)
            
            # 会話履歴管理の初期化
            self.conversation_history = ConversationHistory(self.openai_adapter)
            
            # メモリ管理の初期化
            self.memory_manager = MemoryManager(self.openai_adapter)
            
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
            
            # LLMで生成
            response = self.openai_adapter.create_chat_for_response(prompt)
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
            
            # LLMで生成
            response = self.openai_adapter.create_chat_for_response(prompt)
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
        """開始時の挨拶プロンプトを構築する"""
        try:
            # 汎用的な挨拶プロンプトを読み込む
            with open("prompts/initial_greeting.txt", "r", encoding="utf-8") as f:
                greeting_prompt = f.read()
            
            # 記憶と履歴を取得
            memory_summary = self.memory_manager.get_context_summary() if self.memory_manager else ""
            
            # 最近の会話履歴を取得
            recent_conversations = []
            if self.conversation_history:
                recent_conversations = self.conversation_history.get_recent_conversations("general", limit=3)
            
            # マスタープロンプトと統合
            final_prompt = self.master_prompt_manager.wrap_task_with_master_prompt(
                specific_task_prompt=greeting_prompt,
                memory_summary=memory_summary,
                current_mode="initial_greeting"
            )
            
            print(f"[GreetingHandler] Generic initial greeting integrated with master prompt ({len(final_prompt)} chars)")
            return final_prompt
            
        except Exception as e:
            print(f"[GreetingHandler] Error building initial greeting prompt: {e}")
            return "あなたは蒼月ハヤテです。配信開始の挨拶をしてください。"

    def _build_ending_greeting_prompt(self, bridge_text: str, stream_summary: str) -> str:
        """終了時の挨拶プロンプトを構築する"""
        try:
            # プロンプトファイルを読み込み
            with open('prompts/ending_greeting.txt', 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # 変数を埋め込み
            ending_greeting_prompt = prompt_template.format(
                bridge_text=bridge_text or "それでは、今日の思考実験はここまでとしましょう。",
                stream_summary=stream_summary or "本日も様々な哲学的問いについて考えを深めることができました。"
            )
            
            # マスタープロンプトと統合
            final_prompt = self.master_prompt_manager.wrap_task_with_master_prompt(
                specific_task_prompt=ending_greeting_prompt,
                current_mode="ending_greeting"
            )
            
            print(f"[GreetingHandler] Ending greeting integrated with master prompt ({len(final_prompt)} chars)")
            return final_prompt
            
        except Exception as e:
            print(f"[GreetingHandler] Error building ending greeting prompt: {e}")
            return f"今日の配信を終了します。{bridge_text} {stream_summary} ありがとうございました。"

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