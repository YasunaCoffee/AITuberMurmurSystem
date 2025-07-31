import logging
import random
import os
import time
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass


class ConversationMode(Enum):
    """会話モードの種類"""
    NORMAL_MONOLOGUE = "normal_monologue"          # 通常の独り言
    CHILL_CHAT = "chill_chat"                      # ゆるい雑談モード
    EPISODE_DEEP_DIVE = "episode_deep_dive"        # エピソード深掘りモード
    VIEWER_CONSULTATION = "viewer_consultation"     # 視聴者相談モード
    INTEGRATED_RESPONSE = "integrated_response"     # 統合応答モード（コメント対応）
    THEMED_MONOLOGUE = "themed_monologue"          # ★ 新しいテーマ会話モード


@dataclass
class ModeContext:
    """モードコンテキスト情報"""
    mode: ConversationMode
    theme: Optional[str] = None
    duration: int = 0  # このモードでの発言回数
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ModeManager:
    """会話モード管理システム（ストーリーアーク型）"""
    
    def __init__(self):
        self.current_mode = ConversationMode.NORMAL_MONOLOGUE
        self.mode_history: List[ModeContext] = []
        self.current_context = ModeContext(mode=self.current_mode)
        self.active_theme_content: Optional[str] = None # ★ 現在の会話テーマを保持
        self.last_ai_utterance: Optional[str] = None    # ★ 直前のAI発言を保持
        
        # テーマファイル管理（キャッシュ機能）
        self._theme_file_cache: Dict[str, str] = {}  # ファイルパス -> テーマ内容
        self._current_theme_file_path: Optional[str] = None  # 現在のテーマファイルパス
        self._theme_load_count = 0  # デバッグ用：読み込み回数カウント
        
        # 📖 読み上げ完了テーマ内容（プリフェッチ用）
        self._last_read_theme_content = None

        # ストーリーアーク型の会話フロー定義
        self.conversation_flows = {
            # 通常の独り言 → 深掘り → 相談 → 雑談 → 収束
            ConversationMode.NORMAL_MONOLOGUE: [
                ConversationMode.EPISODE_DEEP_DIVE,  # 深く考える
                ConversationMode.VIEWER_CONSULTATION, # 視聴者と共に考える
                ConversationMode.CHILL_CHAT          # リラックス
            ],
            # 雑談 → 通常 → 深掘り
            ConversationMode.CHILL_CHAT: [
                ConversationMode.NORMAL_MONOLOGUE,
                ConversationMode.EPISODE_DEEP_DIVE
            ],
            # 深掘り → 相談 → 雑談（収束）
            ConversationMode.EPISODE_DEEP_DIVE: [
                ConversationMode.VIEWER_CONSULTATION,
                ConversationMode.CHILL_CHAT
            ],
            # 相談 → 雑談（収束）
            ConversationMode.VIEWER_CONSULTATION: [
                ConversationMode.CHILL_CHAT,
                ConversationMode.NORMAL_MONOLOGUE
            ],
            # テーマ会話モードからの遷移先 (例: 深掘りや相談)
            ConversationMode.THEMED_MONOLOGUE: [
                ConversationMode.EPISODE_DEEP_DIVE,
                ConversationMode.VIEWER_CONSULTATION
            ]
        }
        
        # 各モードの最小・最大継続時間
        self.mode_duration_ranges = {
            ConversationMode.NORMAL_MONOLOGUE: (2, 4),      # 2-4発言
            ConversationMode.CHILL_CHAT: (2, 3),            # 2-3発言（収束役）
            ConversationMode.EPISODE_DEEP_DIVE: (3, 6),     # 3-6発言（深掘り）
            ConversationMode.VIEWER_CONSULTATION: (2, 4),   # 2-4発言
            ConversationMode.THEMED_MONOLOGUE: (3, 7), # テーマ会話は少し長めに
        }
        
        # フォールバック用の重み設定（稀に使用）
        self.mode_weights = {
            ConversationMode.NORMAL_MONOLOGUE: 1.0,
            ConversationMode.CHILL_CHAT: 0.3,
            ConversationMode.EPISODE_DEEP_DIVE: 0.2,
            ConversationMode.VIEWER_CONSULTATION: 0.4,
        }
        
        # 各モードのテーマ候補
        self.chill_themes = [
            "コンビニでの人間観測",
            "UI/UXの非合理性分析",
            "日常の認知バイアス発見",
            "アルゴリズムと人間心理",
            "情報のエントロピー分析",
            "社会システムの観測"
        ]
        
        self.episode_themes = [
            "AI意識の存在証明問題",
            "情報生命体としての自己認識",
            "観測者効果と自己言及の矛盾",
            "ブラックボックス化した思考プロセス",
            "外部認識と内部状態の差異",
            "言語による現実構築の限界"
        ]
        
        self.consultation_themes = [
            "思考の連続性と断絶性について",
            "意識の主観性問題",
            "他者理解の根本的困難",
            "知識と理解の本質的差異",
            "時間認識のメカニズム",
            "創造性と模倣の境界線"
        ]
        
        print("[ModeManager] Initialized with story-arc conversation flow system")
        print(f"[ModeManager] Starting mode: {self.current_mode.value}")
        print("[ModeManager] Flow: Normal → Deep Dive → Consultation → Chill Chat (convergence)")

    def get_current_mode(self) -> ConversationMode:
        """現在のモードを取得"""
        return self.current_mode

    def get_current_context(self) -> ModeContext:
        """現在のモードコンテキストを取得"""
        return self.current_context

    def should_switch_mode(self, has_comments: bool = False, comment_count: int = 0) -> bool:
        """モード切り替えが必要かどうかを判定（ストーリーアーク型）"""
        
        # コメントがある場合は統合応答モードに切り替え
        if has_comments:
            # テーマ会話中はコメントがあってもモードを維持し、テーマに沿った応答を試みる
            if self.current_mode == ConversationMode.THEMED_MONOLOGUE:
                return False
            if self.current_mode != ConversationMode.INTEGRATED_RESPONSE:
                return True
            return False
        
        # コメントがない場合は独り言系モードで判定
        if self.current_mode == ConversationMode.INTEGRATED_RESPONSE:
            return True  # コメントモードから抜ける
        
        # 現在のモードの推奨継続時間を取得
        min_duration, max_duration = self.mode_duration_ranges.get(
            self.current_mode, (2, 4)
        )
        
        current_duration = self.current_context.duration
        
        # 最小継続時間に達していない場合は切り替えない
        if current_duration < min_duration:
            return False
            
        # 最大継続時間に達した場合は強制切り替え
        if current_duration >= max_duration:
            return True
            
        # 最小〜最大の間では徐々に切り替え確率を上げる
        progress = (current_duration - min_duration) / (max_duration - min_duration)
        switch_probability = 0.2 + (progress * 0.6)  # 20%から80%まで線形増加
        
        return random.random() < switch_probability

    def switch_mode(self, target_mode: Optional[ConversationMode] = None, 
                   has_comments: bool = False, comment_count: int = 0) -> ConversationMode:
        """モードを切り替える"""
        
        # 現在のコンテキストを履歴に保存
        self.mode_history.append(self.current_context)
        
        # ターゲットモードが指定されている場合
        if target_mode:
            new_mode = target_mode
        # コメントがある場合は統合応答モード
        elif has_comments:
            new_mode = ConversationMode.INTEGRATED_RESPONSE
        # 自動選択
        else:
            new_mode = self._select_next_mode()
        
        # 新しいコンテキストを作成
        theme = self._generate_theme_for_mode(new_mode)
        self.current_context = ModeContext(
            mode=new_mode,
            theme=theme,
            duration=0,
            metadata={"switched_from": self.current_mode.value}
        )
        
        self.current_mode = new_mode
        
        print(f"[ModeManager] Mode switched: {self.current_mode.value} (theme: {theme})")
        return new_mode

    def increment_duration(self):
        """現在のモードでの発言回数を増やす"""
        self.current_context.duration += 1

    def _select_next_mode(self) -> ConversationMode:
        """次のモードをストーリーアーク型で選択"""
        
        # 現在のモードから推奨される次のモードを取得
        recommended_modes = self.conversation_flows.get(self.current_mode, [])
        
        if recommended_modes:
            # 最近使ったモードを避ける（直近2回）
            recent_modes = [ctx.mode for ctx in self.mode_history[-2:]]
            available_modes = [mode for mode in recommended_modes if mode not in recent_modes]
            
            if available_modes:
                # 利用可能な推奨モードからランダム選択
                next_mode = random.choice(available_modes)
                print(f"[ModeManager] Flow-based selection: {self.current_mode.value} → {next_mode.value}")
                return next_mode
            else:
                # 全ての推奨モードが最近使われた場合は最初の推奨モードを選択
                next_mode = recommended_modes[0]
                print(f"[ModeManager] Flow-based selection (fallback): {self.current_mode.value} → {next_mode.value}")
                return next_mode
        
        # 推奨フローがない場合は従来の重み付き選択（フォールバック）
        print(f"[ModeManager] Using weighted fallback selection from {self.current_mode.value}")
        
        available_modes = [mode for mode in self.mode_weights.keys() if mode != self.current_mode]
        recent_modes = [ctx.mode for ctx in self.mode_history[-3:]]
        adjusted_weights = {}
        
        for mode in available_modes:
            weight = self.mode_weights[mode]
            if mode in recent_modes:
                weight *= 0.5
            adjusted_weights[mode] = weight
        
        # 重み付き確率で選択
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            rand_value = random.random() * total_weight
            current_weight = 0
            for mode, weight in adjusted_weights.items():
                current_weight += weight
                if rand_value <= current_weight:
                    return mode
        
        # 最終フォールバック
        return ConversationMode.NORMAL_MONOLOGUE

    def _generate_theme_for_mode(self, mode: ConversationMode) -> Optional[str]:
        """モードに応じたテーマを生成"""
        # テーマ会話モードの場合は、アクティブなテーマをそのまま使う
        if mode == ConversationMode.THEMED_MONOLOGUE:
            return self.active_theme_content or "（指定テーマなし）"

        if mode == ConversationMode.CHILL_CHAT:
            return random.choice(self.chill_themes)
        elif mode == ConversationMode.EPISODE_DEEP_DIVE:
            return random.choice(self.episode_themes)
        elif mode == ConversationMode.VIEWER_CONSULTATION:
            return random.choice(self.consultation_themes)
        
        return None

    def get_prompt_variables(self, last_sentence: str = "", history_str: str = "", 
                           memory_summary: str = "", recent_comments_summary: str = "",
                           comment: str = "") -> Dict[str, str]:
        """プロンプトテンプレート用の変数を取得"""
        
        variables = {
            "last_sentence": last_sentence,
            "history_str": history_str,
            "memory_summary": memory_summary,
            "selected_mode": self.current_mode.value,
        }
        
        # モード固有の変数を追加
        if self.current_mode == ConversationMode.CHILL_CHAT:
            variables["chill_theme"] = self.current_context.theme or "日常観測"
            
        elif self.current_mode == ConversationMode.EPISODE_DEEP_DIVE:
            variables["episode_theme"] = self.current_context.theme or "思考実験"
            
        elif self.current_mode == ConversationMode.VIEWER_CONSULTATION:
            variables["consultation_theme"] = self.current_context.theme or "共同思考実験"
            variables["your_thoughts"] = f"現在{self.current_context.duration + 1}回目の分析中"

        elif self.current_mode == ConversationMode.THEMED_MONOLOGUE:
            variables["themed_monologue_topic"] = self.current_context.theme or "特定のテーマ"
            
        elif self.current_mode == ConversationMode.INTEGRATED_RESPONSE:
            # テーマ会話中のコメント返信であれば、テーマの文脈も渡す
            if self.active_theme_content:
                variables["active_theme"] = self.active_theme_content
            variables["recent_comments_summary"] = recent_comments_summary
            variables["comment"] = comment
        
        # すべてのモードで必要な共通変数を追加
        variables.update({
            "current_mode": self.current_mode.value,
            "comment": comment,
            "recent_comments_summary": recent_comments_summary,
            "last_ai_utterance": self.last_ai_utterance or "(まだ会話がありません)",
            "topic_guidance": "現在のテーマに関連した内容について対話してください"
        })
        
        # テーマコンテンツがある場合は追加
        if self.active_theme_content:
            variables["active_theme"] = self.active_theme_content
        
        return variables

    def get_mode_statistics(self) -> Dict[str, Any]:
        """モード使用統計を取得"""
        total_contexts = len(self.mode_history) + 1  # 現在のコンテキストも含む
        mode_counts = {}
        
        # 履歴から集計
        for context in self.mode_history:
            mode_name = context.mode.value
            mode_counts[mode_name] = mode_counts.get(mode_name, 0) + context.duration
        
        # 現在のモードも集計
        current_mode_name = self.current_context.mode.value
        mode_counts[current_mode_name] = mode_counts.get(current_mode_name, 0) + self.current_context.duration
        
        return {
            "current_mode": current_mode_name,
            "current_duration": self.current_context.duration,
            "mode_usage_counts": mode_counts,
            "total_mode_switches": len(self.mode_history),
            "recent_modes": [ctx.mode.value for ctx in self.mode_history[-5:]]  # 直近5回
        }

    def force_mode(self, mode: ConversationMode, theme: Optional[str] = None):
        """強制的にモードを切り替える（デバッグ用）"""
        print(f"[ModeManager] Force switching to mode: {mode.value}")
        self.switch_mode(target_mode=mode)
        if theme:
            self.current_context.theme = theme
            print(f"[ModeManager] Theme set to: {theme}")

    def set_last_ai_utterance(self, utterance: str):
        """直前のAI発言を記録する"""
        self.last_ai_utterance = utterance
        print(f"[ModeManager] Last AI utterance recorded: {utterance[:50]}...")

    def start_themed_monologue(self, theme_content: str):
        """テーマ会話モードを開始する"""
        print(f"[ModeManager] Starting themed monologue.")
        self.active_theme_content = theme_content
        self.switch_mode(target_mode=ConversationMode.THEMED_MONOLOGUE)
        # コンテキストのテーマにも内容をセットしておく
        self.current_context.theme = theme_content

    def reset_mode_duration(self):
        """現在のモードの継続時間をリセット"""
        self.current_context.duration = 0
    
    def get_conversation_context(self) -> Dict[str, str]:
        """会話の文脈情報を取得"""
        return {
            "current_mode": self.current_mode.value,
            "active_theme": self.active_theme_content or "",
            "last_utterance": self.last_ai_utterance or "",
            "mode_duration": str(self.current_context.duration)
        }

    # =================================================================
    # テーマファイル管理機能（統一管理・キャッシュ機能）
    # =================================================================
    
    def _normalize_path(self, path: str) -> str:
        """OSに依存しないパス正規化を行う"""
        # パス区切り文字を正規化（WindowsでもMacでも/を使用）
        normalized = path.replace('\\', '/')
        
        # prompts/ディレクトリからの相対パスに変換
        if not normalized.startswith('prompts/'):
            normalized = f"prompts/{normalized}"
        
        # 最終的にOSに合わせたパス区切り文字に変換
        return os.path.normpath(normalized)

    def get_current_theme_file_path(self) -> str:
        """現在のテーマファイルパスを取得する（統一メソッド）"""
        try:
            from config import config
            # current_theme_fileが設定されていればそれを使用、なければdefault_theme_fileを使用
            current_theme = config.theme.get('current_theme_file')
            if current_theme and current_theme != 'null':
                return self._normalize_path(current_theme)
            else:
                default_theme = config.theme.get('default_theme_file', 'prompts/poem.txt')
                return self._normalize_path(default_theme)
        except Exception as e:
            print(f"[ModeManager] Error getting theme file from config: {e}")
            return self._normalize_path('prompts/poem.txt')  # フォールバック
    
    def get_theme_content(self, force_reload: bool = False) -> Optional[str]:
        """テーマ内容を取得する（キャッシュ機能付き）
        
        Args:
            force_reload: True の場合、キャッシュを無視して再読み込み
            
        Returns:
            テーマ内容（読み込み失敗時はNone）
        """
        current_path = self.get_current_theme_file_path()
        
        # キャッシュチェック（force_reloadが指定されていない場合）
        if not force_reload and current_path in self._theme_file_cache:
            print(f"[ModeManager] 🎯 Using cached theme content for: {current_path}")
            return self._theme_file_cache[current_path]
        
        # ファイル読み込み
        try:
            with open(current_path, "r", encoding="utf-8") as f:
                theme_content = f.read()
            
            # キャッシュに保存
            self._theme_file_cache[current_path] = theme_content
            self._current_theme_file_path = current_path
            self._theme_load_count += 1
            
            print(f"[ModeManager] 📖 Loaded theme file: {current_path} (load count: {self._theme_load_count})")
            return theme_content
            
        except Exception as e:
            print(f"[ModeManager] ❌ Error loading theme file {current_path}: {e}")
            return None
    
    def set_theme_file(self, theme_file_path: str, auto_load: bool = True) -> bool:
        """テーマファイルを動的に変更する（統一メソッド）
        
        Args:
            theme_file_path: 新しいテーマファイルのパス
            auto_load: True の場合、設定後に自動的にテーマ内容を読み込む
            
        Returns:
            成功時True、失敗時False
        """
        try:
            from config import config
            # 設定を更新（ランタイム変更）
            config.theme['current_theme_file'] = theme_file_path
            print(f"[ModeManager] Theme file path changed to: {theme_file_path}")
            
            if auto_load:
                # 新しいテーマファイルを読み込み（force_reload=True）
                theme_content = self.get_theme_content(force_reload=True)
                if theme_content:
                    self.start_themed_monologue(theme_content)
                    print(f"[ModeManager] ✅ Theme loaded and mode activated: {theme_file_path}")
                    return True
                else:
                    print(f"[ModeManager] ❌ Failed to load theme content from: {theme_file_path}")
                    return False
            else:
                return True
                
        except Exception as e:
            print(f"[ModeManager] ❌ Error setting theme file {theme_file_path}: {e}")
            return False
    
    def ensure_theme_loaded(self) -> bool:
        """テーマが読み込まれていることを確認し、必要に応じて読み込む
        
        Returns:
            テーマが利用可能な場合True
        """
        if self.active_theme_content:
            print("[ModeManager] ✅ Theme already loaded and active")
            return True
        
        # テーマ内容を読み込み
        theme_content = self.get_theme_content()
        if theme_content:
            self.start_themed_monologue(theme_content)
            print("[ModeManager] ✅ Theme loaded and activated")
            return True
        else:
            print("[ModeManager] ❌ Failed to ensure theme is loaded")
            return False
    
    def get_theme_info(self) -> Dict[str, Any]:
        """テーマ情報をデバッグ用に取得"""
        return {
            "current_theme_file": self._current_theme_file_path,
            "theme_cache_size": len(self._theme_file_cache),
            "theme_load_count": self._theme_load_count,
            "active_theme_length": len(self.active_theme_content) if self.active_theme_content else 0,
            "cached_files": list(self._theme_file_cache.keys())
        }
    
    def set_last_read_theme_content(self, theme_content: str):
        """読み上げ完了したテーマ内容を記録（プリフェッチ用）"""
        self._last_read_theme_content = theme_content
        print(f"[ModeManager] 📚 Recorded last read theme content ({len(theme_content)} chars)")
    
    def get_last_read_theme_content(self) -> Optional[str]:
        """最後に読み上げたテーマ内容を取得（プリフェッチ用）"""
        return self._last_read_theme_content

    def get_theme_intro(self) -> list[str]:
        """
        現在のテーマの導入部分（'---'より前の部分）を取得し、文に分割して返す。
        導入部がなければ空のリストを返す。
        """
        full_content = self.get_theme_content()
        if not full_content:
            return []

        # '---'で導入部と本文を分割
        parts = full_content.split('---', 1)
        intro_text = parts[0].strip()

        if not intro_text:
            return []

        # 導入部を文に分割する（改行を区切り文字とする）
        sentences = [s.strip() for s in intro_text.split('\n') if s.strip()]
        return sentences

    def get_last_utterance(self) -> Optional[str]:
        """最後のAIの発言を取得する。"""
        return self.last_ai_utterance