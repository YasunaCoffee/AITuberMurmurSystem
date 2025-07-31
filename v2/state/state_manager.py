from typing import List, Dict, Any, Optional
import time
from enum import Enum
from v2.core.logger import get_logger


class SystemState(Enum):
    """システムの現在の動作状態"""
    IDLE = "idle"              # 待機中
    THINKING = "thinking"      # 思考中（LLMに問い合わせ中）
    SPEAKING = "speaking"      # 発話中（音声再生中）
    READING = "reading"        # 朗読中（コメント受付中断）
    STARTING = "starting"


class StateManager:
    """
    アプリケーション全体の状態を保持するデータコンテナ。
    V2アーキテクチャでは、このクラスはスレッド同期用のフラグを持たず、
    純粋に状態の保持と提供に専念する。
    """
    def __init__(self):
        # 会話履歴（V1のConversationHistoryに相当）
        self.conversation_history: List[Dict[str, Any]] = []

        # 現在の会話モード（例: "normal", "chill_chat"）
        self.current_mode: str = "normal"

        # アプリケーションが実行中かどうかを示すフラグ
        self.is_running: bool = True

        # システムの現在状態
        self.current_state: SystemState = SystemState.IDLE
        
        # 現在のタスク情報
        self.current_task_id: Optional[str] = None
        self.current_task_type: Optional[str] = None  # "monologue", "comment_response"
        self.task_start_time: Optional[float] = None
        
        # 最後の発話/思考情報
        self.last_speech_content: Optional[str] = None
        self.last_speech_time: Optional[float] = None
        
        # コメントキュー（処理待ちコメント）
        self.pending_comments: List[Dict[str, Any]] = []
        
        # その他の設定値や状態
        # 例: self.user_name = "test_user"
        # 例: self.ng_words = []
        self.logger = get_logger("StateManager")

    def add_conversation_entry(self, role: str, content: str):
        """会話履歴に新しいエントリを追加する。"""
        self.conversation_history.append({"role": role, "content": content})

    def get_latest_conversation(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最新の会話履歴を取得する。"""
        return self.conversation_history[-limit:]
    
    # === 状態管理メソッド ===
    
    def set_state(self, new_state: SystemState, task_id: Optional[str] = None, task_type: Optional[str] = None):
        """システム状態を変更する"""
        self.logger.info(
            "--- SET STATE ---", 
            old_state=self.current_state.value, 
            new_state=new_state.value,
            old_task_id=self.current_task_id,
            new_task_id=task_id,
            old_task_type=self.current_task_type,
            new_task_type=task_type,
        )
        self.current_state = new_state
        self.current_task_id = task_id
        self.current_task_type = task_type
        
        if new_state in [SystemState.THINKING, SystemState.SPEAKING]:
            self.task_start_time = time.time()
        else:
            self.task_start_time = None
    
    def is_idle(self) -> bool:
        """システムが待機中かどうかを判定"""
        return self.current_state == SystemState.IDLE
    
    def is_busy(self) -> bool:
        """システムが処理中（思考中または発話中）かどうかを判定"""
        return self.current_state in [SystemState.THINKING, SystemState.SPEAKING]
    
    def can_handle_comment(self) -> bool:
        """コメントを処理できるかどうかを判定"""
        # 朗読中はコメントを処理しない
        if self.current_state == SystemState.READING:
            return False
        # 現在待機中、または発話中でも緊急性の高いコメントは処理可能
        return self.current_state in [SystemState.IDLE, SystemState.SPEAKING]
    
    def get_task_duration(self) -> Optional[float]:
        """現在のタスクの実行時間を取得"""
        if self.task_start_time is None:
            return None
        return time.time() - self.task_start_time
    
    def finish_task(self):
        """現在のタスクを完了してIDLE状態に戻す"""
        self.logger.info(
            "--- FINISHING TASK ---",
            finished_task_id=self.current_task_id,
            finished_task_type=self.current_task_type
        )
        self.set_state(SystemState.IDLE)
        # last_speech_content の更新は finish_task の責務ではないので削除
    
    # === コメントキュー管理 ===
    
    def add_pending_comment(self, comment: Dict[str, Any]):
        """処理待ちコメントキューに追加"""
        self.pending_comments.append(comment)
    
    def get_pending_comments(self, clear: bool = True) -> List[Dict[str, Any]]:
        """処理待ちコメントを取得（デフォルトではキューをクリア）"""
        comments = self.pending_comments.copy()
        if clear:
            self.pending_comments.clear()
        return comments
    
    def add_prepared_response(self, task_id: str, sentences: List[str]):
        """並行処理で生成された応答を保存"""
        if not hasattr(self, 'prepared_responses'):
            self.prepared_responses: List[Dict[str, Any]] = []
        
        response_data = {
            'task_id': task_id,
            'sentences': sentences,
            'timestamp': time.time()
        }
        self.prepared_responses.append(response_data)
    
    def get_prepared_responses(self, clear: bool = True) -> List[Dict[str, Any]]:
        """生成済み応答を取得"""
        if not hasattr(self, 'prepared_responses'):
            return []
        
        responses = self.prepared_responses.copy()
        if clear:
            self.prepared_responses.clear()
        return responses
    
    def has_prepared_responses(self) -> bool:
        """生成済み応答があるかチェック"""
        return hasattr(self, 'prepared_responses') and len(self.prepared_responses) > 0

    def has_pending_comments(self) -> bool:
        """処理待ちコメントがあるかどうかを判定"""
        return len(self.pending_comments) > 0
    
    # === 統計情報 ===
    
    def get_status_summary(self) -> Dict[str, Any]:
        """現在の状態をサマリー形式で取得"""
        return {
            "state": self.current_state.value,
            "task_id": self.current_task_id,
            "task_type": self.current_task_type,
            "task_duration": self.get_task_duration(),
            "pending_comments_count": len(self.pending_comments),
            "conversation_history_count": len(self.conversation_history),
            "last_speech_time": self.last_speech_time,
            "is_running": self.is_running
        } 