"""文档摄取管道 — 加载、分块、元数据提取."""

import re
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Chunk:
    """文档的一个片段."""
    id: str
    text: str
    source: str           # 来源文件路径
    chunk_index: int      # 在文档中的序号
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None  # 由 embedder 填充


# ---------------------------------------------------------------------------
# 文本分块器
# ---------------------------------------------------------------------------

class TextChunker:
    """基于段落和固定大小的自适应分块.

    优先在段落边界切分，段落过长时按句子切，句子仍过长则硬截断.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, source: str) -> list[Chunk]:
        paragraphs = self._split_paragraphs(text)
        chunks = self._merge_paragraphs(paragraphs, source)
        return chunks

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        # 双换行分割段落
        parts = re.split(r"\n\s*\n", text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

    def _merge_paragraphs(self, paragraphs: list[str], source: str) -> list[Chunk]:
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) <= self.chunk_size:
                current += ("\n\n" + para) if current else para
            else:
                if current:
                    chunks.extend(self._finalize_chunk(current, source, len(chunks)))
                current = para
        if current:
            chunks.extend(self._finalize_chunk(current, source, len(chunks)))
        return chunks

    def _finalize_chunk(self, text: str, source: str, start_index: int) -> list[Chunk]:
        if len(text) <= self.chunk_size:
            return [Chunk(
                id=uuid.uuid4().hex[:12],
                text=text,
                source=source,
                chunk_index=start_index,
            )]
        # 超长: 按句子切
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        result = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= self.chunk_size:
                current += sent
            else:
                if current:
                    result.append(Chunk(
                        id=uuid.uuid4().hex[:12],
                        text=current.strip(),
                        source=source,
                        chunk_index=start_index + len(result),
                    ))
                # 如果单句超长，硬截断
                if len(sent) > self.chunk_size:
                    for i in range(0, len(sent), self.chunk_size - self.chunk_overlap):
                        result.append(Chunk(
                            id=uuid.uuid4().hex[:12],
                            text=sent[i:i + self.chunk_size],
                            source=source,
                            chunk_index=start_index + len(result),
                        ))
                else:
                    current = sent
        if current.strip():
            result.append(Chunk(
                id=uuid.uuid4().hex[:12],
                text=current.strip(),
                source=source,
                chunk_index=start_index + len(result),
            ))
        return result


# ---------------------------------------------------------------------------
# 文档加载器
# ---------------------------------------------------------------------------

class DocumentLoader:
    """加载各种格式的文档为纯文本."""

    @staticmethod
    def load(file_path: str | Path) -> tuple[str, dict]:
        """加载文档，返回 (纯文本, 元数据).

        支持的格式: .txt, .md, .pdf
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8"), {"format": "txt"}

        elif suffix == ".md":
            text = path.read_text(encoding="utf-8")
            title = ""
            # 提取一级标题作为文档标题
            m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if m:
                title = m.group(1)
            return text, {"format": "markdown", "title": title}

        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
                text = "\n\n".join(pages)
                meta = reader.metadata or {}
                return text, {
                    "format": "pdf",
                    "title": str(meta.get("title", "")),
                    "pages": len(reader.pages),
                    "author": str(meta.get("author", "")),
                }
            except ImportError:
                raise ImportError("请安装 pypdf: pip install pypdf")

        else:
            raise ValueError(f"不支持的格式: {suffix}")


# ---------------------------------------------------------------------------
# 管道
# ---------------------------------------------------------------------------

def ingest_file(file_path: str | Path,
                chunk_size: int = 800,
                chunk_overlap: int = 100) -> list[Chunk]:
    """单文件摄取管道: 加载 → 分块."""
    loader = DocumentLoader()
    chunker = TextChunker(chunk_size, chunk_overlap)

    text, meta = loader.load(file_path)
    chunks = chunker.chunk(text, str(Path(file_path).name))

    # 将文档元数据写入每个 chunk
    for c in chunks:
        c.metadata = {**meta, "source_file": str(file_path)}

    return chunks


def ingest_directory(dir_path: str | Path, glob_pattern: str = "*.{txt,md,pdf}",
                     **kwargs) -> list[Chunk]:
    """批量摄取目录中的文档."""
    all_chunks = []
    base = Path(dir_path)
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".txt", ".md", ".pdf"):
            try:
                chunks = ingest_file(path, **kwargs)
                all_chunks.extend(chunks)
                print(f"  [摄取] {path.name}: {len(chunks)} 个chunk")
            except Exception as exc:
                print(f"  [跳过] {path.name}: {exc}")
    return all_chunks
