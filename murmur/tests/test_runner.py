#!/usr/bin/env python3
"""
テストモード実行ツール

様々なテストモードでシステムを起動・実行するためのツール
"""

import sys
import os
import argparse
import time
import signal
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from murmur.core.test_mode import test_mode_manager, TestMode


class TestRunner:
    """テスト実行管理クラス"""
    
    def __init__(self):
        self.start_time = time.time()
        self.running = True
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """シグナル受信時の処理"""
        print(f"\n[TestRunner] Signal {signum} received. Shutting down...")
        self.running = False
        test_mode_manager.shutdown()
        sys.exit(0)
    
    def run_unit_test(self, duration_minutes: Optional[int] = None):
        """ユニットテストモードで実行"""
        print("=== Unit Test Mode ===")
        
        custom_config = {}
        if duration_minutes:
            custom_config['max_runtime_minutes'] = duration_minutes
            custom_config['auto_stop_enabled'] = True
        
        test_mode_manager.set_mode(TestMode.UNIT, custom_config)
        self._run_main_system()
    
    def run_integration_test(self, duration_minutes: Optional[int] = None):
        """統合テストモードで実行"""
        print("=== Integration Test Mode ===")
        
        custom_config = {}
        if duration_minutes:
            custom_config['max_runtime_minutes'] = duration_minutes
            custom_config['auto_stop_enabled'] = True
        
        test_mode_manager.set_mode(TestMode.INTEGRATION, custom_config)
        self._run_main_system()
    
    def run_demo_mode(self, duration_minutes: Optional[int] = None):
        """デモモードで実行"""
        print("=== Demo Mode ===")
        
        custom_config = {}
        if duration_minutes:
            custom_config['max_runtime_minutes'] = duration_minutes
            custom_config['auto_stop_enabled'] = True
        
        test_mode_manager.set_mode(TestMode.DEMO, custom_config)
        self._run_main_system()
    
    def run_debug_mode(self):
        """デバッグモードで実行"""
        print("=== Debug Mode ===")
        
        test_mode_manager.set_mode(TestMode.DEBUG)
        self._run_main_system()
    
    def run_keyboard_interrupt_test(self):
        """KeyboardInterrupt機能テスト"""
        print("=== Keyboard Interrupt Test ===")
        
        # 短時間のユニットテストモードで実行
        custom_config = {
            'max_runtime_minutes': 1,
            'auto_stop_enabled': False,  # 手動停止テストのため
            'dummy_comment_interval': 2.0,
            'verbose_logging': True
        }
        
        test_mode_manager.set_mode(TestMode.UNIT, custom_config)
        
        print("⌨️  Ctrl+C を押して停止テストを実行してください")
        print("⏱️  60秒後に自動停止します")
        
        self._run_main_system()
    
    def _run_main_system(self):
        """テストメインシステムを実行"""
        try:
            # テスト専用メインシステムをインポートして実行
            from test_main import test_main
            print(
                "[TestRunner] Starting test main system in "
                f"{test_mode_manager.get_mode().value} mode..."
            )
            test_main([])  # 引数なしでtest_mainを呼び出す
            
        except KeyboardInterrupt:
            print("\n[TestRunner] KeyboardInterrupt received in test runner")
            
        except Exception as e:
            print(f"[TestRunner] Error running main system: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            runtime = time.time() - self.start_time
            print(f"\n[TestRunner] Test completed after {runtime:.1f} seconds")
            self._print_test_summary()
    
    def _print_test_summary(self):
        """テスト結果サマリーを表示"""
        status = test_mode_manager.get_status()
        
        print("\n" + "="*60)
        print("📊 Test Summary")
        print("="*60)
        print(f"Mode: {status['mode']}")
        print(f"Runtime: {status['runtime_minutes']:.1f} minutes")
        print(f"Components: {', '.join(status['registered_components'])}")
        print(f"Config: {status['config']}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="AI VTuber System Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        dest='mode', required=True, help='Test mode to run'
    )

    # Unit Test
    parser_unit = subparsers.add_parser(
        'unit', help='Run unit test mode'
    )
    parser_unit.add_argument(
        '--duration', type=int, help='Test duration in minutes'
    )

    # Integration Test
    parser_integration = subparsers.add_parser(
        'integration', help='Run integration test mode'
    )
    parser_integration.add_argument(
        '--duration', type=int, help='Test duration in minutes'
    )

    # Demo Mode
    parser_demo = subparsers.add_parser('demo', help='Run demo mode')
    parser_demo.add_argument(
        '--duration', type=int, help='Test duration in minutes'
    )

    # Debug Mode
    subparsers.add_parser('debug', help='Run debug mode')

    # Keyboard Interrupt Test
    subparsers.add_parser(
        'keyboard-test', help='Run keyboard interrupt test'
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    duration = getattr(args, 'duration', None)

    if args.mode == 'unit':
        runner.run_unit_test(duration)
    elif args.mode == 'integration':
        runner.run_integration_test(duration)
    elif args.mode == 'demo':
        runner.run_demo_mode(duration)
    elif args.mode == 'debug':
        runner.run_debug_mode()
    elif args.mode == 'keyboard-test':
        runner.run_keyboard_interrupt_test()


if __name__ == "__main__":
    main()