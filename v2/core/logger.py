import logging
import json
import sys
import time
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    """ログレベルの定義"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ComponentLogger:
    """
    v2システム用の構造化ロガー。
    各コンポーネントで統一されたログ形式を提供する。
    """
    
    def __init__(self, component_name: str, log_level: str = "INFO"):
        self.component_name = component_name
        self.logger = logging.getLogger(f"monologue_v2.{component_name}")
        
        # ログレベルの設定
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(numeric_level)
        
        # ハンドラーが既に存在しない場合のみ追加
        if not self.logger.handlers:
            # コンソールハンドラー
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            
            # カスタムフォーマッター
            formatter = StructuredFormatter()
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
        
        # ログプロパゲーションを無効にして重複を防ぐ
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """デバッグレベルのログ"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """インフォレベルのログ"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告レベルのログ"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """エラーレベルのログ"""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """クリティカルレベルのログ"""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """構造化ログの出力"""
        # メタデータの構築
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "component": self.component_name,
            "level": level.value,
            "message": message,
            **kwargs  # 追加のコンテキスト情報
        }
        
        # ログレベルに応じて出力
        if level == LogLevel.DEBUG:
            self.logger.debug("", extra={"structured_data": log_data})
        elif level == LogLevel.INFO:
            self.logger.info("", extra={"structured_data": log_data})
        elif level == LogLevel.WARNING:
            self.logger.warning("", extra={"structured_data": log_data})
        elif level == LogLevel.ERROR:
            self.logger.error("", extra={"structured_data": log_data})
        elif level == LogLevel.CRITICAL:
            self.logger.critical("", extra={"structured_data": log_data})
    
    # === 特殊なログメソッド ===
    
    def log_event(self, event_name: str, event_data: Dict[str, Any]):
        """イベントログ専用メソッド"""
        self.info(f"Event: {event_name}", event_type="event", event_data=event_data)
    
    def log_command(self, command_name: str, command_data: Dict[str, Any]):
        """コマンドログ専用メソッド"""
        self.info(f"Command: {command_name}", event_type="command", command_data=command_data)
    
    def log_api_call(self, api_name: str, duration: float, success: bool, **kwargs):
        """API呼び出しログ専用メソッド"""
        level = LogLevel.INFO if success else LogLevel.ERROR
        self._log(level, f"API Call: {api_name}", 
                 event_type="api_call", api_name=api_name, 
                 duration=duration, success=success, **kwargs)
    
    def log_state_change(self, old_state: str, new_state: str, **kwargs):
        """状態変更ログ専用メソッド"""
        self.info(f"State Change: {old_state} → {new_state}", 
                 event_type="state_change", old_state=old_state, 
                 new_state=new_state, **kwargs)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """パフォーマンスログ専用メソッド"""
        self.info(f"Performance: {operation}", 
                 event_type="performance", operation=operation, 
                 duration=duration, **kwargs)
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """エラーログにコンテキスト情報を付加"""
        self.error(f"Exception: {str(error)}", 
                  event_type="error", error_type=type(error).__name__, 
                  error_message=str(error), context=context)


class StructuredFormatter(logging.Formatter):
    """構造化ログ用のカスタムフォーマッター"""
    
    def format(self, record):
        if hasattr(record, 'structured_data'):
            # 構造化データが存在する場合
            data = record.structured_data
            # 人間が読みやすい形式でフォーマット
            timestamp = data.get('timestamp', '')
            component = data.get('component', '')
            level = data.get('level', '')
            message = data.get('message', '')
            
            # 基本情報の表示
            formatted = f"[{timestamp}] [{level}] [{component}] {message}"
            
            # 追加情報があれば表示
            extra_data = {k: v for k, v in data.items() 
                         if k not in ['timestamp', 'component', 'level', 'message']}
            if extra_data:
                formatted += f" | {json.dumps(extra_data, ensure_ascii=False, separators=(',', ':'))}"
            
            return formatted
        else:
            # 通常のログの場合はデフォルトフォーマットを使用
            return super().format(record)


# === グローバルロガーファクトリ ===

_loggers: Dict[str, ComponentLogger] = {}

def get_logger(component_name: str, log_level: str = "INFO") -> ComponentLogger:
    """
    コンポーネント名に基づいてロガーを取得する（シングルトンパターン）
    
    Args:
        component_name: コンポーネント名
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        
    Returns:
        ComponentLogger: 指定されたコンポーネント用のロガー
    """
    if component_name not in _loggers:
        _loggers[component_name] = ComponentLogger(component_name, log_level)
    return _loggers[component_name]


# === パフォーマンス測定用デコレータ ===

def log_performance(component_name: str):
    """関数の実行時間を自動ログ出力するデコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(component_name)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log_performance(func.__name__, duration, success=True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.log_performance(func.__name__, duration, success=False, error=str(e))
                raise
        return wrapper
    return decorator