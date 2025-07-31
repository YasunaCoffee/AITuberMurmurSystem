import os
import threading
from typing import List, Optional

from v2.core.event_queue import EventQueue
from v2.core.events import MonologueReady, PrepareMonologue
from v2.services.prompt_manager import PromptManager
from v2.handlers.mode_manager import ModeManager, ConversationMode
from v2.handlers.master_prompt_manager import MasterPromptManager
from openai_adapter import OpenAIAdapter
from conversation_history import ConversationHistory
from memory_manager import MemoryManager
from config import config


class MonologueHandler:
    """独り言の生成を担当するハンドラー。"""

    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        
        # モード管理システムを初期化
        self.mode_manager = ModeManager()
        
        # マスタープロンプト管理システムを初期化
        self.master_prompt_manager = MasterPromptManager()
        
        # v1のコンポーネントを初期化
        try:
            # プロンプト管理の初期化
            self.prompt_manager = PromptManager()
            
            # OpenAIアダプターの初期化
            system_prompt_path = os.path.join(config.paths.prompts, "persona_prompt.txt")
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
            self.openai_adapter = OpenAIAdapter(system_prompt, silent_mode=False)
            
            # 会話履歴とメモリ管理の初期化
            self.conversation_history = ConversationHistory(self.openai_adapter)
            self.memory_manager = MemoryManager(
                llm_adapter=self.openai_adapter, 
                event_queue=self.event_queue
            )
            
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
            
            # LLMで生成
            response = self.openai_adapter.create_chat_for_response(prompt)
            print(f"[MonologueHandler] LLM response received: {response[:100]}...")
            
            if response:
                print(f"[MonologueHandler] LLM response received: {response[:100]}...")
                
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
            specific_task_prompt = ""
            # theme_contentが直接指定されている場合、最優先で使用
            if theme_content:
                theme_info = self._extract_theme_info(theme_content)
                specific_task_prompt = self._build_themed_monologue_prompt(theme_info)
                print("[MonologueHandler] Loaded monologue theme from provided content.")

            # プリフェッチ時（theme_file is None）の処理 - 常にテーマ関連の内容を生成する
            elif theme_file is None:
                # ModeManagerから現在のテーマを取得
                current_theme_content = self.mode_manager.get_theme_content()
                if not current_theme_content:
                    print("[MonologueHandler] No theme content from ModeManager for prefetch, using fallback.")
                    # フォールバックとしてデフォルトのプロンプトを使う
                    prompt_template = self.prompt_manager.get_prompt(prompt_name)
                    specific_task_prompt = prompt_template
                else:
                    # テーマ情報からプロンプトを生成
                    theme_info = self._extract_theme_info(current_theme_content)
                    specific_task_prompt = self._build_themed_monologue_prompt(theme_info)
            else:
                # theme_fileが指定されている場合、その内容を読み込む
                try:
                    with open(theme_file, "r", encoding="utf-8") as f:
                        theme_content = f.read()
                    theme_info = self._extract_theme_info(theme_content)
                    specific_task_prompt = self._build_themed_monologue_prompt(theme_info)
                    print(f"[MonologueHandler] Loaded monologue theme from path: {theme_file}")
                except FileNotFoundError:
                    print(f"[MonologueHandler] Error: Theme file not found at {theme_file}, using default prompt.")
                    prompt_template = self.prompt_manager.get_prompt(prompt_name)
                    specific_task_prompt = prompt_template
                except Exception as e:
                    print(f"[MonologueHandler] Error reading theme file at {theme_file}: {e}, using default prompt.")
                    prompt_template = self.prompt_manager.get_prompt(prompt_name)
                    specific_task_prompt = prompt_template
            
            # マスタープロンプトと統合
            final_prompt = self.master_prompt_manager.wrap_task_with_master_prompt(
                specific_task_prompt=specific_task_prompt,
                memory_summary=self.memory_manager.get_context_summary() if self.memory_manager else "",
                conversation_history="", # 特定プロンプトの場合は履歴を限定
                current_mode="prompt_file_monologue"
            )
            
            print(f"[MonologueHandler] Integrated with master prompt ({len(final_prompt)} chars)")
            return final_prompt

        except Exception as e:
            print(f"[MonologueHandler] Error building monologue prompt: {e}")
            # エラー時は汎用的なプロンプトを返す
            return self.master_prompt_manager.wrap_task_with_master_prompt(
                specific_task_prompt="何か面白いことについて、自由に独り言を話してください。",
                current_mode="fallback_monologue"
            )

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
                speaker="蒼月ハヤテ"
            )
            
            print(f"[MonologueHandler] Saved monologue to memory: {monologue_text[:50]}...")
            
        except Exception as e:
            print(f"[MonologueHandler] Error saving monologue to memory: {e}")
    
    def set_theme_file(self, theme_file_path: str):
        """テーマファイルを動的に変更する（ModeManagerへの委譲）"""
        return self.mode_manager.set_theme_file(theme_file_path)