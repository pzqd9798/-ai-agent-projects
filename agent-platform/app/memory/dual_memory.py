#!/usr/bin/env python3
"""双记忆系统 — 短期 (Redis) + 长期 (向量检索).

短期记忆: Redis 存储最近 N 条会话消息, 支持 TTL 过期
长期记忆: 基于 Redis 的向量相似度检索 (需要 redis 和 embedding)
"""

import json
import time
from typing import Any


# ---------------------------------------------------------------------------
# 短期记忆 (Short-Term Memory)
# ---------------------------------------------------------------------------

class ShortTermMemory:
    """基于 Redis 的短期对话记忆.

    存储结构: 每个会话一个 LIST, 每条消息 JSON 序列化.
    支持 TTL 自动过期和最大消息数截断.
    """

    def __init__(self, redis_client, max_messages: int = 50, ttl: int = 86400):
        self.redis = redis_client
        self.max_messages = max_messages
        self.ttl = ttl

    def _key(self, session_id: str) -> str:
        return f"stm:{session_id}"

    def add(self, session_id: str, role: str, content: str) -> None:
        entry = json.dumps({
            "role": role, "content": content, "ts": time.time(),
        }, ensure_ascii=False)
        key = self._key(session_id)
        self.redis.rpush(key, entry)
        self.redis.expire(key, self.ttl)

        # 截断
        count = self.redis.llen(key)
        if count > self.max_messages:
            self.redis.ltrim(key, count - self.max_messages, -1)

    def get_recent(self, session_id: str, limit: int = 20) -> list[dict]:
        key = self._key(session_id)
        items = self.redis.lrange(key, -limit, -1)
        return [json.loads(item) for item in items]

    def clear(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))


# ---------------------------------------------------------------------------
# 长期记忆 (Long-Term Memory)
# ---------------------------------------------------------------------------

class LongTermMemory:
    """长期向量记忆 — 基于嵌入相似度的语义检索.

    简化实现: 使用内存 dict 存储, 余弦相似度检索.
    生产环境应替换为 RedisVL 或向量数据库.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}  # memory_id -> {content, metadata, embedding}
        self._embedding_fn = None  # 允许外部注入 embedding 函数

    def set_embedding_fn(self, fn) -> None:
        """注入 embedding 函数. fn(text) -> list[float]."""
        self._embedding_fn = fn

    def store(self, content: str, metadata: dict | None = None,
              memory_id: str | None = None) -> str:
        """存储一条长期记忆."""
        import uuid
        mid = memory_id or uuid.uuid4().hex[:12]
        self._store[mid] = {
            "content": content,
            "metadata": metadata or {},
            "ts": time.time(),
            "embedding": self._embedding_fn(content) if self._embedding_fn else None,
        }
        return mid

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """搜索最相似的记忆.

        如果有 embedding_fn 则用向量相似度, 否则回退到关键词匹配.
        """
        if self._embedding_fn:
            return self._vector_search(query, limit)
        return self._keyword_search(query, limit)

    def _vector_search(self, query: str, limit: int) -> list[dict]:
        query_vec = self._embedding_fn(query)
        scored = []
        for mid, mem in self._store.items():
            if mem["embedding"]:
                score = self._cosine_sim(query_vec, mem["embedding"])
                scored.append((score, mid, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": mid, "content": m["content"], "metadata": m["metadata"],
                 "score": s} for s, mid, m in scored[:limit]]

    def _keyword_search(self, query: str, limit: int) -> list[dict]:
        query_words = set(query.lower().split())
        scored = []
        for mid, mem in self._store.items():
            content_lower = mem["content"].lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append((score, mid, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": mid, "content": m["content"], "metadata": m["metadata"],
                 "score": s} for s, mid, m in scored[:limit]]

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def delete(self, memory_id: str) -> None:
        self._store.pop(memory_id, None)

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

def create_memory_system():
    """根据配置创建记忆系统."""
    try:
        import redis
        r = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)
        r.ping()
        stm = ShortTermMemory(r)
        print("[Memory] Redis 短期记忆已连接")
    except Exception:
        print("[Memory] Redis 不可用, 短期记忆降级为内存存储")
        stm = _InMemoryShortTerm()

    ltm = LongTermMemory()
    print("[Memory] 长期记忆已就绪 (内存模式)")

    return stm, ltm


class _InMemoryShortTerm:
    """内存降级实现 (Redis 不可用时)."""
    def __init__(self, max_messages: int = 50):
        self._store: dict[str, list] = {}
        self.max_messages = max_messages

    def add(self, session_id: str, role: str, content: str) -> None:
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append({
            "role": role, "content": content, "ts": time.time(),
        })
        if len(self._store[session_id]) > self.max_messages:
            self._store[session_id] = self._store[session_id][-self.max_messages:]

    def get_recent(self, session_id: str, limit: int = 20) -> list[dict]:
        items = self._store.get(session_id, [])
        return items[-limit:]

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
