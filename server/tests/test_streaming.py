"""Tests for SSE stream token deduplication."""

from types import SimpleNamespace

import pytest

from app.streaming import (
    StreamAccumulator,
    chunk_text,
    merge_run_text,
    token_from_stream_event,
)


class TestMergeRunText:
    def test_delta_chunks_append(self):
        assert merge_run_text("", "안") == "안"
        assert merge_run_text("안", "녕") == "안녕"
        assert merge_run_text("안녕", "하세요") == "안녕하세요"

    def test_cumulative_chunks_replace(self):
        assert merge_run_text("", "안녕") == "안녕"
        assert merge_run_text("안녕", "안녕하세요") == "안녕하세요"

    def test_shorter_piece_ignored(self):
        assert merge_run_text("안녕하세요", "안녕") == "안녕하세요"

    def test_duplicate_same_delta_same_run(self):
        assert merge_run_text("안", "안") == "안"

    def test_duplicate_trailing_fragment(self):
        assert merge_run_text("안녕", "녕") == "안녕"
        assert merge_run_text("안녕하세요", "세요") == "안녕하세요"


class TestChunkText:
    def test_string_content(self):
        chunk = SimpleNamespace(text=None, content="hello")
        assert chunk_text(chunk) == "hello"

    def test_text_property(self):
        chunk = SimpleNamespace(text="hello", content=None)
        assert chunk_text(chunk) == "hello"

    def test_content_blocks(self):
        chunk = SimpleNamespace(
            text=None,
            content=[{"type": "text", "text": "안녕"}, {"type": "text", "text": "하세요"}],
        )
        assert chunk_text(chunk) == "안녕하세요"

    def test_content_blocks_duplicate_same_text(self):
        chunk = SimpleNamespace(
            text=None,
            content=[
                {"type": "text", "text": "안"},
                {"type": "text", "text": "안"},
            ],
        )
        assert chunk_text(chunk) == "안"


class TestStreamAccumulator:
    def test_delta_single_run(self):
        acc = StreamAccumulator()
        assert acc.ingest("run-1", "안") == "안"
        assert acc.ingest("run-1", "녕") == "녕"
        assert acc.ingest("run-1", "하세요") == "하세요"
        assert acc.emitted == "안녕하세요"

    def test_cumulative_single_run(self):
        acc = StreamAccumulator()
        assert acc.ingest("run-1", "안녕") == "안녕"
        assert acc.ingest("run-1", "안녕하세요") == "하세요"
        assert acc.emitted == "안녕하세요"

    def test_duplicate_parallel_runs_same_text(self):
        """Two run_ids streaming the same answer must not duplicate output."""
        acc = StreamAccumulator()
        first = acc.ingest("run-a", "안녕하세요")
        second = acc.ingest("run-b", "안녕하세요")
        assert first == "안녕하세요"
        assert second is None
        assert acc.emitted == "안녕하세요"

    def test_duplicate_parallel_runs_cumulative_chunks(self):
        acc = StreamAccumulator()
        tokens = []
        for _ in range(2):
            for piece in ("안녕", "안녕하세요"):
                t = acc.ingest("run-a", piece)
                if t:
                    tokens.append(t)
            for piece in ("안녕", "안녕하세요"):
                t = acc.ingest("run-b", piece)
                if t:
                    tokens.append(t)
        assert "".join(tokens) == "안녕하세요"

    def test_leader_switches_to_longer_run(self):
        """Shorter run first, then longer run — extends without repeating prefix."""
        acc = StreamAccumulator()
        assert acc.ingest("run-short", "안") == "안"
        assert acc.ingest("run-long", "안녕하세요") == "녕하세요"
        assert acc.emitted == "안녕하세요"

    def test_repeated_cumulative_same_run(self):
        acc = StreamAccumulator()
        assert acc.ingest("run-1", "안녕하세요") == "안녕하세요"
        assert acc.ingest("run-1", "안녕하세요") is None

    def test_duplicate_delta_piece_from_second_run(self):
        acc = StreamAccumulator()
        assert acc.ingest("run-a", "안") == "안"
        assert acc.ingest("run-b", "안") is None

    def test_duplicate_stream_events_same_run(self):
        """Same run_id firing duplicate delta events (observed in production)."""
        acc = StreamAccumulator()
        events = [
            ("run-1", "안"),
            ("run-1", "안"),
            ("run-1", "녕"),
            ("run-1", "녕"),
            ("run-1", "하세요"),
            ("run-1", "하세요"),
        ]
        tokens = []
        for run_id, piece in events:
            t = acc.ingest(run_id, piece)
            if t:
                tokens.append(t)
        assert "".join(tokens) == "안녕하세요"

    def test_reproduces_hellohello_pattern_without_fix(self):
        """Simulates duplicate cumulative emissions that caused '안녕하세요안녕하세요'."""
        acc = StreamAccumulator()
        # Without leader dedup, naive per-run cumulative append to client would double.
        t1 = acc.ingest("middleware-run", "안녕하세요")
        t2 = acc.ingest("model-run", "안녕하세요")
        assert t1 == "안녕하세요"
        assert t2 is None


class TestTokenFromStreamEvent:
    def test_parses_chat_model_stream(self):
        chunk = SimpleNamespace(text=None, content="안녕")
        event = {
            "event": "on_chat_model_stream",
            "run_id": "abc-123",
            "data": {"chunk": chunk},
        }
        assert token_from_stream_event(event) == ("abc-123", "안녕")

    def test_ignores_other_events(self):
        assert token_from_stream_event({"event": "on_chain_start"}) is None

    def test_ignores_missing_chunk(self):
        assert token_from_stream_event({"event": "on_chat_model_stream", "data": {}}) is None


class TestStreamEventPipeline:
    """End-to-end: LangGraph-style events → tokens (no duplicate chars)."""

    def test_duplicate_events_through_pipeline(self):
        acc = StreamAccumulator()
        events = [
            {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": SimpleNamespace(text=None, content="안")}},
            {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": SimpleNamespace(text=None, content="안")}},
            {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": SimpleNamespace(text=None, content="녕")}},
            {"event": "on_chat_model_stream", "run_id": "r1", "data": {"chunk": SimpleNamespace(text=None, content="하세요")}},
        ]
        tokens = []
        for ev in events:
            parsed = token_from_stream_event(ev)
            if parsed:
                run_id, piece = parsed
                t = acc.ingest(run_id, piece)
                if t:
                    tokens.append(t)
        assert "".join(tokens) == "안녕하세요"
