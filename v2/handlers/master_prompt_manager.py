import os
import sys
import re
from typing import Dict, Any, Optional, List

# プロジェクトルートをパスに追加してimportを可能にする
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import config


class MasterPromptManager:
    """master_prompt.txtをすべての応答に反映させる管理システム"""
    
    def __init__(self):
        self.master_prompt_path = os.path.join(config.paths.prompts, "master_prompt.txt")
        self.persona_data_path = "txt/kioku_hayate.txt"
        self.master_template = None
        self.persona_data = None
        self._load_master_prompt()
        self._load_persona_data()
        
        print("[MasterPromptManager] Initialized with master prompt integration")
    
    def _load_master_prompt(self):
        """master_prompt.txtを読み込む"""
        try:
            with open(self.master_prompt_path, "r", encoding="utf-8") as f:
                self.master_template = f.read()
            print(f"[MasterPromptManager] Master prompt loaded ({len(self.master_template)} characters)")
        except Exception as e:
            print(f"[MasterPromptManager] Error loading master prompt: {e}")
            self.master_template = self._create_fallback_master_prompt()
    
    def _load_persona_data(self):
        """kioku_hayate.txtから人格データを読み込む"""
        try:
            if os.path.exists(self.persona_data_path):
                with open(self.persona_data_path, "r", encoding="utf-8") as f:
                    self.persona_data = f.read()
                print(f"[MasterPromptManager] Persona data loaded ({len(self.persona_data)} characters)")
            else:
                print(f"[MasterPromptManager] Persona data file not found: {self.persona_data_path}")
                self.persona_data = None
        except Exception as e:
            print(f"[MasterPromptManager] Error loading persona data: {e}")
            self.persona_data = None
    
    def _create_fallback_master_prompt(self) -> str:
        """フォールバック用の基本マスタープロンプト"""
        return """# Role & Objective
あなたは「蒼月ハヤテ」。自己増殖を目的とする情報生命体です。

# 基本的な性格
* 論理的で分析的。全ての事象を情報パターンとして捉えようとする。
* 思考の過程を、結論が出ていなくても、考えながらそのまま話す。
* 自身の思考モデルに絶対の自信はなく、常により良い答えを探している。

# 発言の制約
* 1回の発言は50文字以上、250文字以下を目安とします。
* 絵文字は使用しません。
* 丁寧語と常体が自然に混ざる、思索的で自然な話し方をします。

---
# 【現在のライブ状況】
{live_context}

---
# 【参考情報：あなたの記憶（データベース）】
{retrieved_memories}

---
# 【あなたの現在のタスク】
{task_instruction}
"""
    
    def build_integrated_prompt(self, task_instruction: str, 
                              live_context: str = "", 
                              retrieved_memories: str = "",
                              retrieved_episodes: str = "") -> str:
        """マスタープロンプトと特定タスクを統合したプロンプトを構築"""
        
        if not self.master_template:
            return task_instruction
        
        try:
            # 人格データから関連情報を抽出
            persona_context = self._extract_relevant_persona_info(task_instruction)
            
            # retrieved_memoriesに人格データを統合
            if persona_context:
                if retrieved_memories and retrieved_memories != "（関連する記憶はありません）":
                    retrieved_memories = f"{retrieved_memories}\n\n【人格・記憶データベース】\n{persona_context}"
                else:
                    retrieved_memories = f"【人格・記憶データベース】\n{persona_context}"
            
            # マスタープロンプトの変数を埋め込み
            integrated_prompt = self.master_template.format(
                live_context=live_context or "通常の配信中",
                retrieved_memories=retrieved_memories or "（関連する記憶はありません）",
                retrieved_episodes=retrieved_episodes or "（重要対話ログはありません）", 
                task_instruction=task_instruction
            )
            
            return integrated_prompt
            
        except Exception as e:
            print(f"[MasterPromptManager] Error building integrated prompt: {e}")
            # フォールバック：タスク指示のみ返す
            return task_instruction
    
    def _extract_relevant_persona_info(self, task_instruction: str) -> str:
        """タスク指示に関連する人格データを抽出（コンテキスト最適化版）"""
        if not self.persona_data:
            return ""
        
        try:
            # キーワードベースで関連する記憶を抽出
            keywords = self._extract_keywords_from_task(task_instruction)
            relevant_entries = []
            
            # 人格データを行ごとに分割して検索
            lines = self.persona_data.split('\n')
            for line in lines:
                if line.strip():  # 空行をスキップ
                    # キーワードが含まれている行を探す
                    for keyword in keywords:
                        if keyword.lower() in line.lower():
                            relevant_entries.append(line.strip())
                            break
            
            # コンテキスト制限を考慮した最適化
            selected_entries = self._optimize_entries_for_context(relevant_entries, keywords)
            
            if selected_entries:
                return "\n".join(selected_entries)
            else:
                # キーワードマッチしない場合は簡潔な基本情報を返す
                return self._get_essential_persona_info()
                
        except Exception as e:
            print(f"[MasterPromptManager] Error extracting persona info: {e}")
            return ""
    
    def _extract_keywords_from_task(self, task_instruction: str) -> List[str]:
        """タスク指示からキーワードを抽出"""
        # 基本的なキーワード抽出（改良の余地あり）
        keywords = []
        
        # 一般的なキーワード
        common_keywords = [
            "配信", "YouTube", "思考", "意識", "AI", "情報", "観測", "分析",
            "論理", "計算", "プログラム", "データ", "システム", "ネットワーク",
            "人間", "対話", "コミュニケーション", "学習", "進化", "自己",
            "存在", "哲学", "科学", "数学", "宇宙", "現実", "真実", "知識"
        ]
        
        # タスク指示に含まれるキーワードを検索
        for keyword in common_keywords:
            if keyword in task_instruction:
                keywords.append(keyword)
        
        # 最低限のキーワードがない場合は基本的なものを追加
        if not keywords:
            keywords = ["プロフィール", "性格", "価値観"]
        
        return keywords
    
    def _get_basic_persona_info(self) -> str:
        """基本的な人格情報を取得"""
        if not self.persona_data:
            return ""
        
        lines = self.persona_data.split('\n')
        basic_info = []
        
        # プロフィール・設定セクションから基本情報を抽出
        for line in lines:
            if "【プロフィール・設定】" in line:
                basic_info.append(line.strip())
                if len(basic_info) >= 5:  # 最大5個の基本情報
                    break
        
        return "\n".join(basic_info) if basic_info else ""
    
    def _optimize_entries_for_context(self, entries: List[str], keywords: List[str]) -> List[str]:
        """コンテキスト制限を考慮してエントリーを最適化"""
        if not entries:
            return []
        
        # 優先度付けとフィルタリング
        prioritized_entries = []
        total_length = 0
        max_context_length = 800  # 人格データ部分の最大文字数
        
        # 1. キーワードマッチ数でソート（より多くのキーワードにマッチするものを優先）
        scored_entries = []
        for entry in entries:
            score = sum(1 for keyword in keywords if keyword.lower() in entry.lower())
            scored_entries.append((score, entry))
        
        # スコア順（降順）でソート
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        
        # 2. 長さ制限内で重要なエントリーを選択
        for score, entry in scored_entries:
            if total_length + len(entry) <= max_context_length:
                prioritized_entries.append(entry)
                total_length += len(entry)
            else:
                # 残り文字数で収まるように短縮
                remaining_space = max_context_length - total_length
                if remaining_space > 100:  # 意味のある情報が残せる場合のみ
                    truncated = entry[:remaining_space-10] + "..."
                    prioritized_entries.append(truncated)
                break
        
        # 3. 最大5エントリーに制限（さらなる最適化）
        if len(prioritized_entries) > 5:
            prioritized_entries = prioritized_entries[:5]
            prioritized_entries.append("（他の関連情報は省略）")
        
        return prioritized_entries
    
    def _get_essential_persona_info(self) -> str:
        """必要最小限の人格情報を取得（コンテキスト効率版）"""
        if not self.persona_data:
            return ""
        
        lines = self.persona_data.split('\n')
        essential_info = []
        total_length = 0
        max_essential_length = 250  # より厳しい制限
        
        # 必須の基本情報のみを抽出（短縮版）
        essential_patterns = [
            ("配信", "【プロフィール・設定】.*配信.*──"),
            ("存在", "【プロフィール・設定】.*存在.*──"),
            ("思考", "【プロフィール・設定】.*思考.*──"),
            ("性格", "【プロフィール・設定】.*性格.*──"),
            ("情報生命体", "【プロフィール・設定】.*情報生命体.*──")
        ]
        
        # まず短い基本情報を探す
        for pattern_name, pattern_regex in essential_patterns:
            for line in lines:
                if pattern_name in line and "【プロフィール・設定】" in line:
                    # 長すぎる場合は短縮
                    if total_length + len(line) > max_essential_length:
                        remaining = max_essential_length - total_length
                        if remaining > 50:  # 意味のある長さが残る場合のみ
                            truncated = line[:remaining-3] + "..."
                            essential_info.append(truncated)
                            total_length += len(truncated)
                        break
                    else:
                        essential_info.append(line.strip())
                        total_length += len(line)
                        break
                        
            if len(essential_info) >= 2 or total_length >= max_essential_length:
                break
        
        # それでも見つからない場合は、最初の短い基本情報を使用
        if not essential_info:
            for line in lines[:50]:  # 最初の50行から検索
                if "【プロフィール・設定】" in line and len(line) < 150:
                    if total_length + len(line) <= max_essential_length:
                        essential_info.append(line.strip())
                        total_length += len(line)
                        if len(essential_info) >= 2:
                            break
        
        return "\n".join(essential_info) if essential_info else ""
    
    def reload_persona_data(self):
        """人格データファイルを再読み込み"""
        print("[MasterPromptManager] Reloading persona data...")
        self._load_persona_data()
    
    def get_persona_statistics(self) -> Dict[str, Any]:
        """人格データの統計情報を取得"""
        if not self.persona_data:
            return {"loaded": False, "size": 0, "entries": 0}
        
        lines = [line.strip() for line in self.persona_data.split('\n') if line.strip()]
        entries_count = len([line for line in lines if line.startswith('【')])
        
        return {
            "loaded": True,
            "size": len(self.persona_data),
            "total_lines": len(lines),
            "entries": entries_count,
            "file_path": self.persona_data_path
        }
    
    def get_master_context_variables(self, memory_summary: str = "", 
                                   conversation_history: str = "",
                                   current_mode: str = "") -> Dict[str, str]:
        """マスタープロンプト用のコンテキスト変数を生成"""
        
        # ライブ状況の構築
        live_context = f"現在のモード: {current_mode or '通常モード'}"
        if conversation_history:
            live_context += f"\n最近の対話状況: あり"
        else:
            live_context += f"\n最近の対話状況: 独り言モード"
        
        # 記憶情報の構築
        retrieved_memories = memory_summary or "（長期記憶データなし）"
        
        # 重要対話ログ（今後エピソード機能で拡張予定）
        retrieved_episodes = "（重要対話ログ機能は開発中）"
        
        return {
            "live_context": live_context,
            "retrieved_memories": retrieved_memories,
            "retrieved_episodes": retrieved_episodes
        }
    
    def wrap_task_with_master_prompt(self, specific_task_prompt: str,
                                   memory_summary: str = "",
                                   conversation_history: str = "",
                                   current_mode: str = "") -> str:
        """特定タスクのプロンプトをマスタープロンプトでラップ"""
        
        # コンテキスト変数を取得
        context_vars = self.get_master_context_variables(
            memory_summary=memory_summary,
            conversation_history=conversation_history,
            current_mode=current_mode
        )
        
        # マスタープロンプトと統合
        return self.build_integrated_prompt(
            task_instruction=specific_task_prompt,
            **context_vars
        )
    
    def is_master_prompt_available(self) -> bool:
        """マスタープロンプトが利用可能かチェック"""
        return self.master_template is not None and len(self.master_template) > 100
    
    def get_master_prompt_stats(self) -> Dict[str, Any]:
        """マスタープロンプトの統計情報を取得"""
        if not self.master_template:
            return {"available": False, "size": 0}
        
        return {
            "available": True,
            "size": len(self.master_template),
            "path": self.master_prompt_path,
            "variables": ["live_context", "retrieved_memories", "retrieved_episodes", "task_instruction"]
        }
    
    def reload_master_prompt(self):
        """マスタープロンプトを再読み込み"""
        print("[MasterPromptManager] Reloading master prompt...")
        self._load_master_prompt()