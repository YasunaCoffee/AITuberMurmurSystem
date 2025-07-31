import time
import threading
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class MetricEvent:
    """メトリクスイベントを表すデータクラス"""
    timestamp: float
    component: str
    metric_type: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    v2システム用のメトリクス収集・管理クラス。
    パフォーマンス情報、エラー率、応答時間などを収集する。
    """
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.retention_seconds = retention_hours * 3600
        
        # メトリクスデータの保存
        self.events: deque = deque()  # 時系列イベント
        self.counters: Dict[str, int] = defaultdict(int)  # カウンター
        self.gauges: Dict[str, float] = {}  # ゲージ（最新値）
        self.histograms: Dict[str, List[float]] = defaultdict(list)  # 履歴データ
        
        # スレッドセーフ用のロック
        self.lock = threading.Lock()
        
        # 自動クリーンアップ用スレッド
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_running = True
        self.cleanup_thread.start()
        
        print("[MetricsCollector] Initialized with retention period:", retention_hours, "hours")

    def record_counter(self, component: str, metric_name: str, value: int = 1, **metadata):
        """カウンターメトリクスを記録"""
        with self.lock:
            key = f"{component}.{metric_name}"
            self.counters[key] += value
            
            event = MetricEvent(
                timestamp=time.time(),
                component=component,
                metric_type="counter",
                value=value,
                metadata={"metric_name": metric_name, **metadata}
            )
            self.events.append(event)

    def record_gauge(self, component: str, metric_name: str, value: float, **metadata):
        """ゲージメトリクスを記録"""
        with self.lock:
            key = f"{component}.{metric_name}"
            self.gauges[key] = value
            
            event = MetricEvent(
                timestamp=time.time(),
                component=component,
                metric_type="gauge",
                value=value,
                metadata={"metric_name": metric_name, **metadata}
            )
            self.events.append(event)

    def record_histogram(self, component: str, metric_name: str, value: float, **metadata):
        """ヒストグラムメトリクス（応答時間等）を記録"""
        with self.lock:
            key = f"{component}.{metric_name}"
            self.histograms[key].append(value)
            
            # 古いデータを削除（最大1000件まで保持）
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            
            event = MetricEvent(
                timestamp=time.time(),
                component=component,
                metric_type="histogram",
                value=value,
                metadata={"metric_name": metric_name, **metadata}
            )
            self.events.append(event)

    def record_duration(self, component: str, operation: str, duration: float, success: bool = True, **metadata):
        """操作の実行時間を記録"""
        self.record_histogram(component, f"{operation}_duration", duration, 
                            success=success, operation=operation, **metadata)
        
        # 成功/失敗カウンターも更新
        result = "success" if success else "error"
        self.record_counter(component, f"{operation}_{result}", 1, 
                          operation=operation, **metadata)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """メトリクスのサマリー情報を取得"""
        with self.lock:
            current_time = time.time()
            cutoff_time = current_time - 3600  # 過去1時間
            
            # 過去1時間のイベントを抽出
            recent_events = [e for e in self.events if e.timestamp >= cutoff_time]
            
            # 統計情報を計算
            summary = {
                "collection_time": datetime.now().isoformat(),
                "retention_hours": self.retention_hours,
                "total_events": len(self.events),
                "recent_events_1h": len(recent_events),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms_stats": self._calculate_histogram_stats()
            }
            
            return summary

    def _calculate_histogram_stats(self) -> Dict[str, Dict[str, float]]:
        """ヒストグラムデータの統計情報を計算"""
        stats = {}
        
        for key, values in self.histograms.items():
            if not values:
                continue
                
            values_sorted = sorted(values)
            count = len(values_sorted)
            
            stats[key] = {
                "count": count,
                "min": min(values_sorted),
                "max": max(values_sorted),
                "mean": sum(values_sorted) / count,
                "median": values_sorted[count // 2],
                "p95": values_sorted[int(count * 0.95)] if count > 0 else 0,
                "p99": values_sorted[int(count * 0.99)] if count > 0 else 0
            }
            
        return stats

    def get_component_metrics(self, component: str) -> Dict[str, Any]:
        """特定のコンポーネントのメトリクス情報を取得"""
        with self.lock:
            component_counters = {k: v for k, v in self.counters.items() if k.startswith(f"{component}.")}
            component_gauges = {k: v for k, v in self.gauges.items() if k.startswith(f"{component}.")}
            component_histograms = {k: v for k, v in self.histograms.items() if k.startswith(f"{component}.")}
            
            return {
                "component": component,
                "counters": component_counters,
                "gauges": component_gauges,
                "histograms": {k: self._calculate_histogram_stats()[k] 
                             for k in component_histograms.keys() 
                             if k in self._calculate_histogram_stats()}
            }

    def get_system_health(self) -> Dict[str, Any]:
        """システム全体の健全性情報を取得"""
        with self.lock:
            current_time = time.time()
            last_hour = current_time - 3600
            
            # エラー率の計算
            error_events = [e for e in self.events 
                          if e.timestamp >= last_hour and "error" in e.metadata.get("metric_name", "")]
            total_events = [e for e in self.events if e.timestamp >= last_hour]
            
            error_rate = len(error_events) / len(total_events) if total_events else 0
            
            # 平均応答時間の計算
            duration_events = [e for e in self.events 
                             if e.timestamp >= last_hour and "duration" in e.metadata.get("metric_name", "")]
            avg_response_time = (sum(e.value for e in duration_events) / len(duration_events)) if duration_events else 0
            
            return {
                "timestamp": datetime.now().isoformat(),
                "error_rate": error_rate,
                "error_count_1h": len(error_events),
                "total_events_1h": len(total_events),
                "avg_response_time_1h": avg_response_time,
                "health_status": "healthy" if error_rate < 0.05 else "degraded" if error_rate < 0.20 else "unhealthy"
            }

    def _cleanup_worker(self):
        """古いメトリクスデータを定期的にクリーンアップ"""
        while self.cleanup_running:
            try:
                with self.lock:
                    current_time = time.time()
                    cutoff_time = current_time - self.retention_seconds
                    
                    # 古いイベントを削除
                    while self.events and self.events[0].timestamp < cutoff_time:
                        self.events.popleft()
                
                # 5分ごとにクリーンアップ
                time.sleep(300)
                
            except Exception as e:
                print(f"[MetricsCollector] Cleanup error: {e}")
                time.sleep(60)  # エラー時は1分待機

    def shutdown(self):
        """メトリクス収集を停止"""
        self.cleanup_running = False
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2.0)
        print("[MetricsCollector] Shutdown completed")


# === グローバルメトリクスコレクター ===

_global_metrics: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """グローバルメトリクスコレクターを取得（シングルトンパターン）"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics

def record_performance(component: str, operation: str, duration: float, success: bool = True, **metadata):
    """パフォーマンスメトリクスを記録するヘルパー関数"""
    collector = get_metrics_collector()
    collector.record_duration(component, operation, duration, success, **metadata)

def record_event(component: str, event_name: str, count: int = 1, **metadata):
    """イベントカウンターを記録するヘルパー関数"""
    collector = get_metrics_collector()
    collector.record_counter(component, event_name, count, **metadata)

def record_value(component: str, metric_name: str, value: float, **metadata):
    """ゲージ値を記録するヘルパー関数"""
    collector = get_metrics_collector()
    collector.record_gauge(component, metric_name, value, **metadata)


# === パフォーマンス測定デコレータ ===

def measure_performance(component: str, operation: Optional[str] = None):
    """関数の実行時間を自動測定するデコレータ"""
    def decorator(func):
        op_name = operation or func.__name__
        
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                record_performance(component, op_name, duration, success)
                
        return wrapper
    return decorator