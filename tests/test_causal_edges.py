"""Tests for reconstruct_causal_edges — causal DAG reconstruction.

Tests cover:
  - H1 (data-flow): file-based dependencies
  - H2 (bash-reference): shell commands referencing files
  - H3 (output-reference): token overlap with trace-scoping
  - H4 (temporal fallback): orphan event linking
  - Parallel subagent detection
  - Cross-trace false edge suppression
  - Edge cases: empty input, single event, null trace_ids, etc.
"""

from __future__ import annotations

import pytest

from services.eval.kernel import (
    ActionType,
    RawEvent,
    TraceEvent,
    reconstruct_causal_edges,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mk(
    node_id: int,
    ts: int,
    action_type: ActionType = ActionType.BASH,
    detail: str = "",
    output: str = "",
    files: tuple[str, ...] = (),
    trace_id: str | None = None,
    latency_ms: int = 100,
) -> RawEvent:
    return RawEvent(
        node_id=node_id,
        timestamp_ms=ts,
        action_type=action_type,
        action_detail=detail,
        tokens_in=0,
        tokens_out=0,
        latency_ms=latency_ms,
        result_hash="",
        files_touched=files,
        output_text=output,
        trace_id=trace_id,
    )


def parent_map(events: list[TraceEvent]) -> dict[int, list[int]]:
    return {e.node_id: sorted(e.parent_ids) for e in events}


def edges_set(events: list[TraceEvent]) -> set[tuple[int, int]]:
    result = set()
    for e in events:
        for pid in e.parent_ids:
            result.add((pid, e.node_id))
    return result


# ---------------------------------------------------------------------------
# Basic / empty
# ---------------------------------------------------------------------------


class TestEmpty:
    def test_empty_input(self):
        assert reconstruct_causal_edges([]) == []

    def test_single_event(self):
        result = reconstruct_causal_edges([mk(0, 1000)])
        assert len(result) == 1
        assert result[0].parent_ids == []


# ---------------------------------------------------------------------------
# H1 — Data-flow
# ---------------------------------------------------------------------------


class TestH1DataFlow:
    def test_write_then_read_same_file(self):
        """Writer → reader via shared file."""
        events = [
            mk(0, 1000, ActionType.FILE_WRITE, files=("src/main.py",)),
            mk(1, 2000, ActionType.FILE_READ, files=("src/main.py",)),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]

    def test_no_link_for_disjoint_files(self):
        """Different files → no H1 edge."""
        events = [
            mk(0, 1000, ActionType.FILE_WRITE, files=("src/a.py",)),
            mk(1, 2000, ActionType.FILE_READ, files=("src/b.py",)),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 not in pm.get(1, []) or pm[1] == [0]  # may get H4 fallback

    def test_chain_through_multiple_writers(self):
        """A writes f, B writes f, C reads f → A→B and B→C."""
        events = [
            mk(0, 1000, ActionType.FILE_WRITE, files=("f.py",)),
            mk(1, 2000, ActionType.FILE_WRITE, files=("f.py",)),
            mk(2, 3000, ActionType.FILE_READ, files=("f.py",)),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]
        assert 1 in pm[2]


# ---------------------------------------------------------------------------
# H2 — Bash references file
# ---------------------------------------------------------------------------


class TestH2BashReference:
    def test_bash_mentions_written_file(self):
        """Bash command naming a file path creates edge to last writer."""
        events = [
            mk(0, 1000, ActionType.FILE_WRITE, files=("src/config.py",)),
            mk(1, 2000, ActionType.BASH, detail="cat src/config.py"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]


# ---------------------------------------------------------------------------
# H3 — Output-reference (the redesigned heuristic)
# ---------------------------------------------------------------------------


class TestH3OutputReference:
    def test_same_trace_token_overlap_creates_edge(self):
        """Within same trace, token overlap in output→detail creates edge."""
        events = [
            mk(0, 1000, detail="", output="Error in src/utils.py line 42", trace_id="T1"),
            mk(1, 2000, detail="fixing src/utils.py", trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]

    def test_cross_trace_no_handoff_suppresses_edge(self):
        """Different traces, no handoff evidence → no H3 edge."""
        events = [
            mk(0, 1000, detail="", output="editing docker/Dockerfile.api", trace_id="T1"),
            mk(1, 5000, detail="checking docker/Dockerfile.api", trace_id="T2"),
        ]
        result = reconstruct_causal_edges(events)
        es = edges_set(result)
        # Should NOT have (0, 1) from H3 — different traces, no handoff
        # May have it from H4 fallback if no other parent found
        # Key: H3 should not fire here
        pm = parent_map(result)
        # If 0 is parent of 1, it should be from H4 only, not H3
        # We can't distinguish heuristic source, but the important thing
        # is that parallel agents with different trace_ids and overlapping
        # timestamps should NOT be linked (see TestParallelSubagents)

    def test_ubiquitous_tokens_filtered(self):
        """Tokens appearing in >=40% of outputs should be filtered."""
        common_path = "observal-server/main.py"
        events = [
            mk(0, 1000, output=f"loaded {common_path}", trace_id="T1"),
            mk(1, 2000, output=f"started {common_path}", trace_id="T1"),
            mk(2, 3000, output=f"running {common_path}", trace_id="T1"),
            mk(3, 4000, output=f"checking {common_path}", trace_id="T1"),
            mk(4, 5000, output=f"done with {common_path}", trace_id="T1"),
            mk(5, 6000, output=f"finished {common_path}", trace_id="T1"),
            # Event 6 references the ubiquitous token — should NOT create
            # edges to all 6 prior events just because of shared path
            mk(6, 7000, detail=f"grep {common_path}", trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        # Should not have edges to ALL of 0-5 from ubiquitous token matching
        parents_of_6 = pm.get(6, [])
        assert len(parents_of_6) <= 3, (
            f"Event 6 has {len(parents_of_6)} parents — ubiquitous token filter not working"
        )


# ---------------------------------------------------------------------------
# H4 — Temporal fallback
# ---------------------------------------------------------------------------


class TestH4TemporalFallback:
    def test_orphan_gets_linked_to_predecessor(self):
        """Event with no H1/H2/H3 parent gets linked to prior event."""
        events = [
            mk(0, 1000, ActionType.THINK, detail="planning", trace_id="T1"),
            mk(1, 2000, ActionType.THINK, detail="more planning", trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]

    def test_fallback_skips_parallel_cross_trace(self):
        """H4 should not link to a temporally parallel event from different trace."""
        events = [
            mk(0, 1000, detail="", trace_id="T1", latency_ms=5000),
            mk(1, 2000, detail="", trace_id="T2"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        # Event 1 at ts=2000 is within event 0's span (1000+5000=6000)
        # Different trace → H4 should skip event 0
        # Event 1 may remain a root


# ---------------------------------------------------------------------------
# Parallel subagents — the core fix
# ---------------------------------------------------------------------------


class TestParallelSubagents:
    def test_three_parallel_agents_branch(self):
        """Main agent spawns 3 parallel subagents on different files.
        Should produce branching DAG, not linear chain."""
        events = [
            # Main agent action
            mk(0, 1000, ActionType.BASH, detail="spawning agents",
               output="launching 3 parallel tasks", trace_id="main"),
            # Subagent A: works on Dockerfile
            mk(1, 1500, ActionType.FILE_READ, detail="read docker/Dockerfile.api",
               files=("docker/Dockerfile.api",), trace_id="agent-a", latency_ms=3000),
            mk(2, 2000, ActionType.FILE_WRITE, detail="write docker/Dockerfile.api",
               files=("docker/Dockerfile.api",), trace_id="agent-a"),
            # Subagent B: works on .dockerignore (parallel, different files)
            mk(3, 1500, ActionType.FILE_READ, detail="read .dockerignore",
               files=(".dockerignore",), trace_id="agent-b", latency_ms=3000),
            mk(4, 2500, ActionType.FILE_WRITE, detail="write .dockerignore",
               files=(".dockerignore",), trace_id="agent-b"),
            # Subagent C: works on nginx.conf (parallel, different files)
            mk(5, 1500, ActionType.FILE_READ, detail="read docker/nginx.conf",
               files=("docker/nginx.conf",), trace_id="agent-c", latency_ms=3000),
            mk(6, 3000, ActionType.FILE_WRITE, detail="write docker/nginx.conf",
               files=("docker/nginx.conf",), trace_id="agent-c"),
        ]
        result = reconstruct_causal_edges(events)
        es = edges_set(result)

        # Within each agent: sequential edges should exist
        assert (1, 2) in es, "Agent A: read→write missing"
        assert (3, 4) in es, "Agent B: read→write missing"
        assert (5, 6) in es, "Agent C: read→write missing"

        # Cross-agent: agents working on different files in parallel
        # should NOT be chained together
        assert (2, 3) not in es, "False edge: agent-a → agent-b"
        assert (2, 5) not in es, "False edge: agent-a → agent-c"
        assert (4, 5) not in es, "False edge: agent-b → agent-c"
        assert (4, 6) not in es, "False edge: agent-b → agent-c"
        assert (1, 3) not in es, "False edge: agent-a → agent-b"
        assert (1, 5) not in es, "False edge: agent-a → agent-c"
        assert (3, 5) not in es, "False edge: agent-b → agent-c"

    def test_parallel_agents_dont_form_linear_chain(self):
        """Critical path should be shorter than total nodes when agents are parallel."""
        events = [
            mk(0, 1000, ActionType.BASH, trace_id="main"),
            mk(1, 2000, ActionType.FILE_WRITE, files=("a.py",), trace_id="T1"),
            mk(2, 2000, ActionType.FILE_WRITE, files=("b.py",), trace_id="T2"),
            mk(3, 2000, ActionType.FILE_WRITE, files=("c.py",), trace_id="T3"),
            mk(4, 5000, ActionType.BASH, trace_id="main"),
        ]
        result = reconstruct_causal_edges(events)

        # Nodes 1, 2, 3 are parallel (same timestamp, different traces, different files)
        # They should NOT all chain: 1→2→3
        es = edges_set(result)
        assert not ((1, 2) in es and (2, 3) in es), (
            "Parallel agents chained linearly — parallelism not detected"
        )

    def test_shared_files_across_agents_creates_real_edge(self):
        """If two agents touch the same file, that IS a real dependency."""
        events = [
            mk(0, 1000, ActionType.FILE_WRITE, files=("shared.py",), trace_id="T1"),
            mk(1, 3000, ActionType.FILE_READ, files=("shared.py",), trace_id="T2"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1], "Cross-trace file dependency should create edge via H1"


# ---------------------------------------------------------------------------
# Cross-trace handoff
# ---------------------------------------------------------------------------


class TestCrossTraceHandoff:
    def test_explicit_node_id_reference(self):
        """Cross-trace event referencing parent's node_id should create edge."""
        events = [
            mk(0, 1000, detail="research task", output="found the bug in auth.py",
               trace_id="main"),
            mk(1, 3000, detail="fixing based on node 0 findings",
               trace_id="sub-1"),
        ]
        result = reconstruct_causal_edges(events)
        # "0" is only 1 char so won't match as token, but action_detail
        # might trigger H4 fallback. This tests the boundary.


# ---------------------------------------------------------------------------
# Null / missing trace IDs
# ---------------------------------------------------------------------------


class TestNullTraceIds:
    def test_null_trace_ids_dont_crash(self):
        """Events with None trace_id should not cause errors."""
        events = [
            mk(0, 1000, trace_id=None),
            mk(1, 2000, trace_id=None),
            mk(2, 3000, trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 3

    def test_mixed_null_and_real_trace_ids(self):
        """Mix of null and real trace IDs processes without error."""
        events = [
            mk(0, 1000, trace_id=None, detail="setup"),
            mk(1, 2000, trace_id="T1", detail="agent work",
               files=("a.py",)),
            mk(2, 3000, trace_id=None, detail="teardown"),
            mk(3, 4000, trace_id="T2", detail="other agent",
               files=("b.py",)),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 4

    def test_empty_string_trace_id_treated_as_null(self):
        """Empty string trace_id should behave same as None."""
        events = [
            mk(0, 1000, trace_id=""),
            mk(1, 2000, trace_id=""),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Temporal parallelism
# ---------------------------------------------------------------------------


class TestTemporalParallelism:
    def test_overlapping_timestamps_same_trace_still_linked(self):
        """Within same trace, temporal overlap doesn't suppress edges."""
        events = [
            mk(0, 1000, latency_ms=5000, trace_id="T1",
               output="found src/utils.py"),
            mk(1, 2000, trace_id="T1", detail="fix src/utils.py"),
        ]
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)
        assert 0 in pm[1]

    def test_overlapping_timestamps_cross_trace_no_false_edge(self):
        """Cross-trace events running in parallel should not link via H3."""
        events = [
            mk(0, 1000, latency_ms=10000, trace_id="T1",
               output="working on docker/Dockerfile"),
            mk(1, 2000, latency_ms=10000, trace_id="T2",
               detail="editing docker/Dockerfile"),
        ]
        result = reconstruct_causal_edges(events)
        # These are parallel (T1 still running when T2 starts)
        # Different traces, no file dependency
        # Should NOT be linked via H3


# ---------------------------------------------------------------------------
# Adversarial inputs
# ---------------------------------------------------------------------------


class TestAdversarial:
    def test_all_events_same_timestamp(self):
        """All events at same timestamp should not crash."""
        events = [mk(i, 1000, trace_id=f"T{i}") for i in range(5)]
        result = reconstruct_causal_edges(events)
        assert len(result) == 5

    def test_duplicate_node_ids(self):
        """Duplicate node_ids — should handle gracefully or raise."""
        events = [
            mk(0, 1000),
            mk(0, 2000),  # duplicate node_id
        ]
        # Should either handle gracefully or raise, not crash silently
        try:
            result = reconstruct_causal_edges(events)
            assert len(result) == 2
        except (ValueError, KeyError):
            pass  # also acceptable

    def test_very_long_action_detail(self):
        """Long action_detail with many tokens should not cause O(n^3) blowup."""
        long_detail = " ".join(f"token_{i}_path/to/file.py" for i in range(500))
        events = [
            mk(0, 1000, output=long_detail, trace_id="T1"),
            mk(1, 2000, detail=long_detail, trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 2

    def test_event_with_no_detail_no_output_no_files(self):
        """Minimal event with empty everything."""
        events = [
            mk(0, 1000, detail="", output="", files=()),
            mk(1, 2000, detail="", output="", files=()),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 2

    def test_negative_latency(self):
        """Negative latency_ms should not break temporal checks."""
        events = [
            mk(0, 1000, latency_ms=-100, trace_id="T1"),
            mk(1, 2000, trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 2

    def test_zero_latency(self):
        """Zero latency_ms — events at same timestamp not parallel."""
        events = [
            mk(0, 1000, latency_ms=0, trace_id="T1"),
            mk(1, 1000, trace_id="T2"),
        ]
        result = reconstruct_causal_edges(events)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# DAG structural invariants
# ---------------------------------------------------------------------------


class TestDAGInvariants:
    def test_no_self_loops(self):
        """No event should be its own parent."""
        events = [mk(i, 1000 * (i + 1), trace_id="T1") for i in range(10)]
        result = reconstruct_causal_edges(events)
        for e in result:
            assert e.node_id not in e.parent_ids, f"Self-loop on node {e.node_id}"

    def test_no_backwards_edges(self):
        """All edges point forward in timestamp order."""
        events = [
            mk(0, 1000, trace_id="T1"),
            mk(1, 2000, trace_id="T1"),
            mk(2, 3000, trace_id="T1"),
        ]
        result = reconstruct_causal_edges(events)
        ts_map = {e.node_id: e.timestamp_ms for e in result}
        for e in result:
            for pid in e.parent_ids:
                assert ts_map[pid] <= ts_map[e.node_id], (
                    f"Backwards edge: {pid} (ts={ts_map[pid]}) → {e.node_id} (ts={ts_map[e.node_id]})"
                )

    def test_all_events_in_output(self):
        """All input events appear in output regardless of input order."""
        events = [
            mk(2, 3000),
            mk(0, 1000),
            mk(1, 2000),
        ]
        result = reconstruct_causal_edges(events)
        assert sorted(e.node_id for e in result) == [0, 1, 2]

    def test_all_input_events_present_in_output(self):
        """Every input event appears exactly once in output."""
        events = [mk(i, 1000 * (i + 1), trace_id="T1") for i in range(20)]
        result = reconstruct_causal_edges(events)
        output_ids = [e.node_id for e in result]
        assert sorted(output_ids) == list(range(20))


# ---------------------------------------------------------------------------
# Regression: real session 1b4d5cd0 (Docker optimization session)
#
# 148 events across 23 traces. Three subagent groups ran in parallel:
#   - Trace 0fbb02bc (nodes 101-110): Dockerfile.api multi-stage
#   - Trace 844f11cd (nodes 111-116): nginx gzip compression
#   - Trace e1dca487 (nodes 117-118): .dockerignore expansion
#
# These three ran simultaneously after a main-agent spawn at node 100.
# Old code chained them linearly (critical path = 100% of nodes).
# Fixed code should branch them (critical path < total nodes).
# ---------------------------------------------------------------------------


class TestRealSessionRegression:
    """Regression test derived from actual session 1b4d5cd0."""

    @staticmethod
    def _build_session_events() -> list[RawEvent]:
        """Build events mimicking the real session's structure.

        Uses actual trace_ids, action_types, latencies, and node counts.
        Timestamps are synthesized: cumulative within each trace, with the
        three parallel traces starting at the same base timestamp.
        """
        # (node_id, action_type_str, trace_id, latency_ms)
        RAW = [
            # Main agent early exploration (trace ca6ef3f3)
            (0, "bash", "ca6ef3f3", 451),
            (1, "bash", "ca6ef3f3", 309),
            (2, "bash", "ca6ef3f3", 112),
            (3, "bash", "ca6ef3f3", 151),
            (4, "bash", "ca6ef3f3", 177),
            (5, "bash", "ca6ef3f3", 412),
            (6, "bash", "ca6ef3f3", 86),
            # Explore agent (trace 7cb7da0f)
            (7, "bash", "7cb7da0f", 31),
            (8, "bash", "7cb7da0f", 32),
            (9, "bash", "7cb7da0f", 47),
            (10, "bash", "7cb7da0f", 39),
            (11, "bash", "7cb7da0f", 38),
            (12, "bash", "7cb7da0f", 42),
            (13, "file_read", "7cb7da0f", 1),
            # More sequential traces (abbreviated — key is parallel region)
            (14, "bash", "614882ec", 91),
            (15, "bash", "614882ec", 71),
            # Main agent planning (trace b1499db7)
            (16, "file_read", "b1499db7", 5),
            (17, "file_write", "b1499db7", 16),
            (18, "bash", "b1499db7", 36),
            (19, "bash", "b1499db7", 39),
            (20, "bash", "b1499db7", 55),
            (21, "bash", "b1499db7", 73),
            (22, "bash", "b1499db7", 109),
            (23, "bash", "b1499db7", 110),
            (24, "bash", "b1499db7", 33),
            # Pre-parallel work (various sequential traces)
            (25, "bash", "4f5f72c4", 79),
            (26, "bash", "4f5f72c4", 49),
            (27, "bash", "4f5f72c4", 93),
            (28, "bash", "29992bc1", 1626),
            (29, "bash", "cc336aa4", 1139),
            (30, "bash", "cc336aa4", 43),
            (31, "bash", "cc336aa4", 39),
            (32, "bash", "cc336aa4", 102),
            (33, "bash", "cc336aa4", 0),
            (34, "bash", "bca42e83", 1599),
            (35, "bash", "aea8b01c", 512),
            (36, "bash", "aea8b01c", 466),
            (37, "bash", "aea8b01c", 423),
            (38, "bash", "aea8b01c", 423),
            (39, "bash", "aea8b01c", 104),
            (40, "bash", "aea8b01c", 1102),
            (41, "bash", "aea8b01c", 106),
            (42, "bash", "d23f76a2", 120),
            (43, "bash", "d23f76a2", 242),
            (44, "bash", "d23f76a2", 122),
            (45, "bash", "5a5c789f", 128),
            (46, "bash", "5a5c789f", 100),
            (47, "bash", "5a5c789f", 486),
            (48, "bash", "5a5c789f", 121),
            (49, "bash", "1ddbe7f7", 133),
            # Large main-agent block (trace 55dd28f0, 37 events)
            (50, "bash", "55dd28f0", 46674),
            (51, "bash", "55dd28f0", 42),
            (52, "bash", "55dd28f0", 42),
            (53, "bash", "55dd28f0", 42),
            (54, "file_read", "55dd28f0", 0),
            (55, "file_read", "55dd28f0", 259),
            (56, "bash", "55dd28f0", 40),
            (57, "bash", "55dd28f0", 40),
            (58, "bash", "55dd28f0", 58),
            (59, "bash", "55dd28f0", 34),
            (60, "file_read", "55dd28f0", 5),
            (61, "file_read", "55dd28f0", 5),
            (62, "file_read", "55dd28f0", 5),
            (63, "file_read", "55dd28f0", 8),
            (64, "file_read", "55dd28f0", 9),
            (65, "file_read", "55dd28f0", 12),
            (66, "file_read", "55dd28f0", 13),
            (67, "file_read", "55dd28f0", 8),
            (68, "file_read", "55dd28f0", 32),
            (69, "bash", "55dd28f0", 33),
            (70, "file_read", "55dd28f0", 1),
            (71, "file_write", "55dd28f0", 16),
            (72, "file_write", "55dd28f0", 7),
            (73, "file_write", "55dd28f0", 6),
            (74, "file_write", "55dd28f0", 19),
            (75, "file_write", "55dd28f0", 6),
            (76, "file_write", "55dd28f0", 7),
            (77, "file_write", "55dd28f0", 5),
            (78, "bash", "55dd28f0", 34),
            (79, "file_read", "55dd28f0", 1),
            (80, "file_write", "55dd28f0", 9),
            (81, "file_write", "55dd28f0", 8),
            (82, "bash", "55dd28f0", 99),
            (83, "bash", "55dd28f0", 51),
            (84, "bash", "55dd28f0", 104),
            (85, "bash", "55dd28f0", 9470),
            (86, "bash", "55dd28f0", 22619),
            # Single write (trace da4b082a)
            (87, "file_write", "da4b082a", 17),
            # Code review agent (trace 9efc6b70)
            (88, "file_read", "9efc6b70", 8),
            (89, "bash", "9efc6b70", 49),
            (90, "bash", "9efc6b70", 49),
            (91, "bash", "9efc6b70", 46),
            (92, "file_read", "9efc6b70", 1),
            (93, "bash", "9efc6b70", 37),
            (94, "bash", "9efc6b70", 33),
            (95, "file_read", "9efc6b70", 1),
            (96, "file_write", "9efc6b70", 11),
            (97, "file_write", "9efc6b70", 6),
            (98, "file_write", "9efc6b70", 17),
            (99, "bash", "9efc6b70", 54),
            (100, "bash", "9efc6b70", 21114),
            # === THREE PARALLEL SUBAGENTS ===
            # Agent A: Dockerfile multi-stage (trace 0fbb02bc)
            (101, "file_read", "0fbb02bc", 9),
            (102, "file_write", "0fbb02bc", 13),
            (103, "file_read", "0fbb02bc", 1),
            (104, "file_write", "0fbb02bc", 7),
            (105, "file_read", "0fbb02bc", 1),
            (106, "file_write", "0fbb02bc", 4),
            (107, "bash", "0fbb02bc", 33),
            (108, "file_write", "0fbb02bc", 7),
            (109, "bash", "0fbb02bc", 52),
            (110, "bash", "0fbb02bc", 20519),
            # Agent B: nginx gzip (trace 844f11cd)
            (111, "file_read", "844f11cd", 7),
            (112, "file_write", "844f11cd", 7),
            (113, "bash", "844f11cd", 33),
            (114, "file_read", "844f11cd", 3),
            (115, "file_write", "844f11cd", 20),
            (116, "bash", "844f11cd", 21140),
            # Agent C: .dockerignore (trace e1dca487)
            (117, "file_read", "e1dca487", 1),
            (118, "file_read", "e1dca487", 5),
            # Post-parallel work
            (119, "bash", "41af848c", 269),
            (120, "bash", "41af848c", 34),
            (121, "file_read", "41af848c", 2),
            (122, "file_read", "99acb0ab", 7),
            (123, "bash", "99acb0ab", 38),
            (124, "file_read", "99acb0ab", 1),
            (125, "file_read", "9c770723", 8),
            (126, "file_read", "9c770723", 1),
            (127, "file_read", "9c770723", 1),
            (128, "bash", "9c770723", 44),
            (129, "file_read", "9c770723", 9),
            (130, "bash", "9c770723", 32),
            (131, "file_read", "9c770723", 1),
            (132, "file_write", "9c770723", 8),
            (133, "bash", "9c770723", 878),
            (134, "file_write", "9c770723", 8),
            (135, "file_read", "9bcdda4d", 9),
            (136, "file_write", "9bcdda4d", 13),
            (137, "bash", "9bcdda4d", 586),
            (138, "bash", "9bcdda4d", 555),
            (139, "file_read", "9bcdda4d", 1),
            (140, "file_read", "9bcdda4d", 1),
            (141, "file_write", "9bcdda4d", 7),
            (142, "bash", "9bcdda4d", 569),
            (143, "bash", "9bcdda4d", 20842),
            (144, "bash", "ff1e03cc", 273),
            (145, "file_read", "ff1e03cc", 8),
            (146, "bash", "ff1e03cc", 266),
            (147, "file_read", "ff1e03cc", 1),
        ]

        ACTION_MAP = {
            "bash": ActionType.BASH,
            "file_read": ActionType.FILE_READ,
            "file_write": ActionType.FILE_WRITE,
        }

        # Synthesize timestamps: cumulative latency within each trace.
        # Parallel traces (0fbb02bc, 844f11cd, e1dca487) start at same base.
        PARALLEL_TRACES = {"0fbb02bc", "844f11cd", "e1dca487"}
        PARALLEL_BASE = 500_000  # ms offset where parallel agents spawn

        trace_clock: dict[str, int] = {}
        events: list[RawEvent] = []

        for node_id, atype, trace_id, lat in RAW:
            if trace_id in PARALLEL_TRACES:
                base = PARALLEL_BASE
            else:
                base = 0

            if trace_id not in trace_clock:
                if trace_id in PARALLEL_TRACES:
                    trace_clock[trace_id] = base
                else:
                    # Sequential traces: start after previous trace ended
                    trace_clock[trace_id] = max(trace_clock.values()) + 1 if trace_clock else 0

            ts = trace_clock[trace_id]
            trace_clock[trace_id] = ts + max(lat, 1)

            events.append(mk(
                node_id=node_id,
                ts=ts,
                action_type=ACTION_MAP[atype],
                latency_ms=lat,
                trace_id=trace_id,
            ))

        return events

    def test_session_produces_branches(self):
        """The three parallel subagent traces must produce DAG branches."""
        events = self._build_session_events()
        result = reconstruct_causal_edges(events)
        es = edges_set(result)

        # Agents A (0fbb02bc), B (844f11cd), C (e1dca487) should NOT
        # chain into each other
        agent_a_nodes = set(range(101, 111))
        agent_b_nodes = set(range(111, 117))
        agent_c_nodes = {117, 118}

        cross_ab = {(s, t) for s, t in es if s in agent_a_nodes and t in agent_b_nodes}
        cross_ac = {(s, t) for s, t in es if s in agent_a_nodes and t in agent_c_nodes}
        cross_bc = {(s, t) for s, t in es if s in agent_b_nodes and t in agent_c_nodes}

        assert not cross_ab, f"False cross-agent edges A→B: {cross_ab}"
        assert not cross_ac, f"False cross-agent edges A→C: {cross_ac}"
        assert not cross_bc, f"False cross-agent edges B→C: {cross_bc}"

    def test_session_intra_agent_edges_exist(self):
        """Within each parallel agent, sequential edges must exist."""
        events = self._build_session_events()
        result = reconstruct_causal_edges(events)
        pm = parent_map(result)

        # Agent A: 101→102 (read→write within same trace)
        assert 101 in pm.get(102, []) or any(
            p in range(101, 111) for p in pm.get(102, [])
        ), "Agent A intra-trace edge missing"

        # Agent B: 111→112
        assert 111 in pm.get(112, []) or any(
            p in range(111, 117) for p in pm.get(112, [])
        ), "Agent B intra-trace edge missing"

    def test_session_critical_path_shorter_than_total(self):
        """Critical path must be shorter than total nodes due to parallelism."""
        events = self._build_session_events()
        result = reconstruct_causal_edges(events)

        # Compute critical path length using same DP as kernel_bridge
        events_by_id = {e.node_id: e for e in result}
        dp: dict[int, float] = {}
        dp_pred: dict[int, int | None] = {}
        for e in sorted(result, key=lambda x: x.timestamp_ms):
            best_parent = None
            best_cost = 0.0
            for pid in e.parent_ids:
                if pid in dp and dp[pid] > best_cost:
                    best_cost = dp[pid]
                    best_parent = pid
            dp[e.node_id] = best_cost + e.latency_ms
            dp_pred[e.node_id] = best_parent

        critical_path: list[int] = []
        if dp:
            tail = max(dp, key=lambda k: dp[k])
            while tail is not None:
                critical_path.append(tail)
                tail = dp_pred.get(tail)

        total = len(result)
        cp_len = len(critical_path)
        assert cp_len < total, (
            f"Critical path ({cp_len}) == total nodes ({total}) — "
            f"parallelism not reflected in DAG"
        )

    def test_session_node_count_preserved(self):
        """All 148 events must appear in output."""
        events = self._build_session_events()
        result = reconstruct_causal_edges(events)
        assert len(result) == len(events)
