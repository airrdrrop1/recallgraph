"""Day-1 integration tests — run against the live local FalkorDB.

They use a dedicated graph (recallgraph_pytestday1) and delete it afterwards,
so they never touch demo data. If FalkorDB is unreachable the whole module
is skipped with a clear reason instead of failing spuriously.
"""
import pytest

from graphmem.demo_data import DOCUMENTS
from graphmem.extract import extract_document
from graphmem.store import RecallGraphStore

GRAPH_USER = "pytestday1"


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


def test_schema_counts(store):
    stats = store.stats()
    assert stats["nodes"]["Paper"] == 3
    assert stats["nodes"]["Concept"] == 4
    assert stats["nodes"]["Claim"] == 7
    assert stats["nodes"]["Question"] == 3
    assert stats["edges"]["SUPPORTS"] >= 4
    assert stats["edges"]["CONTRADICTS"] == 1
    assert stats["edges"]["ANSWERS"] == 2
    assert stats["edges"]["CITES"] == 2


def test_claims_about_concept(store):
    claims = store.claims_about("Graph Memory")
    texts = " ".join(c["text"] for c in claims)
    assert "preserves relations" in texts
    assert len(claims) >= 4


def test_answer_question_with_path(store):
    result = store.answer_question("q-why-graph")
    assert result["question"].startswith("Why should an AI agent")
    assert len(result["answers"]) == 1
    assert result["answers"][0]["paper_id"] == "paper-flat-rag-critique-2026"
    assert result["paths"] and "ANSWERS" in result["paths"][0]
    assert "STATES" in result["paths"][0]


def test_contradiction_detected(store):
    pairs = store.contradictions()
    assert len(pairs) == 1
    assert pairs[0]["a_id"] == "claim-flat-is-enough"
    assert pairs[0]["b_id"] == "claim-graph-beats-flat"


def test_support_chain_multihop(store):
    chains = store.support_chain("claim-answer-why-graph")
    joined = "\n".join(chains)
    assert "preserves relations" in joined  # 1 hop via SUPPORTS
    assert any(chain.count("SUPPORTS") >= 2 for chain in chains)  # multi-hop


def test_cites(store):
    citers = store.cited_by("paper-graph-memory-2025")
    assert {p["id"] for p in citers} == {
        "paper-flat-rag-critique-2026", "paper-agent-coordination-2026"}


def test_per_user_isolation():
    try:
        other = RecallGraphStore(user="pytestempty")
        assert other.ping()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"FalkorDB not reachable: {exc}")
    assert other.stats()["total_nodes"] == 0
    other.delete_graph()


def test_extractor_is_deterministic():
    text = (
        "PAPER: Tiny Study | Doe | 2026\n"
        "CONCEPT: Widgets — Small test things\n"
        "CLAIM [0.9]: Widgets help testing ABOUT: Widgets\n"
        "QUESTION: Do widgets help? ABOUT: Widgets\n"
    )
    doc = extract_document(text)
    assert doc["paper"]["title"] == "Tiny Study"
    assert doc["paper"]["year"] == 2026
    assert doc["claims"][0]["confidence"] == 0.9
    assert doc["claims"][0]["about"] == ["concept-widgets"]
    assert doc["questions"][0]["asks_about"] == ["concept-widgets"]
    assert extract_document(text) == doc
