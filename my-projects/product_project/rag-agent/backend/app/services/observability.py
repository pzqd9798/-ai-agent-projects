"""可观测性 — 结构化日志 + 指标采集 + 健康检查."""

import time
import os
import logging
import json
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# 结构化日志 (轻量级, 不依赖 structlog 动态配置)
# ---------------------------------------------------------------------------

class StructuredLogger:
    """结构化 JSON 日志 — 同时输出到控制台和文件."""

    def __init__(self, name: str = "rag-agent"):
        self.name = name
        self._start_time = time.time()

        # 确保日志目录存在
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Python 标准日志
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            self._logger.setLevel(
                logging.DEBUG if os.getenv("DEBUG", "").lower() == "true" else logging.INFO
            )
            # 控制台 handler
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self._logger.addHandler(ch)

            # 文件 handler
            fh = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                '{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            self._logger.addHandler(fh)

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(self._fmt(msg, **kwargs))

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(self._fmt(msg, **kwargs))

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(self._fmt(msg, **kwargs))

    def debug(self, msg: str, **kwargs) -> None:
        self._logger.debug(self._fmt(msg, **kwargs))

    @staticmethod
    def _fmt(msg: str, **kwargs) -> str:
        if kwargs:
            return json.dumps({"msg": msg, **kwargs}, ensure_ascii=False)
        return msg

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time


# ---------------------------------------------------------------------------
# 内存指标
# ---------------------------------------------------------------------------

class MetricsCollector:
    """简易 Prometheus 风格指标采集."""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, amount: int = 1) -> None:
        self._counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def get_counters(self) -> dict:
        return dict(self._counters)

    def get_gauges(self) -> dict:
        return dict(self._gauges)

    def get_summary(self) -> dict:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_logger: StructuredLogger | None = None
_metrics: MetricsCollector | None = None


def get_logger() -> StructuredLogger:
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger


def get_metrics() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
