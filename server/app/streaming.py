"""Helpers for SSE token streaming from LangGraph / LangChain message chunks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def chunk_text(chunk: Any) -> str:
    """Extract plain text from an AIMessageChunk-like object."""
    text = getattr(chunk, "text", None)
    if text is not None:
        return str(text)
    content = getattr(chunk, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str):
                    parts.append(block_text)
            else:
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str):
                    parts.append(block_text)
        if not parts:
            return ""
        # Some providers repeat the same text block twice in one chunk
        if len(parts) > 1 and len(set(parts)) == 1:
            return parts[0]
        return "".join(parts)
    return ""


def merge_run_text(previous: str, piece: str) -> str:
    """Merge a new stream piece into per-run accumulated text.

    Handles both delta chunks (``"안"``, ``"녕"``) and cumulative chunks
    (``"안녕"``, ``"안녕하세요"``).
    """
    if not piece:
        return previous
    if not previous:
        return piece
    if piece == previous:
        return previous
    if piece.startswith(previous):
        return piece
    if previous.startswith(piece):
        return previous
    # Re-emitted trailing fragment (e.g. duplicate "녕" after "안녕")
    if previous.endswith(piece):
        return previous
    return previous + piece


@dataclass
class StreamAccumulator:
    """Deduplicate multi-run ``on_chat_model_stream`` events into one SSE stream."""

    by_run: dict[str, str] = field(default_factory=dict)
    emitted: str = ""
    leader_run_id: str | None = None

    def ingest(self, run_id: str, piece: str) -> str | None:
        """Return the next UTF-8 suffix to send to the client, or ``None``."""
        if not piece:
            return None

        previous = self.by_run.get(run_id, "")
        merged = merge_run_text(previous, piece)
        self.by_run[run_id] = merged

        if self.leader_run_id is None:
            self.leader_run_id = run_id
        elif len(merged) > len(self.by_run.get(self.leader_run_id, "")):
            self.leader_run_id = run_id

        leader_full = self.by_run.get(self.leader_run_id, "")
        if not leader_full:
            return None

        if leader_full.startswith(self.emitted):
            token = leader_full[len(self.emitted) :]
        else:
            # Unrelated segment (rare) — show only the new leader tail
            token = leader_full

        if not token:
            return None

        self.emitted = leader_full
        return token


def token_from_stream_event(event: dict) -> tuple[str, str] | None:
    """Parse an ``astream_events`` v2 payload into ``(run_id, text_piece)``."""
    if event.get("event") != "on_chat_model_stream":
        return None
    chunk = event.get("data", {}).get("chunk")
    if chunk is None:
        return None
    run_id = str(event.get("run_id", "default"))
    piece = chunk_text(chunk)
    if not piece:
        return None
    return run_id, piece
