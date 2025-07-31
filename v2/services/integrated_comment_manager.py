import threading
import time
import os
from typing import List, Any, Dict, Optional
from v2.core.event_queue import EventQueue
from v2.core.events import NewCommentReceived
from v2.core.test_mode import test_mode_manager, TestMode, TestConfig, DummyDataGenerator
from config import config

try:
    import pytchat
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    print(
        "[IntegratedCommentManager] Warning: pytchat not available, "
        "using simulation mode"
    )


class IntegratedCommentManager:
    """
    コメントの取得と管理を担当するサービス。
    新しいコメントを定期的に取得し、NewCommentReceivedイベントを発行する。
    """

    def __init__(self, event_queue: EventQueue, video_id: Optional[str] = None):
        self.event_queue = event_queue
        self.video_id = video_id or os.getenv('YOUTUBE_VIDEO_ID')
        
        # テストモードの確認（新しいシステムを優先）
        test_config = test_mode_manager.get_config()
        self.test_mode = test_config.use_mock_youtube
        self.dummy_generator = DummyDataGenerator()
        self.dummy_comment_counter = 0
        
        # スレッド制御
        self.running = False
        self.monitor_thread = None

        # YouTube接続
        self.chat = None
        # テストモードが有効の場合は強制的にシミュレーションモード
        self.youtube_enabled = (
            not self.test_mode and YOUTUBE_AVAILABLE and self.video_id
        )
        
        # コメント管理
        self.recent_comments: List[Dict[str, Any]] = []
        self.processed_comment_ids = set()  # 処理済みコメントIDを保持
        self.comment_cache: Dict[str, Any] = {}
        self.last_check_time = time.time()
        
        # テストモード管理に登録（属性初期化後）
        test_mode_manager.register_component("IntegratedCommentManager", self)
        
        test_mode_name = test_mode_manager.get_mode().value
        if self.test_mode:
            print(f"[IntegratedCommentManager] Running in TEST MODE "
                  f"({test_mode_name})")
        elif self.youtube_enabled:
            print(
                "[IntegratedCommentManager] Initialized for YouTube video: "
                f"{self.video_id}"
            )
        else:
            print("[IntegratedCommentManager] Initialized in simulation mode")

    def on_test_mode_change(self, new_mode: TestMode, new_config: TestConfig):
        """テストモードの変更を処理するコールバック"""
        old_test_mode = self.test_mode
        self.test_mode = new_config.use_mock_youtube
        
        print(f"[IntegratedCommentManager] Test mode changed: {old_test_mode} -> {self.test_mode} ({new_mode.value})")

        # 実行中にモードが変更された場合、監視スレッドを再起動
        if self.running and old_test_mode != self.test_mode:
            print("[IntegratedCommentManager] Restarting monitor thread due to mode change...")
            # 既存スレッドを停止
            self.stop()
            # 新しいモードで再開
            self.start()

    def start(self):
        """コメント監視を開始する"""
        if self.running:
            print("[IntegratedCommentManager] Already running")
            return
        
        if self.test_mode:
            print("[IntegratedCommentManager] Starting in TEST MODE - using dummy comments")
        else:
            # YouTube接続を初期化
            if self.youtube_enabled:
                try:
                    self.chat = pytchat.create(video_id=self.video_id)
                    print(
                        "[IntegratedCommentManager] Connected to YouTube chat "
                        f"for video: {self.video_id}"
                    )
                except Exception as e:
                    print(
                        "[IntegratedCommentManager] Failed to connect to YouTube: "
                        f"{e}"
                    )
                    self.youtube_enabled = False
            
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_comments,
            daemon=True,
            name="CommentMonitor"
        )
        self.monitor_thread.start()
        
        mode_status = (
            "TEST MODE" if self.test_mode else
            ("YouTube Live" if self.youtube_enabled else "Simulation")
        )
        print(
            "[IntegratedCommentManager] Comment monitoring started in "
            f"{mode_status} mode"
        )

    def stop(self):
        """コメント監視を停止する"""
        self.running = False
        
        # YouTube接続を終了
        if self.chat:
            try:
                self.chat.terminate()
                print(
                    "[IntegratedCommentManager] YouTube chat connection terminated"
                )
            except Exception as e:
                print(
                    "[IntegratedCommentManager] Error terminating YouTube chat: "
                    f"{e}"
                )
            
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        print("[IntegratedCommentManager] Comment monitoring stopped")

    def _monitor_comments(self):
        """コメントを定期的に監視するメインループ"""
        print("[IntegratedCommentManager] Starting comment monitoring loop")
        
        while self.running:
            try:
                # 新しいコメントをチェック
                new_comments = self._fetch_new_comments()
                
                if new_comments:
                    print(f"[IntegratedCommentManager] Found {len(new_comments)} new comments")
                    
                    # 新規コメントイベントを発行
                    event = NewCommentReceived(comments=new_comments)
                    self.event_queue.put(event)
                    
                    # コメントをキャッシュに追加
                    self._cache_comments(new_comments)
                
                # running状態をチェックしてから短時間待機（テストモード対応）
                test_config = test_mode_manager.get_config()
                sleep_interval = test_config.comment_check_interval if test_mode_manager.is_test_mode() else getattr(config, 'comment_check_interval', 3.0)
                
                for _ in range(int(sleep_interval * 10)):  # 0.1秒刻みでチェック
                    if not self.running:
                        break
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"[IntegratedCommentManager] Error during comment monitoring: {e}")
                # エラー時も短時間待機で応答性を保つ
                for _ in range(50):  # 5秒待機
                    if not self.running:
                        break
                    time.sleep(0.1)
                    
        print("[IntegratedCommentManager] Comment monitoring loop finished")

    def _fetch_new_comments(self) -> List[Dict[str, Any]]:
        """
        新しいコメントを取得する。
        YouTube API (pytchat) または シミュレーションモードで動作。
        """
        if self.test_mode:
            # テストモードが有効な場合は強制的にダミーコメント
            return self._fetch_dummy_comments()
        elif self.youtube_enabled and self.chat:
            return self._fetch_youtube_comments()
        else:
            return self._fetch_dummy_comments()
    
    def _safe_get_author_attr(self, author, attr_names: List[str], default_value):
        """
        Authorオブジェクトから属性を安全に取得する
        
        Args:
            author: pytchatのAuthorオブジェクト
            attr_names: 試行する属性名のリスト
            default_value: デフォルト値
        """
        for attr_name in attr_names:
            if hasattr(author, attr_name):
                return getattr(author, attr_name)
        return default_value

    def _fetch_youtube_comments(self) -> List[Dict[str, Any]]:
        """YouTube APIから実際のコメントを取得する"""
        try:
            if not self.chat.is_alive():
                # 接続が失われた場合はYouTube接続を無効化
                if self.youtube_enabled:
                    print("[IntegratedCommentManager] YouTube chat connection lost, disabling YouTube mode")
                    self.youtube_enabled = False
                return []
            
            new_comments = []
            for comment in self.chat.get().sync_items():
                if comment.id in self.processed_comment_ids:
                    continue  # 既に処理済みのコメントはスキップ
                
                comment_data = {
                    "username": comment.author.name,
                    "message": comment.message,
                    "timestamp": comment.datetime,
                    "user_id": comment.author.channelId,
                    "message_id": comment.id,
                    "author": {
                        "name": comment.author.name,
                        "channel_id": comment.author.channelId,
                        "is_owner": self._safe_get_author_attr(comment.author, ['isOwner', 'is_owner'], False),
                        "is_moderator": self._safe_get_author_attr(comment.author, ['isModerator', 'is_moderator'], False),
                        "is_verified": self._safe_get_author_attr(comment.author, ['isVerified', 'is_verified'], False),
                        "badge_url": self._safe_get_author_attr(comment.author, ['badgeUrl', 'badge_url'], None)
                    },
                    "superchat": {
                        "amount": comment.amountValue if hasattr(comment, 'amountValue') else None,
                        "currency": comment.currency if hasattr(comment, 'currency') else None,
                        "amount_string": comment.amountString if hasattr(comment, 'amountString') else None
                    } if hasattr(comment, 'amountValue') else None
                }
                new_comments.append(comment_data)
                self.processed_comment_ids.add(comment.id)
            
            if new_comments:
                print(
                    f"[IntegratedCommentManager] Fetched {len(new_comments)} "
                    "new YouTube comments"
                )
                
            return new_comments
            
        except Exception as e:
            print(
                "[IntegratedCommentManager] Error fetching YouTube comments: "
                f"{e}"
            )
            return []
    
    def _fetch_dummy_comments(self) -> List[Dict[str, Any]]:
        """シミュレーション用のダミーコメントを生成する（テストモード対応）"""
        current_time = time.time()
        
        # テストモード設定を取得
        test_config = test_mode_manager.get_config()
        interval = test_config.dummy_comment_interval if test_mode_manager.is_test_mode() else 10.0
        max_comments = test_config.max_dummy_comments if test_mode_manager.is_test_mode() else 1
        
        # 指定間隔でダミーコメントを生成
        if current_time - self.last_check_time > interval:
            self.last_check_time = current_time
            
            # テスト設定に基づいてコメント数を制限
            if not test_config.dummy_comments_enabled:
                return []
            
            # 新しいダミーデータ生成器を使用
            dummy_comments = []
            for i in range(min(max_comments, 1)):  # 基本的に1つずつ生成
                comment = self.dummy_generator.generate_dummy_comment(self.dummy_comment_counter)
                dummy_comments.append(comment)
                self.dummy_comment_counter += 1
            
            if test_config.verbose_logging:
                print(f"[IntegratedCommentManager] Generated {len(dummy_comments)} dummy comments")
            
            return dummy_comments
        
        return []

    def _cache_comments(self, comments: List[Dict[str, Any]]):
        """コメントをキャッシュに保存する"""
        # このメソッドは現在重複排除には寄与していないため、
        # user_idベースのキャッシュとしての役割のみとする。
        # processed_comment_idsが重複排除の主役。
        for comment in comments:
            # ユーザーIDをキーとしてキャッシュ
            user_id = comment.get('user_id', comment.get('username', 'unknown'))
            self.comment_cache[user_id] = comment
            
        # 最近のコメントリストに追加（最大100件まで保持）
        self.recent_comments.extend(comments)
        if len(self.recent_comments) > 100:
            self.recent_comments = self.recent_comments[-100:]

    def add_comment(self, comment_data: Dict[str, Any]):
        """外部からコメントを手動で追加する（テスト用）"""
        self._cache_comments([comment_data])
        event = NewCommentReceived(comments=[comment_data])
        self.event_queue.put(event)
        print(
            "[IntegratedCommentManager] Manually added comment: "
            f"{comment_data.get('message', 'No message')}"
        )

    def get_recent_comments(self, count: int = 10) -> List[Dict[str, Any]]:
        """最近のコメントを取得する"""
        return self.recent_comments[-count:]

    def get_user_comment_history(self, user_id: str) -> Dict[str, Any]:
        """特定ユーザーのコメント履歴を取得する"""
        return self.comment_cache.get(user_id, {})
    