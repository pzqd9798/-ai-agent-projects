"""文档分块器 — 自适应分块，支持段落/句子/固定窗口."""

import re
import uuid
from dataclasses import dataclass, field

from app.config import retrieval


@dataclass
class ChunkData:
    """分块数据结构 (不依赖 ORM)."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    source: str = ""           # 来源文件名
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None


class AdaptiveChunker:
    """自适应文本分块器.

    1. 优先在段落边界切分 (双换行)
    2. 段落过长按句子切
    3. 句子仍超长则硬截断
    """

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        self.chunk_size = chunk_size or retrieval.chunk_size
        self.chunk_overlap = chunk_overlap or retrieval.chunk_overlap

    def chunk(self, text: str, source: str = "") -> list[ChunkData]:
        paragraphs = self._split_paragraphs(text)
        chunks = self._merge_paragraphs(paragraphs, source)
        return chunks

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        parts = re.split(r"\n\s*\n", text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

    def _merge_paragraphs(self, paragraphs: list[str], source: str) -> list[ChunkData]:
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) <= self.chunk_size:
                current += ("\n\n" + para) if current else para
            else:
                if current:
                    chunks.extend(self._finalize(current, source, len(chunks)))
                current = para
        if current:
            chunks.extend(self._finalize(current, source, len(chunks)))
        return chunks

    def _finalize(self, text: str, source: str, start_idx: int) -> list[ChunkData]:
        if len(text) <= self.chunk_size:
            return [ChunkData(text=text, source=source, chunk_index=start_idx)]

        # 按句子切
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        result = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= self.chunk_size:
                current += sent
            else:
                if current:
                    result.append(ChunkData(
                        text=current.strip(), source=source,
                        chunk_index=start_idx + len(result),
                    ))
                if len(sent) > self.chunk_size:
                    # 硬截断
                    step = self.chunk_size - self.chunk_overlap
                    for i in range(0, len(sent), step):
                        result.append(ChunkData(
                            text=sent[i:i + self.chunk_size], source=source,
                            chunk_index=start_idx + len(result),
                        ))
                else:
                    current = sent
        if current.strip():
            result.append(ChunkData(
                text=current.strip(), source=source,
                chunk_index=start_idx + len(result),
            ))
        return result
