#!/usr/bin/env python3
"""
v2システムのメトリクス機能テスト用スクリプト
"""

import time
import json
from v2.core.metrics import get_metrics_collector, record_performance, record_event, record_value, measure_performance


@measure_performance("TestComponent", "test_operation")
def test_operation_with_decorator(duration: float):
    """デコレータによる自動パフォーマンス測定のテスト"""
    time.sleep(duration)
    return f"Operation completed in {duration}s"


def test_metrics_system():
    """メトリクスシステムの総合テスト"""
    print("=== v2 Metrics System Test ===")
    
    collector = get_metrics_collector()
    
    # 1. 各種メトリクスの記録テスト
    print("📊 Recording various metrics...")
    
    # カウンター
    record_event("AudioManager", "speech_requests", 5)
    record_event("CommentHandler", "comment_responses", 3)
    record_event("MainController", "state_changes", 8)
    
    # パフォーマンス（応答時間）
    record_performance("AudioManager", "speech_synthesis", 2.5, True, sentences=2)
    record_performance("CommentHandler", "llm_request", 3.2, True, model="gpt-4.1")
    record_performance("CommentHandler", "llm_request", 5.1, False, model="gpt-4.1", error="timeout")
    
    # ゲージ値
    record_value("StateManager", "pending_comments", 12)
    record_value("EventQueue", "queue_size", 5)
    record_value("System", "memory_usage_mb", 256.7)
    
    # 2. デコレータによる自動測定テスト
    print("⚡ Testing performance measurement decorator...")
    result = test_operation_with_decorator(0.1)
    print(f"Result: {result}")
    
    # 複数の操作をシミュレート
    for i in range(3):
        test_operation_with_decorator(0.05 + i * 0.02)
    
    # 3. メトリクスサマリーの表示
    print("\n📈 Metrics Summary:")
    summary = collector.get_metrics_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 4. 特定コンポーネントのメトリクス
    print("\n🎯 Component-specific metrics (AudioManager):")
    audio_metrics = collector.get_component_metrics("AudioManager")
    print(json.dumps(audio_metrics, indent=2, ensure_ascii=False))
    
    # 5. システム健全性
    print("\n🏥 System Health:")
    health = collector.get_system_health()
    print(json.dumps(health, indent=2, ensure_ascii=False))
    
    # 6. 追加データで統計精度を向上
    print("\n📊 Adding more performance data for better statistics...")
    for i in range(10):
        duration = 1.0 + (i * 0.2)  # 1.0〜3.0秒の範囲
        success = i < 8  # 80%成功率
        record_performance("TestComponent", "bulk_operation", duration, success)
    
    # 最終統計の表示
    print("\n📊 Final Statistics:")
    final_stats = collector.get_component_metrics("TestComponent")
    print(json.dumps(final_stats, indent=2, ensure_ascii=False))
    
    print("\n✅ Metrics system test completed successfully!")


if __name__ == "__main__":
    test_metrics_system()