"""Two agents, one shared graph — Librarian (writes) and Scout (reads/acts).

Coordination model (RANCANGAN.md §2, Track 2 + Track 1):

* **Librarian** owns writes: it ingests text/documents through the
  deterministic extractor into FalkorDB, de-duplicates against what is
  already stored, and audits the memory (contradictions, unanswered
  questions, orphan-free counts). It never answers questions itself.
* **Scout** owns reads: it answers questions through ReasoningEngine and
  turns the *same reasoning path* into suggested actions, and it drafts a
  brief (what is known, what is contested, what is missing) purely by
  traversing the graph the Librarian wrote.

Handoff needs no re-teaching and no message bus: both agents hold a store
handle on the *same* per-user graph, so anything the Librarian ingests is
immediately traversable by Scout — which the day-2 tests prove by having
Scout answer a question about a document it never saw ingested.
"""
from __future__ import annotations

from graphmem.extract import extract_document
from graphmem.reasoning import ReasoningEngine


class Librarian:
    """Write-side agent: ingest, dedupe, audit."""

    def __init__(self, store):
        self.store = store

    def ingest_text(self, text: str, source: str = "text") -> dict:
        """Extract + ingest free text; report what was genuinely new."""
        before = self.store.stats()
        known_claims = {c["id"] for c in self.store.strongest_claims(1000)} \
            if before["total_nodes"] else set()
        doc = extract_document(text, source=source)
        new_claim_ids = [c["id"] for c in doc.get("claims", [])
                         if c["id"] not in known_claims]
        counts = self.store.ingest_document(doc)
        after = self.store.stats()
        return {
            "counts": counts,
            "new_claim_ids": new_claim_ids,
            "nodes_before": before["total_nodes"],
            "nodes_after": after["total_nodes"],
            "document": doc,
        }

    def ingest_document(self, doc: dict) -> dict:
        before = self.store.stats()
        counts = self.store.ingest_document(doc)
        after = self.store.stats()
        return {"counts": counts, "nodes_before": before["total_nodes"],
                "nodes_after": after["total_nodes"]}

    def audit(self) -> dict:
        """Health of the shared memory, from graph traversal only."""
        stats = self.store.stats()
        return {
            "stats": stats,
            "contradictions": self.store.contradictions(),
            "unanswered_questions": self.store.unanswered_questions(),
            "strongest_claims": self.store.strongest_claims(limit=3),
        }


class Scout:
    """Read-side agent: answer + act, and draft briefs."""

    def __init__(self, store):
        self.store = store
        self.engine = ReasoningEngine(store)

    def answer(self, query_text: str) -> dict:
        return self.engine.ask(query_text)

    def suggest_actions(self, result: dict) -> list[dict]:
        """Derive actions from a reasoning result — the Track-1 move.

        Actions come from the path itself, never from a template list
        unrelated to the traversal:
        * contested answer      -> resolve the contradiction first
        * cited paper           -> verify / read the source paper
        * multi-hop support     -> promote the evidence chain into a note
        * no answer             -> ingest a source about the gap concept
        """
        actions: list[dict] = []
        for w in result.get("contradiction_warnings", []):
            actions.append({
                "action": "Resolve contradiction before relying on "
                          f"claim {w['answer_claim']}",
                "reason": f"Contradicted by {w['contradicting_claim']}: "
                          f"{w['text']}",
                "priority": "high",
                "based_on": "(Claim)-[:CONTRADICTS]->(Claim)",
            })
        for citation in result.get("citations", []):
            actions.append({
                "action": f"Read / verify source paper '{citation['title']}'",
                "reason": "This paper STATES the answering claim, so it is "
                          "the citation behind the answer.",
                "priority": "medium",
                "based_on": "(Paper)-[:STATES]->(Claim)",
            })
        deep = [a for a in result.get("answers", [])
                if any(len(ch) >= 3 for ch in a.get("support_chains", []))]
        for ans in deep:
            actions.append({
                "action": f"Promote the multi-hop evidence chain under "
                          f"claim {ans['id']} into a summary note",
                "reason": "The answer rests on a SUPPORTS chain of "
                          "depth >= 2, worth capturing explicitly.",
                "priority": "low",
                "based_on": "(Claim)-[:SUPPORTS*]->(Claim|Concept)",
            })
        if not result.get("answers"):
            actions.append({
                "action": "Ingest a source covering this question, then "
                          "re-ask",
                "reason": result["answer_text"],
                "priority": "high",
                "based_on": "(no path)",
            })
        return actions

    def answer_and_act(self, query_text: str) -> dict:
        result = self.answer(query_text)
        return {**result, "suggested_actions": self.suggest_actions(result)}

    def brief(self) -> dict:
        """Morning brief from shared memory — no re-teaching involved."""
        stats = self.store.stats()
        unanswered = self.store.unanswered_questions()
        contradictions = self.store.contradictions()
        strongest = self.store.strongest_claims(limit=3)
        actions: list[dict] = []
        for q in unanswered:
            actions.append({
                "action": f"Find a source that answers: {q['text']}",
                "reason": "Question node has no incoming ANSWERS edge.",
                "priority": "medium",
                "based_on": "(Question) with no (Claim)-[:ANSWERS]",
            })
        for pair in contradictions:
            actions.append({
                "action": f"Resolve contradiction {pair['a_id']} vs "
                          f"{pair['b_id']}",
                "reason": f"'{pair['a_text']}' contradicts "
                          f"'{pair['b_text']}'",
                "priority": "high",
                "based_on": "(Claim)-[:CONTRADICTS]->(Claim)",
            })
        return {
            "stats": stats,
            "known_concepts": self.store.all_concepts(),
            "strongest_claims": strongest,
            "unanswered_questions": unanswered,
            "contradictions": contradictions,
            "suggested_actions": actions,
            "summary": (
                f"Memory holds {stats['total_nodes']} nodes / "
                f"{stats['total_edges']} edges "
                f"({stats['nodes'].get('Paper', 0)} papers, "
                f"{stats['nodes'].get('Claim', 0)} claims). "
                f"{len(unanswered)} question(s) unanswered, "
                f"{len(contradictions)} contradiction(s) open."),
        }
