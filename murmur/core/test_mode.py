#!/usr/bin/env python3
"""
テストモードシステム

アプリケーション全体のテストモードを統一管理し、
コンポーネントごとにテスト用の設定と動作を提供する。
"""

import os
import sys
import time
import threading
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field


class TestMode(Enum):
    """テストモードの種類"""
    PRODUCTION = "production"       # 本番モード（通常運用）
    INTEGRATION = "integration"     # 統合テスト（実際のAPIを使用、短縮動作）
    UNIT = "unit"                  # ユニットテスト（モック使用）
    DEMO = "demo"                  # デモモード（模擬データ使用）
    DEBUG = "debug"                # デバッグモード（詳細ログ出力）


@dataclass
class TestConfig:
    """テストモード固有の設定"""
    mode: TestMode
    
    # API設定
    use_mock_openai: bool = False
    use_mock_audio: bool = False
    use_mock_youtube: bool = False
    
    # タイムアウト設定
    api_timeout: float = 30.0
    audio_timeout: float = 10.0
    comment_check_interval: float = 3.0
    
    # データ設定
    dummy_comments_enabled: bool = False
    dummy_comment_interval: float = 10.0
    max_dummy_comments: int = 5
    
    # ログ設定
    verbose_logging: bool = False
    log_api_calls: bool = False
    log_performance: bool = False
    
    # 実行制限
    max_runtime_minutes: Optional[int] = None
    auto_stop_enabled: bool = False
    
    # 追加設定
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class TestModeManager:
    """テストモードの統一管理クラス"""
    
    def __init__(self):
        self._current_mode = TestMode.PRODUCTION
        self._config = TestConfig(TestMode.PRODUCTION)
        self._start_time = time.time()
        self._stop_timer: Optional[threading.Timer] = None
        self._registered_components: Dict[str, Any] = {}
        
        # 環境変数からテストモードを検出
        self._detect_test_mode()
        
    def _detect_test_mode(self):
        """環境変数からテストモードを自動検出"""
        env_test_mode = os.getenv('TEST_MODE', '').lower()
        env_chat_test = os.getenv('CHAT_TEST_MODE', 'false').lower() == 'true'
        env_debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        if env_test_mode:
            try:
                detected_mode = TestMode(env_test_mode)
                self.set_mode(detected_mode)
                print(f"[TestMode] Detected from TEST_MODE env: {detected_mode.value}")
            except ValueError:
                print(f"[TestMode] Invalid TEST_MODE env value: {env_test_mode}")
        
        elif env_chat_test:
            self.set_mode(TestMode.UNIT)
            print(f"[TestMode] Detected from CHAT_TEST_MODE: {self._current_mode.value}")
        
        elif env_debug:
            self.set_mode(TestMode.DEBUG)
            print(f"[TestMode] Detected from DEBUG: {self._current_mode.value}")
        
        else:
            print(f"[TestMode] Using default mode: {self._current_mode.value}")
    
    def set_mode(self, mode: TestMode, custom_config: Optional[Dict[str, Any]] = None):
        """テストモードを設定"""
        self._current_mode = mode
        self._config = self._create_config_for_mode(mode, custom_config)
        
        print(f"[TestMode] Switched to {mode.value} mode")
        if self._config.verbose_logging:
            print(f"[TestMode] Config: {self._config}")
        
        # 自動停止タイマーを設定
        if self._config.auto_stop_enabled and self._config.max_runtime_minutes:
            self._setup_auto_stop()
        
        # 登録されたコンポーネントに通知
        self._notify_components_mode_change()
    
    def _create_config_for_mode(self, mode: TestMode, custom_config: Optional[Dict[str, Any]] = None) -> TestConfig:
        """モード別の設定を作成"""
        base_config = {
            TestMode.PRODUCTION: TestConfig(
                mode=mode,
                use_mock_openai=False,
                use_mock_audio=False,
                use_mock_youtube=False,
                verbose_logging=False,
                dummy_comments_enabled=False
            ),
            TestMode.INTEGRATION: TestConfig(
                mode=mode,
                use_mock_openai=False,
                use_mock_audio=True,
                use_mock_youtube=True,
                api_timeout=15.0,
                comment_check_interval=2.0,
                verbose_logging=True,
                dummy_comments_enabled=True,
                dummy_comment_interval=5.0,
                max_runtime_minutes=10,
                auto_stop_enabled=True
            ),
            TestMode.UNIT: TestConfig(
                mode=mode,
                use_mock_openai=True,
                use_mock_audio=True,
                use_mock_youtube=True,
                api_timeout=5.0,
                audio_timeout=1.0,
                comment_check_interval=1.0,
                verbose_logging=True,
                log_api_calls=True,
                dummy_comments_enabled=True,
                dummy_comment_interval=3.0,
                max_dummy_comments=3,
                max_runtime_minutes=5,
                auto_stop_enabled=True
            ),
            TestMode.DEMO: TestConfig(
                mode=mode,
                use_mock_openai=False,
                use_mock_audio=False,
                use_mock_youtube=True,
                comment_check_interval=5.0,
                verbose_logging=True,
                dummy_comments_enabled=True,
                dummy_comment_interval=15.0,
                max_dummy_comments=10,
                max_runtime_minutes=30,
                auto_stop_enabled=True
            ),
            TestMode.DEBUG: TestConfig(
                mode=mode,
                use_mock_openai=False,
                use_mock_audio=False,
                use_mock_youtube=False,
                verbose_logging=True,
                log_api_calls=True,
                log_performance=True,
                comment_check_interval=2.0
            )
        }
        
        config = base_config[mode]
        
        # カスタム設定を適用
        if custom_config:
            for key, value in custom_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    config.custom_settings[key] = value
        
        return config
    
    def _setup_auto_stop(self):
        """自動停止タイマーを設定"""
        if self._stop_timer:
            self._stop_timer.cancel()
        
        runtime_seconds = self._config.max_runtime_minutes * 60
        self._stop_timer = threading.Timer(runtime_seconds, self._auto_stop)
        self._stop_timer.daemon = True
        self._stop_timer.start()
        
        print(f"[TestMode] Auto-stop timer set for {self._config.max_runtime_minutes} minutes")
    
    def _auto_stop(self):
        """自動停止実行"""
        print(f"[TestMode] Auto-stop triggered after {self._config.max_runtime_minutes} minutes")
        print(f"[TestMode] Sending SIGINT to process...")
        
        import signal
        os.kill(os.getpid(), signal.SIGINT)
    
    def register_component(self, name: str, component: Any):
        """コンポーネントをテストモード管理に登録"""
        self._registered_components[name] = component
        print(f"[TestMode] Registered component: {name}")
        
        # 現在のモードを即座に通知
        if hasattr(component, 'on_test_mode_change'):
            component.on_test_mode_change(self._current_mode, self._config)
    
    def _notify_components_mode_change(self):
        """登録されたコンポーネントにモード変更を通知"""
        for name, component in self._registered_components.items():
            try:
                if hasattr(component, 'on_test_mode_change'):
                    component.on_test_mode_change(self._current_mode, self._config)
                    print(f"[TestMode] Notified {name} of mode change")
            except Exception as e:
                print(f"[TestMode] Error notifying {name}: {e}")
    
    def get_mode(self) -> TestMode:
        """現在のテストモードを取得"""
        return self._current_mode
    
    def get_config(self) -> TestConfig:
        """現在のテスト設定を取得"""
        return self._config
    
    def is_production(self) -> bool:
        """本番モードかどうか"""
        return self._current_mode == TestMode.PRODUCTION
    
    def is_test_mode(self) -> bool:
        """何らかのテストモードかどうか"""
        return self._current_mode != TestMode.PRODUCTION
    
    def get_runtime_minutes(self) -> float:
        """実行時間（分）を取得"""
        return (time.time() - self._start_time) / 60
    
    def get_status(self) -> Dict[str, Any]:
        """テストモードの状態を取得"""
        return {
            'mode': self._current_mode.value,
            'runtime_minutes': self.get_runtime_minutes(),
            'max_runtime_minutes': self._config.max_runtime_minutes,
            'auto_stop_enabled': self._config.auto_stop_enabled,
            'registered_components': list(self._registered_components.keys()),
            'config': {
                'use_mock_openai': self._config.use_mock_openai,
                'use_mock_audio': self._config.use_mock_audio,
                'use_mock_youtube': self._config.use_mock_youtube,
                'dummy_comments_enabled': self._config.dummy_comments_enabled,
                'verbose_logging': self._config.verbose_logging
            }
        }
    
    def shutdown(self):
        """テストモード管理を終了"""
        if self._stop_timer:
            self._stop_timer.cancel()
        print(f"[TestMode] Shutdown after {self.get_runtime_minutes():.1f} minutes")


# グローバルインスタンス
test_mode_manager = TestModeManager()


def get_test_mode() -> TestMode:
    """現在のテストモードを取得"""
    return test_mode_manager.get_mode()


def get_test_config() -> TestConfig:
    """現在のテスト設定を取得"""
    return test_mode_manager.get_config()


def is_test_mode() -> bool:
    """テストモードかどうか"""
    return test_mode_manager.is_test_mode()


def register_test_component(name: str, component: Any):
    """コンポーネントをテストモード管理に登録"""
    test_mode_manager.register_component(name, component)


# テスト用のダミーデータ生成
class DummyDataGenerator:
    """テスト用のダミーデータ生成器"""
    
    @staticmethod
    def generate_dummy_comment(index: int = 0) -> Dict[str, Any]:
        """ダミーコメントを生成"""
        current_time = time.time()
        comment_templates = [
            "テストコメント {index}",
            "こんにちは！",
            "面白い話ですね",
            "AIについてどう思いますか？",
            "小説の話をもっと聞きたいです",
            "今日の配信も楽しみです"
        ]
        
        template = comment_templates[index % len(comment_templates)]
        message = template.format(index=index)
        
        return {
            "username": f"テストユーザー{index}",
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
            "user_id": f"test_user_{index}",
            "message_id": f"test_msg_{int(current_time)}_{index}",
            "author": {
                "name": f"テストユーザー{index}",
                "channel_id": f"test_channel_{index}",
                "is_owner": index == 0,
                "is_moderator": index % 5 == 0,
                "is_verified": index % 3 == 0,
                "badge_url": None
            },
            "superchat": None
        }
    
    @staticmethod
    def generate_dummy_response(prompt: str) -> str:
        """ダミーAI応答を生成"""
        responses = [
            "それは興味深い観点ですね。私も同じように考えます。",
            "確かにその通りです。もう少し詳しく教えていただけますか？",
            "なるほど、そういう見方もありますね。",
            "コメントありがとうございます！とても参考になります。",
            "その話題について、私なりの考えを述べさせていただきますと..."
        ]
        
        return responses[hash(prompt) % len(responses)]


if __name__ == "__main__":
    # テスト実行
    print("=== Test Mode Manager Test ===")
    
    manager = TestModeManager()
    print(f"Current mode: {manager.get_mode()}")
    print(f"Status: {manager.get_status()}")
    
    # モード変更テスト
    manager.set_mode(TestMode.UNIT)
    print(f"After mode change: {manager.get_mode()}")
    
    # ダミーデータ生成テスト
    generator = DummyDataGenerator()
    dummy_comment = generator.generate_dummy_comment(1)
    print(f"Dummy comment: {dummy_comment}")
    
    dummy_response = generator.generate_dummy_response("test prompt")
    print(f"Dummy response: {dummy_response}")