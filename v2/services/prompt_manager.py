import os
import random
import sys
from typing import Dict, List, Optional
from enum import Enum

# プロジェクトルートをパスに追加してimportを可能にする
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import config


class PromptType(Enum):
    """プロンプトの種類を定義"""
    MONOLOGUE = "monologue"
    COMMENT_RESPONSE = "comment_response"
    GREETING = "greeting"
    THEME_CONTINUATION = "theme_continuation"
    CONSULTATION = "consultation"


class PromptManager:
    """
    プロンプトファイルを管理し、動的に選択・組み合わせを行うクラス。
    """
    
    def __init__(self):
        self.prompts_dir = config.paths.prompts
        self.prompt_cache: Dict[str, str] = {}
        
        # プロンプトの分類とファイルマッピング
        self.prompt_mappings = {
            PromptType.MONOLOGUE: [
                "normal_monologue.txt",
                "theme_continuation_monologue.txt", 
                "topic_continuation_monologue.txt"
            ],
            PromptType.COMMENT_RESPONSE: [
                "integrated_response.txt"
            ],
            PromptType.GREETING: [
                "initial_greeting.txt",
                "ending_greeting.txt"
            ],
            PromptType.THEME_CONTINUATION: [
                "theme_continuation_monologue.txt",
                "episode_deep_dive_prompt.txt"
            ],
            PromptType.CONSULTATION: [
                "viewer_consultation_prompt.txt",
                "chill_chat_prompt.txt"
            ]
        }
        
        # プロンプトの重み付け（選択確率を調整）
        self.prompt_weights = {
            "normal_monologue.txt": 0.6,  # 通常の独り言（最頻出）
            "theme_continuation_monologue.txt": 0.2,
            "topic_continuation_monologue.txt": 0.15,
            "episode_deep_dive_prompt.txt": 0.05,
            "integrated_response.txt": 1.0,  # コメント応答は基本的にこれのみ
            "viewer_consultation_prompt.txt": 0.4,
            "chill_chat_prompt.txt": 0.6
        }
        
        print(f"[PromptManager] Initialized with {len(self.get_all_prompts())} prompt files")

    def get_prompt(self, prompt_type: PromptType, 
                  context: Optional[Dict] = None,
                  force_specific: Optional[str] = None) -> str:
        """
        指定された種類のプロンプトを取得する。
        
        Args:
            prompt_type: プロンプトの種類
            context: コンテキスト情報（選択に影響する場合あり）
            force_specific: 特定のプロンプトファイル名を強制指定
            
        Returns:
            プロンプトの内容
        """
        if force_specific:
            return self._load_prompt(force_specific)
        
        # プロンプトタイプに応じて適切なファイルを選択
        candidate_files = self.prompt_mappings.get(prompt_type, [])
        
        if not candidate_files:
            raise ValueError(f"No prompts available for type: {prompt_type}")
        
        # コンテキストに基づいた選択（拡張可能）
        selected_file = self._select_prompt_file(candidate_files, context)
        
        return self._load_prompt(selected_file)

    def _select_prompt_file(self, candidates: List[str], 
                           context: Optional[Dict] = None) -> str:
        """
        候補ファイルから適切なプロンプトファイルを選択する。
        
        Args:
            candidates: 候補となるプロンプトファイル名のリスト
            context: 選択の判断材料となるコンテキスト
            
        Returns:
            選択されたプロンプトファイル名
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # 重み付き選択
        weights = [self.prompt_weights.get(file, 1.0) for file in candidates]
        selected_file = random.choices(candidates, weights=weights)[0]
        
        print(f"[PromptManager] Selected prompt: {selected_file}")
        return selected_file

    def _load_prompt(self, filename: str) -> str:
        """プロンプトファイルを読み込む（キャッシュ機能付き）"""
        if filename in self.prompt_cache:
            return self.prompt_cache[filename]
        
        file_path = os.path.join(self.prompts_dir, filename)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.prompt_cache[filename] = content
                return content
        except FileNotFoundError:
            print(f"[PromptManager] Warning: Prompt file not found: {file_path}")
            return self._get_fallback_prompt(filename)
        except Exception as e:
            print(f"[PromptManager] Error loading prompt {filename}: {e}")
            return self._get_fallback_prompt(filename)

    def _get_fallback_prompt(self, filename: str) -> str:
        """プロンプトファイルが見つからない場合のフォールバック"""
        fallback_prompts = {
            "normal_monologue.txt": "自然で楽しい独り言を話してください。",
            "integrated_response.txt": "以下のコメントに自然に返答してください：{comments}",
            "initial_greeting.txt": "こんにちは！今日も配信を始めます。",
            "ending_greeting.txt": "今日の配信はここまでです。ありがとうございました。"
        }
        
        return fallback_prompts.get(filename, "自然で楽しい会話をしてください。")

    def get_all_prompts(self) -> List[str]:
        """利用可能な全プロンプトファイル名を取得"""
        all_files = []
        for file_list in self.prompt_mappings.values():
            all_files.extend(file_list)
        return list(set(all_files))  # 重複除去

    def reload_prompts(self):
        """プロンプトキャッシュをクリアして再読み込み"""
        self.prompt_cache.clear()
        print("[PromptManager] Prompt cache cleared, will reload on next access")

    def get_prompt_stats(self) -> Dict:
        """プロンプト使用統計を取得（今後の機能拡張用）"""
        return {
            "total_prompts": len(self.get_all_prompts()),
            "cached_prompts": len(self.prompt_cache),
            "prompt_types": len(self.prompt_mappings)
        }

    # === 便利メソッド ===
    
    def get_monologue_prompt(self, context: Optional[Dict] = None) -> str:
        """独り言用プロンプトを取得"""
        return self.get_prompt(PromptType.MONOLOGUE, context)
    
    def get_comment_response_prompt(self, context: Optional[Dict] = None) -> str:
        """コメント応答用プロンプトを取得"""
        return self.get_prompt(PromptType.COMMENT_RESPONSE, context)
    
    def get_greeting_prompt(self, is_ending: bool = False) -> str:
        """挨拶用プロンプトを取得"""
        specific_file = "ending_greeting.txt" if is_ending else "initial_greeting.txt"
        return self.get_prompt(PromptType.GREETING, force_specific=specific_file)
    
    def get_prompt_by_filename(self, filename: str) -> Optional[str]:
        """ファイル名を指定してプロンプトを取得"""
        try:
            return self._load_prompt(filename)
        except Exception as e:
            print(f"[PromptManager] Error loading prompt file {filename}: {e}")
            return None