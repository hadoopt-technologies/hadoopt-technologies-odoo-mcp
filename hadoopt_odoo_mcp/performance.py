"""
Performance monitoring utilities for Odoo MCP
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Track performance metrics for MCP operations"""
    
    total_calls: int = 0
    total_time: float = 0
    avg_time: float = 0
    min_time: float = float('inf')
    max_time: float = 0
    method_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def record_call(self, method_name: str, execution_time: float) -> None:
        """Record a method call and its execution time"""
        self.total_calls += 1
        self.total_time += execution_time
        self.avg_time = self.total_time / self.total_calls
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        
        # Record method-specific stats
        if method_name not in self.method_stats:
            self.method_stats[method_name] = {
                'calls': 0,
                'total_time': 0,
                'avg_time': 0,
                'min_time': float('inf'),
                'max_time': 0
            }
        
        stats = self.method_stats[method_name]
        stats['calls'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['calls']
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['max_time'] = max(stats['max_time'], execution_time)
    
    def get_slow_methods(self, threshold_ms: float = 200) -> List[Dict[str, Any]]:
        """Get methods that take longer than threshold on average"""
        slow_methods = []
        for method, stats in self.method_stats.items():
            if stats['avg_time'] * 1000 > threshold_ms:
                slow_methods.append({
                    'method': method,
                    'avg_time_ms': stats['avg_time'] * 1000,
                    'calls': stats['calls']
                })
        
        # Sort by average time (slowest first)
        return sorted(slow_methods, key=lambda x: x['avg_time_ms'], reverse=True)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics"""
        most_called = sorted(
            [{'method': m, 'calls': s['calls']} for m, s in self.method_stats.items()],
            key=lambda x: x['calls'], 
            reverse=True
        )[:5]
        
        slowest = self.get_slow_methods()[:5]
        
        return {
            'total_calls': self.total_calls,
            'total_time_s': self.total_time,
            'avg_time_ms': self.avg_time * 1000,
            'min_time_ms': self.min_time * 1000,
            'max_time_ms': self.max_time * 1000,
            'most_called': most_called,
            'slowest_methods': slowest
        }


# Global performance tracker
performance_metrics = PerformanceMetrics()


def measure_performance(func: Callable) -> Callable:
    """Decorator to measure performance of a function"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Record performance metrics
        method_name = func.__name__
        performance_metrics.record_call(method_name, execution_time)
        
        # Log slow operations
        if execution_time > 1.0:  # Log operations taking more than 1 second
            logger.warning(f"Slow operation: {method_name} took {execution_time:.2f}s")
        
        return result
    return wrapper


def get_performance_metrics() -> Dict[str, Any]:
    """Get the current performance metrics"""
    return performance_metrics.get_summary()


def reset_performance_metrics() -> None:
    """Reset the performance metrics"""
    global performance_metrics
    performance_metrics = PerformanceMetrics()
