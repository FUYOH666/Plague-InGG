"""Metrics monitoring module for system performance tracking."""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent

class MetricsMonitor:
    """Monitors system metrics and performance indicators."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "latency": [],
            "errors": [],
            "token_usage": [],
            "tool_calls": [],
            "evolution_events": []
        }
        self.start_time = datetime.now()
        self.metrics_file = PROJECT_ROOT / "data" / "memory" / "metrics-log.json"
        
    def record_latency(self, operation: str, duration_ms: float) -> None:
        """Record latency for a specific operation."""
        self.metrics["latency"].append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "duration_ms": duration_ms
        })
        
    def record_error(self, operation: str, error_type: str, message: str) -> None:
        """Record an error event."""
        self.metrics["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "error_type": error_type,
            "message": message
        })
        
    def record_token_usage(self, model: str, tokens_used: int, tokens_limit: int) -> None:
        """Record token usage for an LLM model."""
        self.metrics["token_usage"].append({
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "tokens_used": tokens_used,
            "tokens_limit": tokens_limit,
            "usage_percentage": (tokens_used / tokens_limit) * 100
        })
        
    def record_tool_call(self, tool_name: str, success: bool, duration_ms: float) -> None:
        """Record a tool call event."""
        self.metrics["tool_calls"].append({
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms
        })
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Generate comprehensive metrics summary."""
        total_ops = len(self.metrics["latency"])
        avg_latency = (
            sum(m["duration_ms"] for m in self.metrics["latency"]) / total_ops
            if total_ops > 0 else 0
        )
        error_rate = (
            sum(1 for e in self.metrics["errors"] if e["error_type"] == "critical") /
            total_ops * 100
        )
        token_health = (
            sum(m["usage_percentage"] for m in self.metrics["token_usage"]) /
            len(self.metrics["token_usage"])
            if self.metrics["token_usage"] else 0
        )
        
        return {
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "total_operations": total_ops,
            "average_latency_ms": round(avg_latency, 2),
            "error_rate_percent": round(error_rate, 2),
            "token_health_score": round(token_health, 2),
            "last_updated": datetime.now().isoformat()
        }
    
    def save_metrics(self) -> None:
        """Save current metrics to JSON file."""
        with open(self.metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
    
    def load_metrics(self) -> None:
        """Load metrics from JSON file."""
        if self.metrics_file.exists():
            with open(self.metrics_file, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []
        summary = self.get_metrics_summary()
        
        if summary["average_latency_ms"] > 500:
            alerts.append({
                "type": "warning",
                "message": f"High latency detected: {summary['average_latency_ms']}ms"
            })
        
        if summary["error_rate_percent"] > 5:
            alerts.append({
                "type": "critical",
                "message": f"Elevated error rate: {summary['error_rate_percent']}%"
            })
        
        if summary["token_health_score"] > 80:
            alerts.append({
                "type": "info",
                "message": f"Excellent token health: {summary['token_health_score']}%"
            })
        
        return alerts