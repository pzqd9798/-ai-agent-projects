"""可观测性 — 结构化日志 + 性能指标."""

import time
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

from app.config import config


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    context: dict = field(default_factory=dict)


class ObservabilityManager:
    """结构化日志管理器 + 内存指标."""

    def __init__(self):
        self.logs_dir = config.logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # 内存中的指标
        self._metrics: dict[str, list] = defaultdict(list)
        self._counters: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # 结构化日志
    # ------------------------------------------------------------------

    def log(self, level: str, message: str, **context):
        """写入结构化日志."""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.upper(),
            message=message,
            context=context,
        )

        # 控制台输出
        ctx_str = " ".join(f"{k}={v}" for k, v in context.items())
        print(f"[{entry.timestamp}] {entry.level:5s} {message} {ctx_str}")

        # 写文件 (JSONL)
        log_file = self.logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": entry.timestamp,
                "level": entry.level,
                "message": entry.message,
                **entry.context,
            }, ensure_ascii=False) + "\n")

    def info(self, message: str, **context):
        self.log("INFO", message, **context)

    def warn(self, message: str, **context):
        self.log("WARN", message, **context)

    def error(self, message: str, **context):
        self.log("ERROR", message, **context)

    # ------------------------------------------------------------------
    # 指标收集
    # ------------------------------------------------------------------

    def record_phase_execution(self, project_id: str, phase: str,
                               role: str, duration_ms: float, tokens: int,
                               success: bool):
        """记录阶段执行指标."""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "phase": phase,
            "role": role,
            "duration_ms": round(duration_ms, 1),
            "tokens": tokens,
            "success": success,
        }
        self._metrics["phase_executions"].append(metric)
        self._counters[f"phases_{'success' if success else 'failed'}"] += 1
        self._counters["total_tokens"] += tokens

        self.info(
            "phase_executed",
            project_id=project_id[:8],
            phase=phase,
            role=role,
            duration_ms=round(duration_ms, 1),
            tokens=tokens,
            success=success,
        )

    def record_tool_call(self, agent: str, tool: str, duration_ms: float, ok: bool):
        """记录工具调用指标."""
        self._counters[f"tool_{tool}"] += 1

    def record_api_request(self, path: str, method: str, status_code: int,
                           duration_ms: float):
        """记录 API 请求指标."""
        self._counters[f"api_{method}_{path}"] += 1
        self._metrics["api_requests"].append({
            "timestamp": datetime.now().isoformat(),
            "path": path,
            "method": method,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 1),
        })

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_metrics_summary(self) -> dict:
        """获取指标摘要."""
        return {
            "counters": dict(self._counters),
            "total_phase_executions": len(self._metrics["phase_executions"]),
            "total_api_requests": len(self._metrics["api_requests"]),
            "recent_executions": self._metrics["phase_executions"][-10:],
        }

    def get_recent_logs(self, n: int = 50) -> list[dict]:
        """获取最近的日志."""
        log_file = self.logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        if not log_file.exists():
            return []
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        recent = lines[-n:]
        return [json.loads(line) for line in recent if line.strip()]


# 全局单例
_observability: ObservabilityManager | None = None


def get_observability() -> ObservabilityManager:
    global _observability
    if _observability is None:
        _observability = ObservabilityManager()
    return _observability
