"""Day-3 integration tests — graph snapshot + the web UI (app.py).

Two dedicated graphs (recallgraph_pytestday3 for the snapshot,
recallgraph_pytestui for HTTP), both deleted afterwards. Skipped cleanly
when FalkorDB is unreachable, like the day-1/day-2 suites.
"""
import json
import threading
import urllib.request

import pytest

import app as ui_app
from graphmem.demo_data import DOCUMENTS
from graphmem.store import RecallGraphStore

GRAPH_USER = "pytestday3"
HTTP_USER = "pytestui"


def _seeded_store(user):
    try:
        s = RecallGraphStore(user=user)
        assert s.ping()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"FalkorDB not reachable: {exc}")
    s.ensure_schema()
    s.clear()
    for doc in DOCUMENTS:
        s.ingest_document(doc)
    return s


@pytest.fixture(scope="module")
def store():
    s = _seeded_store(GRAPH_USER)
    yield s
    s.delete_graph()


@pytest.fixture(scope="module")
def http_base():
    store = _seeded_store(HTTP_USER)
    server = ui_app.create_server("127.0.0.1", 0, user=HTTP_USER)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
    store.delete_graph()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


# -- snapshot (the data behind the graph view) ------------------------------

def test_snapshot_counts_match_demo_graph(store):
    snap = store.graph_snapshot()
    assert len(snap["nodes"]) == 17
    assert len(snap["edges"]) == 30
    labels = {n["label"] for n in snap["nodes"]}
    assert labels == {"Paper", "Concept", "Claim", "Question"}


def test_snapshot_edges_reference_real_nodes(store):
    snap = store.graph_snapshot()
    keys = {n["key"] for n in snap["nodes"]}
    assert all(e["from"] in keys and e["to"] in keys for e in snap["edges"])
    types = {e["type"] for e in snap["edges"]}
    assert {"SUPPORTS", "CONTRADICTS", "ANSWERS", "STATES"} <= types


def test_snapshot_titles_are_human_labels(store):
    snap = store.graph_snapshot()
    by_key = {n["key"]: n for n in snap["nodes"]}
    assert by_key["Paper:paper-graph-memory-2025"]["title"] == \
        "Graph Memory for Persistent AI Agents"
    assert by_key["Concept:concept-graph-memory"]["title"] == "Graph Memory"
    assert "preserves relations" in \
        by_key["Claim:claim-graph-beats-flat"]["title"]
    assert by_key["Claim:claim-graph-beats-flat"]["confidence"] == \
        pytest.approx(0.82)


# -- HTTP UI ------------------------------------------------------------------

def test_ui_homepage_serves_app_shell(http_base):
    status, body = _get(http_base, "/")
    assert status == 200
    assert "RecallGraph" in body and 'id="graph"' in body
    assert "Reasoning path" in body


def test_ui_graph_api_matches_snapshot(http_base):
    status, body = _get(http_base, "/api/graph")
    assert status == 200
    payload = json.loads(body)
    assert payload["ok"] is True
    assert len(payload["snapshot"]["nodes"]) == 17
    assert len(payload["snapshot"]["edges"]) == 30


def test_ui_ask_returns_answer_with_reasoning_path(http_base):
    status, payload = _post(http_base, "/api/ask", {
        "question": "Why should an AI agent store memory in a graph?"})
    assert status == 200 and payload["ok"] is True
    result = payload["result"]
    assert result["answers"][0]["id"] == "claim-answer-why-graph"
    assert result["confidence"] == pytest.approx(0.8)
    assert len(result["reasoning_steps"]) >= 4
    assert "Reasoning path:" in result["reasoning_text"]
    assert result["suggested_actions"], "Scout actions must ride along"


def test_ui_ask_unknown_question_is_honest(http_base):
    status, payload = _post(http_base, "/api/ask", {
        "question": "What is the capital of France?"})
    assert status == 200
    result = payload["result"]
    assert result["answers"] == []
    assert "No answer in memory yet" in result["answer_text"]


def test_ui_ingest_then_ask_handoff(http_base):
    """Librarian ingests through the UI API; Scout answers from it."""
    status, payload = _post(http_base, "/api/ingest", {
        "text": "PAPER: UI Handoff Notes | Tester | 2026\n"
                "CONCEPT: Quokka Caching — Cache like a quokka\n"
                "CLAIM [0.71]: Quokka caching keeps hot paths warm "
                "ABOUT: Quokka Caching\n"
                "QUESTION: Does quokka caching help? ABOUT: Quokka Caching\n"})
    assert status == 200 and payload["ok"] is True
    assert payload["report"]["nodes_after"] > payload["report"]["nodes_before"]

    status, payload = _post(http_base, "/api/ask", {
        "question": "Tell me about Quokka Caching"})
    assert status == 200
    assert payload["result"]["answers"], "Scout must see the UI ingest"
    assert "Quokka caching keeps hot paths warm" in \
        payload["result"]["answers"][0]["text"]


def test_ui_brief_api(http_base):
    status, body = _get(http_base, "/api/brief")
    assert status == 200
    payload = json.loads(body)
    assert payload["ok"] is True
    assert "question(s) unanswered" in payload["brief"]["summary"]
    assert payload["audit_counts"]["contradictions"] == 1
