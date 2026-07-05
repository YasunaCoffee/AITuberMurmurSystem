import os
import threading
from typing import List, Optional

from murmur.core.event_queue import EventQueue
from murmur.core.events import MonologueReady, PrepareMonologue
from murmur.services.prompt_manager import PromptManager
from murmur.handlers.mode_manager import ModeManager, ConversationMode
from murmur.handlers.master_prompt_manager import MasterPromptManager
from app.openai_adapter import OpenAIAdapter
from app.conversation_history import ConversationHistory
from app.memory_manager import MemoryManager
from config import config
from murmur.runtime.character_runtime import get_character, resolve_character_path, get_monologue_basename
from murmur.handlers.finetuned_prompt_builder import (
    FINETUNED_SYSTEM_PROMPT,
    MONOLOGUE_MODES,
    build_monologue,
    extract_theme_label,
    pick_monologue_mode,
)
from murmur.quality.guarded import generate_speech


class MonologueHandler:
    """独り言の生成を担当するハンドラー。"""

    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        
        # モード管理システムを初期化
        self.mode_manager = ModeManager()
        # 直前に使った独り言モード[A-H]（連続重複を避けるため保持）
        self._last_monologue_mode = None

        # マスタープロンプト管理システムを初期化
        self.master_prompt_manager = MasterPromptManager()
        
        # v1のコンポーネントを初期化
        try:
            # プロンプト管理の初期化
            self.prompt_manager = PromptManager(monologue_primary=get_monologue_basename())
            
            # OpenAIアダプターの初期化（hayate-ft 用: system は学習時の固定3行。
            # 人格は重みに焼かれているため persona_prompt.txt は読み込まない）
            self.openai_adapter = OpenAIAdapter(FINETUNED_SYSTEM_PROMPT, silent_mode=False)
            
            # 会話履歴とメモリ管理の初期化
            self.conversation_history = ConversationHistory(self.openai_adapter)
            self.memory_manager = MemoryManager(
                llm_adapter=self.openai_adapter, 
                event_queue=self.event_queue
            )
            _mem = resolve_character_path(get_character().memory.memory_file)
            self.memory_manager.set_auto_save_path(_mem)
            if os.path.isfile(_mem):
                self.memory_manager.load_summary_from_file(_mem)
            
            print("[MonologueHandler] Initialized successfully with OpenAI adapter and PromptManager")
        except Exception as e:
            print(f"[MonologueHandler] Warning: Failed to initialize components: {e}")
            self.prompt_manager = None
            self.openai_adapter = None
            self.conversation_history = None
            self.memory_manager = None

    def handle_prepare_monologue(self, command: PrepareMonologue):
        """
        PrepareMonologueコマンドを処理する。
        バックグラウンドでLLMに問い合わせ、完了時にイベントを発行する。
        """
        print(f"[MonologueHandler] Received command: {command}")
        thread = threading.Thread(
            target=self._execute_monologue_in_background,
            args=(command,),
            daemon=True,
            name=f"Monologue-{command.task_id}"
        )
        thread.start()

    def _execute_monologue_in_background(self, command: PrepareMonologue):
        """独り言生成をバックグラウンドで実行する"""
        try:
            print(f"[MonologueHandler] Processing monologue for task: {command.task_id}")
            
            # プロンプトを構築
            prompt = self._build_monologue_prompt(
                prompt_name="normal_monologue", 
                theme_file=command.theme_file,
                theme_content=command.theme_content
            )
            
            # LLMで生成（品質ゲート付き: 検査→fatalなら自動リトライ→ログ記録）
            response, quality = generate_speech(
                self.openai_adapter, prompt, kind="monologue",
                meta={"mode": self._last_monologue_mode, "task_id": command.task_id},
            )

            if response:
                print(f"[MonologueHandler] LLM response received: {response[:100]}...")
                if quality.warnings:
                    print(f"[MonologueHandler] Quality warnings: {quality.warnings}")

                # ★ 生成した発言をModeManagerに記録
                self.mode_manager.set_last_ai_utterance(response)
                
                sentences = self._split_into_sentences(response)

                # 3. 独り言を記憶に記録
                self._save_monologue_to_memory(response)

                # 4. 結果をイベントキューに入れる
                event = MonologueReady(task_id=command.task_id, sentences=sentences)
                self.event_queue.put(event)
            else:
                print("[MonologueHandler] Warning: Received empty response from LLM")
                # エラー時のフォールバック応答
                fallback_sentences = ["えーっと、ちょっと考えがまとまらないですね。"]
                event = MonologueReady(task_id=command.task_id, sentences=fallback_sentences)
                self.event_queue.put(event)

        except Exception as e:
            print(f"[MonologueHandler] Error during LLM call: {e}")
            # エラー時のフォールバック
            fallback_sentences = [
                "うーん、今ちょっと思考が整理できていないみたいです。"
            ]
            event = MonologueReady(task_id=command.task_id, sentences=fallback_sentences)
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

    def _build_monologue_prompt(
        self,
        prompt_name: str = "normal_monologue", 
        theme_file: Optional[str] = None,
        theme_content: Optional[str] = None
    ) -> str:
        """
        独り言のプロンプトを構築する。
        theme_content, theme_file の順で優先的に使用し、
        どちらもなければ、モードマネージャーから現在のテーマを取得して
        テーマに基づいたプロンプトを生成します。
        """
        try:
            # テーマ本文を決定: theme_content > theme_file > ModeManager
            content = theme_content
            if content is None and theme_file:
                try:
                    with open(theme_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    print(f"[MonologueHandler] Loaded theme from path: {theme_file}")
                except Exception as e:
                    print(f"[MonologueHandler] Theme file read failed ({theme_file}): {e}")
            if content is None:
                content = self.mode_manager.get_theme_content()

            # 短いテーマ名を抽出し、ModeManager の現在モード＋直前の発話で
            # v2 チェーン形式の user を組み立てる（思考が前の断片から連続する）
            theme_label = extract_theme_label(content or "")
            mode = getattr(self.mode_manager.current_mode, "value", None)
            if mode not in MONOLOGUE_MODES:
                mode = pick_monologue_mode(exclude=self._last_monologue_mode)
            self._last_monologue_mode = mode
            prompt = build_monologue(
                theme_label, mode=mode,
                last_utterance=self.mode_manager.last_ai_utterance,
            )
            print(f"[MonologueHandler] FT monologue prompt: {prompt}")
            return prompt

        except Exception as e:
            print(f"[MonologueHandler] Error building monologue prompt: {e}")
            return build_monologue("フリートーク")

    def _build_themed_monologue_prompt(self, theme_info: dict) -> str:
        """テーマ情報に基づいて独り言のプロンプトを生成する"""
        work_info = theme_info.get('work_info', 'ある文学作品')
        analysis_elements = theme_info.get('analysis_elements', '人間の感情')
        experiment_themes_default = '・テキスト分析\n・感情解析'
        experiment_themes = theme_info.get('experiment_themes', experiment_themes_default)

        prompt = (
            f"あなたは今、「{work_info}」について思考実験を行っています。"
            f"この作品のテーマである「{analysis_elements}」について、"
            "あなたの考察を独り言として話してください。\n\n"
            "特に、以下の実験テーマのいずれかに触れながら、自由に思考を展開してください。\n"
            f"{experiment_themes}"
            "--- \n"
            "例：「この物語の主人公は、なぜあの場面で矛盾した行動を取ったのだろうか…」\n"
            "例：「作者が使ったこの比喩表現は、登場人物のどんな深層心理を表現しているんだろう…」"
        )
        return prompt

    def _extract_theme_info(self, theme_content: str) -> dict:
        """テーマのテキストから情報を抽出する"""
        try:
            # デフォルト値
            theme_info = {
                'work_info': '不明な作品',
                'experiment_type': '思考実験',
                'analysis_elements': '人間の複雑な感情',
                'experiment_themes': '■実験テーマ:\n・テキスト分析\n・感情解析\n・思考プロセス\n\n'
            }
            
            if not theme_content:
                return theme_info
            
            lines = theme_content.split('\n')
            
            # Case: 行から作品情報を抽出
            for line in lines:
                if 'Case:' in line and '-' in line:
                    parts = line.split('-', 1)
                    if len(parts) > 1:
                        work_title = parts[1].strip()
                        for separator in ['からの', 'を通じた', 'による']:
                            if separator in work_title:
                                work_title = work_title.split(separator)[0].strip()
                                break
                        theme_info['work_info'] = work_title
                    break
            
            # Analysis & Observation Log: から分析要素を抽出
            analysis_section = self._extract_section(theme_content, '[Analysis & Observation Log: 分析と観測ログ]')
            if analysis_section:
                keywords = ['比喩', 'メタファー', '状態方程式', '孤独', '関係性']
                elements = [k for k in keywords if k in analysis_section]
                if elements:
                    theme_info['analysis_elements'] = '、'.join(elements)
            
            # ■実験テーマ: セクションを抽出
            theme_lines = []
            in_theme_section = False
            for line in lines:
                if line.strip().startswith('■') and ('テーマ' in line or 'Theme' in line):
                    in_theme_section = True
                if in_theme_section:
                    if line.strip():
                        theme_lines.append(line.strip())
                    elif theme_lines:
                        break # 空行でセクション終了
            
            if theme_lines:
                theme_info['experiment_themes'] = '\n'.join(theme_lines) + '\n\n'
            
            return theme_info
            
        except Exception as e:
            print(f"[MonologueHandler] Error extracting theme info: {e}")
            return theme_info # エラー時もデフォルト値を返す

    def _extract_section(self, content: str, section_header: str) -> str:
        """特定のセクションの内容を抽出する"""
        lines = content.split('\n')
        in_section = False
        section_content = []
        
        for line in lines:
            if section_header in line:
                in_section = True
                continue
            elif in_section:
                if line.strip().startswith('[') and line.strip().endswith(']'):
                    break
                section_content.append(line)
        
        return '\n'.join(section_content).strip()

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

    def _save_monologue_to_memory(self, monologue_text: str):
        """独り言を記憶に記録する"""
        if not self.memory_manager:
            print("[MonologueHandler] Warning: MemoryManager not available, skipping memory save")
            return
        
        try:
            # 独り言の内容をメモリマネージャーに記録
            # add_utteranceメソッドを使用してシステム発話として記録
            self.memory_manager.add_utterance(
                text=monologue_text,
                speaker=get_character().name,
            )
            
            print(f"[MonologueHandler] Saved monologue to memory: {monologue_text[:50]}...")
            
        except Exception as e:
            print(f"[MonologueHandler] Error saving monologue to memory: {e}")
    
    def set_theme_file(self, theme_file_path: str):
        """テーマファイルを動的に変更する（ModeManagerへの委譲）"""
        return self.mode_manager.set_theme_file(theme_file_path)