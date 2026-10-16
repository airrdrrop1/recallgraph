"""Day-2 integration tests — reasoning engine + Librarian/Scout agents.

Dedicated graph (recallgraph_pytestday2), deleted afterwards. Skipped
cleanly when FalkorDB is unreachable, like the day-1 suite.
"""
import pytest

from graphmem.agents import Librarian, Scout
from graphmem.demo_data import DOCUMENTS
from graphmem.reasoning import ReasoningEngine
from graphmem.store import RecallGraphStore

GRAPH_USER = "pytestday2"


@pytest.fixture(scope="module")
def store():
    try:
        s = RecallGraphStore(user=GRAPH_USER)
        assert s.ping()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"FalkorDB not reachable: {exc}")
    s.ensure_schema()
    s.clear()
    for doc in DOCUMENTS:
        s.ingest_document(doc)
    yield s
    s.delete_graph()


@pytest.fixture(scope="module")
def engine(store):
    return ReasoningEngine(store)


def test_ask_exact_question_has_visible_reasoning_path(engine):
    result = engine.ask("Why should an AI agent store memory in a graph?")
    assert result["matched_question"]["id"] == "q-why-graph"
    assert result["answers"][0]["id"] == "claim-answer-why-graph"
    # The path must be step-by-step and name the traversals used.
    steps = result["reasoning_steps"]
    assert len(steps) >= 4
    assert [s["step"] for s in steps] == list(range(1, len(steps) + 1))
    joined = " ".join(s["traversal"] for s in steps)
    assert "ANSWERS" in joined and "SUPPORTS" in joined
    assert "CONTRADICTS" in joined and "STATES" in joined
    # Citations come from the STATES traversal, not from thin air.
    assert result["citations"][0]["id"] == "paper-flat-rag-critique-2026"
    assert result["confidence"] == pytest.approx(0.8)


def test_ask_shows_multihop_support_evidence(engine):
    result = engine.ask("Why should an AI agent store memory in a graph?")
    ans = result["answers"][0]
    # Evidence sits along the answer's outgoing SUPPORTS chains (the
    # demo data models 'supports' as claim -> evidence it builds on).
    chain_ids = {n["id"] for ch in ans["support_chains"] for n in ch}
    assert "claim-graph-beats-flat" in chain_ids
    # At least one structured chain reaches depth >= 2 (multi-hop).
    assert any(len(ch) >= 3 for ch in ans["support_chains"])
    rendered = ReasoningEngine.render_reasoning_path(result)
    assert "Reasoning path:" in rendered and "SUPPORTS" in rendered


def test_ask_concept_fallback_without_stored_question(engine):
    result = engine.ask("Tell me about Multi-hop Reasoning")
    assert result["matched_question"] is None
    assert result["answers"]
    assert result["answers"][0]["id"] == "claim-multihop-path"
    assert any("ABOUT" in s["traversal"] for s in result["reasoning_steps"])


def test_ask_unknown_question_is_honest_gap(engine):
    result = engine.ask("What is the capital of France?")
    assert result["answers"] == []
    assert result["confidence"] == 0.0
    assert "No answer in memory yet" in result["answer_text"]
    # Even a gap returns the steps it took — no silent hallucination.
    assert result["reasoning_steps"]


def test_ask_stored_but_unanswered_question(engine, store):
    # At graph level the question IS unanswered (no ANSWERS edge) —
    assert {q["id"] for q in store.unanswered_questions()} == {"q-flat-enough"}
    # — and the engine must say so in its path, then fall back to the
    # concept traversal rather than stopping dead at the gap.
    result = engine.ask("Is flat retrieval enough for agent memory?")
    assert result["matched_question"]["id"] == "q-flat-enough"
    descriptions = " ".join(s["description"]
                            for s in result["reasoning_steps"])
    assert "no ANSWERS edge yet" in descriptions
    assert result["answers"], "concept fallback should surface claims"
    assert all("Flat Retrieval" in [c["name"] for c in a["concepts"]]
               or "flat" in a["text"].lower() for a in result["answers"])


def test_explain_claim_surfaces_contradiction(engine):
    bundle = engine.explain_claim("claim-graph-beats-flat")
    assert bundle is not None
    contra_ids = {c["id"] for c in bundle["claim"]["contradictions"]}
    assert contra_ids == {"claim-flat-is-enough"}
    assert bundle["claim"]["paper"]["id"] == "paper-graph-memory-2025"
    assert "contested by 1" in bundle["summary"]
    assert engine.explain_claim("claim-does-not-exist") is None


def test_scout_actions_come_from_the_path(store):
    scout = Scout(store)
    result = scout.answer_and_act(
        "Why should an AI agent store memory in a graph?")
    kinds = " ".join(a["based_on"] for a in result["suggested_actions"])
    assert "STATES" in kinds  # citation -> read-the-paper action
    assert any("multi-hop" in a["action"]
               for a in result["suggested_actions"])
    gap = scout.answer_and_act("What is the capital of France?")
    assert gap["suggested_actions"][0]["priority"] == "high"
    assert "Ingest a source" in gap["suggested_actions"][0]["action"]


def test_scout_brief_reports_gaps_and_contradictions(store):
    brief = Scout(store).brief()
    assert brief["stats"]["total_nodes"] == 17
    assert {q["id"] for q in brief["unanswered_questions"]} == {
        "q-flat-enough"}
    assert len(brief["contradictions"]) == 1
    assert brief["suggested_actions"]
    assert "1 question(s) unanswered" in brief["summary"]


def test_librarian_audit(store):
    audit = Librarian(store).audit()
    assert audit["stats"]["total_edges"] == 30
    assert len(audit["contradictions"]) == 1
    assert audit["strongest_claims"][0]["id"] == "claim-graph-beats-flat"


def test_librarian_to_scout_handoff(store):
    """Scout answers about a doc only the Librarian ingested — shared graph."""
    librarian = Librarian(store)
    report = librarian.ingest_text(
        "PAPER: Handoff Probe Notes | Tester | 2026\n"
        "CONCEPT: Zebra Indexing — Indexing by stripes\n"
        "CLAIM [0.66]: Zebra indexing speeds recall for striped data "
        "ABOUT: Zebra Indexing\n"
        "QUESTION: Does zebra indexing help? ABOUT: Zebra Indexing\n")
    assert report["nodes_after"] > report["nodes_before"]
    assert report["new_claim_ids"], "Librarian should report the new claim"

    scout = Scout(store)  # a *separate* agent instance, same graph
    result = scout.answer("Tell me about Zebra Indexing")
    assert result["answers"], "Scout must traverse Librarian's memory"
    assert "Zebra indexing speeds recall" in result["answers"][0]["text"]
    audit = librarian.audit()
    assert audit["stats"]["nodes"]["Concept"] == 5
