"""Bounded, local retrieval over documents attached in a chat."""

from array import array
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import math
import re
import threading
import time

_PAGE_MARKER = re.compile(r"(?m)^\[Page\s+(\d+)\]\s*$")
_TOKEN = re.compile(r"[^\W_]{2,}", re.UNICODE)
_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have how i in is it of on or that "
    "the this to was what when where which who why with".split()
)
_CHUNK_CHARS = 1200
_TARGET_CHUNK_CHARS = 500
_CHUNK_OVERLAP = 160
_MAX_CONTEXT_CHARS = 12_000
_MAX_CHUNKS = 8
MAX_CHAT_CHARS = 12 * 1024 * 1024
_MAX_CHAT_COUNT = 32
_MAX_TOTAL_CHARS = 64 * 1024 * 1024
_MAX_DOCUMENTS_PER_CHAT = 20
_CHAT_TTL_SECONDS = 2 * 60 * 60
MAX_EMBEDDING_CHUNKS = 2048


@dataclass(frozen=True)
class DocumentChunk:
    name: str
    page: int | None
    text: str
    tokens: tuple[str, ...]
    embedding: bytes | None = None


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token for token in (item.casefold() for item in _TOKEN.findall(text))
        if token not in _STOP_WORDS
    )


def _split_text(text: str, limit: int = _CHUNK_CHARS) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n{2,}", text.strip())
        if sentence.strip()
    ]
    parts = []
    pending = ""
    for sentence in sentences or [text.strip()]:
        if len(sentence) > limit:
            if pending:
                parts.append(pending)
                pending = ""
            start = 0
            while start < len(sentence):
                end = min(len(sentence), start + limit)
                if end < len(sentence):
                    boundary = sentence.rfind(" ", start + limit // 2, end)
                    if boundary > start:
                        end = boundary
                part = sentence[start:end].strip()
                if part:
                    parts.append(part)
                if end >= len(sentence):
                    break
                start = max(start + 1, end - _CHUNK_OVERLAP)
        elif not pending:
            pending = sentence
        elif len(pending) + len(sentence) + 1 <= _TARGET_CHUNK_CHARS:
            pending = f"{pending} {sentence}"
        else:
            parts.append(pending)
            pending = sentence
    if pending:
        parts.append(pending)
    return parts


def chunk_document(name: str, text: str) -> tuple[DocumentChunk, ...]:
    """Split text while retaining PDF page metadata for citation."""
    if not isinstance(name, str) or not isinstance(text, str):
        raise TypeError("document names and contents must be text")
    markers = list(_PAGE_MARKER.finditer(text))
    sections = []
    if markers:
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            sections.append((int(marker.group(1)), text[marker.end():end].strip()))
    else:
        sections.append((None, text.strip()))

    chunks = []
    for page, section in sections:
        for part in _split_text(section):
            chunks.append(DocumentChunk(name, page, part, _tokens(part)))
    return tuple(chunks)


def retrieve(
    query: str,
    chunks: tuple[DocumentChunk, ...] | list[DocumentChunk],
    limit: int = _MAX_CHUNKS,
    max_chars: int = _MAX_CONTEXT_CHARS,
    query_embedding: tuple[float, ...] | list[float] | None = None,
) -> list[DocumentChunk]:
    """Rank matching excerpts with embeddings when available, otherwise BM25."""
    if not chunks or limit < 1 or max_chars < 1:
        return []
    ranked = []
    if query_embedding:
        query_vector = array("f", query_embedding)
        query_norm = math.sqrt(math.fsum(value * value for value in query_vector))
        semantic_scores = []
        if query_norm:
            for index, chunk in enumerate(chunks):
                if not chunk.embedding:
                    continue
                vector = array("f")
                vector.frombytes(chunk.embedding)
                if len(vector) != len(query_vector):
                    continue
                vector_norm = math.sqrt(math.fsum(value * value for value in vector))
                if vector_norm:
                    score = math.fsum(
                        left * right for left, right in zip(query_vector, vector)
                    ) / (query_norm * vector_norm)
                    if score > 0:
                        semantic_scores.append((score, index, chunk))
        if semantic_scores:
            ranked = [
                (index, chunk)
                for _, index, chunk in sorted(semantic_scores, reverse=True)
            ]
            without_embeddings = [
                chunk for chunk in chunks if not chunk.embedding
            ]
            if without_embeddings:
                ranked.extend(
                    enumerate(retrieve(query, without_embeddings, limit=len(without_embeddings)))
                )

    terms = set(_tokens(query))
    if ranked:
        pass
    elif not terms:
        ranked = list(enumerate(chunks))
    else:
        document_frequency = {}
        lengths = []
        token_counts = []
        for chunk in chunks:
            counts = {}
            for token in chunk.tokens:
                counts[token] = counts.get(token, 0) + 1
            token_counts.append(counts)
            lengths.append(len(chunk.tokens))
            for term in terms.intersection(counts):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        average_length = sum(lengths) / max(1, len(lengths))
        scores = []
        for index, counts in enumerate(token_counts):
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                frequency_in_documents = document_frequency.get(term, 0)
                inverse_frequency = math.log(
                    1 + (len(chunks) - frequency_in_documents + 0.5)
                    / (frequency_in_documents + 0.5)
                )
                length_factor = lengths[index] / max(1.0, average_length)
                score += inverse_frequency * (
                    frequency * 2.2
                    / (frequency + 1.2 * (0.25 + 0.75 * length_factor))
                )
            if score > 0:
                scores.append((score, index, chunks[index]))
        ranked = (
            [(index, chunk) for _, index, chunk in sorted(scores, reverse=True)]
            if scores else list(enumerate(chunks))
        )

    selected = []
    total_chars = 0
    for _, chunk in ranked:
        if len(selected) >= limit:
            break
        if selected and total_chars + len(chunk.text) > max_chars:
            continue
        if len(chunk.text) > max_chars and not selected:
            chunk = DocumentChunk(
                chunk.name, chunk.page, chunk.text[:max_chars], chunk.tokens
            )
        selected.append(chunk)
        total_chars += len(chunk.text)
    return selected


def format_context(chunks: list[DocumentChunk]) -> str:
    """Format retrieved excerpts with stable document and page citations."""
    return "\n\n".join(
        f"--- Source: {chunk.name}"
        + (f", Page {chunk.page}" if chunk.page is not None else "")
        + f" ---\n{chunk.text}"
        for chunk in chunks
    )


class LocalDocumentIndex:
    """An in-memory, size-bounded, expiring index that never writes uploads to disk."""

    def __init__(self):
        self._chats = OrderedDict()
        self._lock = threading.Lock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            chat_id for chat_id, chat in self._chats.items()
            if now - chat["updated"] > _CHAT_TTL_SECONDS
        ]
        for chat_id in expired:
            del self._chats[chat_id]

    def _total_chars(self) -> int:
        return sum(chat["chars"] for chat in self._chats.values())

    def add(
        self,
        chat_id: str,
        name: str,
        text: str,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        if not chat_id or not isinstance(text, str):
            raise ValueError("a chat id and document text are required")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks = chunk_document(name, text)
        if embeddings is not None:
            if len(embeddings) != len(chunks):
                raise ValueError("embedding count must match the document chunk count")
            embedded_chunks = []
            for chunk, values in zip(chunks, embeddings):
                vector = array("f", values)
                if not vector or not all(math.isfinite(value) for value in vector):
                    raise ValueError("document embeddings must contain finite values")
                embedded_chunks.append(
                    DocumentChunk(
                        chunk.name,
                        chunk.page,
                        chunk.text,
                        chunk.tokens,
                        vector.tobytes(),
                    )
                )
            chunks = tuple(embedded_chunks)
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            chat = self._chats.pop(chat_id, {"updated": now, "documents": OrderedDict(), "chars": 0})
            previous = chat["documents"].pop(digest, None)
            if previous:
                chat["chars"] -= previous[1]
            document_chars = len(text)
            chat["documents"][digest] = (chunks, document_chars, text)
            chat["chars"] += document_chars
            while chat["chars"] > MAX_CHAT_CHARS or len(chat["documents"]) > _MAX_DOCUMENTS_PER_CHAT:
                _, (_, removed_chars, _) = chat["documents"].popitem(last=False)
                chat["chars"] -= removed_chars
            chat["updated"] = now
            self._chats[chat_id] = chat
            while (
                len(self._chats) > _MAX_CHAT_COUNT
                or self._total_chars() > _MAX_TOTAL_CHARS
            ):
                self._chats.popitem(last=False)

    def has_embeddings(self, chat_id: str) -> bool:
        with self._lock:
            chat = self._chats.get(chat_id)
            return bool(
                chat
                and any(
                    chunk.embedding
                    for document_chunks, _, _ in chat["documents"].values()
                    for chunk in document_chunks
                )
            )

    def retrieve(
        self,
        chat_id: str,
        query: str,
        query_embedding: tuple[float, ...] | list[float] | None = None,
    ) -> list[DocumentChunk]:
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            chat = self._chats.get(chat_id)
            if chat is None:
                return []
            self._chats.move_to_end(chat_id)
            chat["updated"] = now
            chunks = tuple(
                chunk
                for document_chunks, _, _ in chat["documents"].values()
                for chunk in document_chunks
            )
        return retrieve(query, chunks, query_embedding=query_embedding)

    def first_lines(self, chat_id: str, count: int) -> list[tuple[str, str]]:
        """Return exact opening lines from each indexed source document."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("line count must be a positive integer")
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            chat = self._chats.get(chat_id)
            if chat is None:
                return []
            self._chats.move_to_end(chat_id)
            chat["updated"] = now
            documents = tuple(chat["documents"].items())
        results = []
        for _, (chunks, _, text) in documents:
            name = chunks[0].name if chunks else "attachment"
            lines = text.splitlines()[:count]
            if lines:
                results.append((name, "\n".join(lines)))
        return results
