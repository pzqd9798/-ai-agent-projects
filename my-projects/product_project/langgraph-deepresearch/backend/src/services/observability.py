"""Structured logging and metrics for the deep research platform."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import defaultdict
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------


class JsonLogger:
    """JSON-structured logger wrapping Python's logging."""

    def __init__(self, name: str = "deepresearch", level: int = logging.INFO) -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
                    '"msg":"%(message)s"}',
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            self.logger.addHandler(handler)

    def _emit(self, level: int, event: str, **kwargs: Any) -> None:
        payload = {"event": event}
        payload.update(kwargs)
        self.logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self.logger.exception(json.dumps({"event": event, **kwargs}, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# Simple metrics collector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """In-memory metrics with Prometheus-style exposition."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._timers: dict[str, float] = {}

    def incr(self, name: str, delta: int = 1) -> None:
        self._counters[name] += delta

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def timer_start(self, name: str) -> None:
        self._timers[name] = time.time()

    def timer_end(self, name: str) -> float:
        start = self._timers.pop(name, time.time())
        elapsed = (time.time() - start) * 1000
        self.observe(f"{name}_ms", elapsed)
        return elapsed

    def get_counters(self) -> dict[str, int]:
        return dict(self._counters)

    def get_gauges(self) -> dict[str, float]:
        return dict(self._gauges)

    def get_snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_avgs": {
                k: round(sum(v) / len(v), 2) if v else 0
                for k, v in self._histograms.items()
            },
        }

    def prometheus_text(self) -> str:
        """Export in Prometheus text format."""
        lines = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)


# Singletons
_logger_instance: Optional[JsonLogger] = None
_metrics_instance: Optional[MetricsCollector] = None


def get_logger() -> JsonLogger:
    global _logger_instance
    if _logger_instance is None:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        _logger_instance = JsonLogger(level=level)
    return _logger_instance


def get_metrics() -> MetricsCollector:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance
