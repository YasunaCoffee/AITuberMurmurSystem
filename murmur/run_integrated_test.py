#!/usr/bin/env python3
"""
v2システムの統合テスト
実際のYouTubeライブコメントと接続してシステム全体を動作確認
"""

import os
import sys
import time
import threading
from typing import Dict, Any
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from murmur.controllers.main_controller import MainController
from murmur.core.logger import ComponentLogger
from murmur.core.metrics import get_metrics_collector
from murmur.state.state_manager import StateManager, SystemState
from murmur.core.event_queue import EventQueue


class SystemTestRunner:
    """v2システムの統合テスト実行クラス"""
    
    def __init__(self):
        self.logger = ComponentLogger(__name__)
        self.metrics = get_metrics_collector()
        self.controller = None
        self.test_duration = 15  # 15秒間テスト
        self.results = {}
        
    def run_integration_test(self):
        """統合テストの実行"""
        print("=== v2 System Integration Test ===")
        print(f"📺 Video ID: {os.getenv('YOUTUBE_VIDEO_ID')}")
        print(f"⏱️  Test Duration: {self.test_duration} seconds")
        print("=" * 50)
        
        try:
            # システム初期化
            print("🚀 Initializing v2 system...")
            event_queue = EventQueue()
            state_manager = StateManager()
            self.controller = MainController(event_queue, state_manager)
            
            # システム開始
            print("▶️  Starting system...")
            start_time = time.time()
            
            # システム起動（別スレッドで実行）
            system_thread = threading.Thread(target=self._run_system, daemon=True)
            system_thread.start()
            
            # メトリクス監視
            monitoring_thread = threading.Thread(target=self._monitor_metrics, daemon=True)
            monitoring_thread.start()
            
            # テスト実行
            print(f"📡 Running test for {self.test_duration} seconds...")
            print("Press Ctrl+C to stop early\n")
            
            time.sleep(self.test_duration)
            
            # システム停止
            print("\n⏹️  Stopping system...")
            self.controller.state_manager.is_running = False
            
            elapsed = time.time() - start_time
            
            # 結果表示
            self._display_results(elapsed)
            
            return True
            
        except KeyboardInterrupt:
            print("\n⏹️  Test interrupted by user")
            if self.controller:
                self.controller.state_manager.is_running = False
            return False
            
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
            self.logger.error("integration_test_failed", error=str(e))
            return False
    
    def _run_system(self):
        """システムメインループの実行"""
        try:
            self.controller.run()
        except Exception as e:
            self.logger.error("system_main_loop_error", error=str(e))
    
    def _monitor_metrics(self):
        """メトリクス監視"""
        monitor_interval = 10  # 10秒間隔
        
        while True:
            try:
                time.sleep(monitor_interval)
                
                # システム状態の記録
                if self.controller and hasattr(self.controller, 'state_manager'):
                    state = self.controller.state_manager.current_state
                    self.metrics.record_gauge("SystemMonitor", "current_state", state.value)
                
                # メトリクス概要の表示
                summary = self.metrics.get_metrics_summary()
                if summary.get('counters') or summary.get('performance'):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 System active - "
                          f"Events: {sum(summary.get('counters', {}).values())}")
                
            except Exception as e:
                self.logger.error("metrics_monitoring_error", error=str(e))
                continue
    
    def _display_results(self, elapsed_time: float):
        """テスト結果の表示"""
        print("\n" + "=" * 50)
        print("📊 Integration Test Results")
        print("=" * 50)
        
        # 基本統計
        print(f"⏱️  Test Duration: {elapsed_time:.1f} seconds")
        
        # メトリクス統計
        summary = self.metrics.get_metrics_summary()
        
        if summary.get('counters'):
            print("\n📈 Event Counters:")
            for key, count in summary['counters'].items():
                print(f"   - {key}: {count}")
        
        if summary.get('performance'):
            print("\n⚡ Performance Metrics:")
            for key, stats in summary['performance'].items():
                avg_time = stats.get('avg_duration_sec', 0)
                success_rate = stats.get('success_rate', 0) * 100
                print(f"   - {key}: {avg_time:.2f}s avg, {success_rate:.1f}% success")
        
        if summary.get('gauges'):
            print("\n📊 Current Values:")
            for key, value in summary['gauges'].items():
                print(f"   - {key}: {value}")
        
        # システム健全性
        health = self.metrics.get_system_health()
        print(f"\n🏥 System Health: {health.get('overall_status', 'unknown')}")
        
        if health.get('issues'):
            print("⚠️  Issues detected:")
            for issue in health['issues']:
                print(f"   - {issue}")
        
        print("\n✅ Integration test completed!")


def main():
    """メイン実行関数"""
    # 環境チェック
    if not os.getenv('YOUTUBE_VIDEO_ID'):
        print("❌ YOUTUBE_VIDEO_ID not set in environment")
        print("Please set it in your .env file")
        return False
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not set in environment")
        print("Please set it in your .env file")
        return False
    
    # テスト実行
    runner = SystemTestRunner()
    success = runner.run_integration_test()
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)