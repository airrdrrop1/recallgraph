"""FalkorDB store for RecallGraph — all Cypher lives in this module.

Schema (day-1 foundation, per build plan 15-18 Oct 2026):

Nodes
  Paper    {id, title, authors, year, source}
  Concept  {id, name, description}
  Claim    {id, text, confidence}   confidence: float 0..1
  Question {id, text}

Primary semantic edges (build-plan spec)
  (Claim)-[:SUPPORTS]->(Claim|Concept)
  (Claim)-[:CONTRADICTS]->(Claim)
  (Claim)-[:ANSWERS]->(Question)
  (Paper)-[:CITES]->(Paper)

Structural edges (glue so a paper/question can be traversed to its claims)
  (Paper)-[:STATES]->(Claim)        a paper states a claim
  (Claim)-[:ABOUT]->(Concept)      a claim is about a concept
  (Question)-[:ASKS_ABOUT]->(Concept)

One FalkorDB graph per user/tenant: graph name is ``recallgraph_<user>``
(sanitised). This keeps memories isolated, which the tests verify.
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable

from falkordb import FalkorDB

NODE_LABELS = ("Paper", "Concept", "Claim", "Question")
PRIMARY_EDGE_TYPES = ("SUPPORTS", "CONTRADICTS", "ANSWERS", "CITES")
STRUCTURAL_EDGE_TYPES = ("STATES", "ABOUT", "ASKS_ABOUT")
ALL_EDGE_TYPES = PRIMARY_EDGE_TYPES + STRUCTURAL_EDGE_TYPES


def _sanitise(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(name).strip()).strip("_")
    return cleaned or "default"


def _esc(value: Any) -> Any:
    """Pass values through as Cypher parameters (never string-interpolated)."""
    return value


class RecallGraphStore:
    """Thin, explicit wrapper around one FalkorDB graph."""

    def __init__(self, user: str = "demo", host: str | None = None,
                 port: int | None = None, graph_name: str | None = None):
        self.host = host or os.environ.get("FALKORDB_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("FALKORDB_PORT", "6379"))
        self.user = _sanitise(user)
        self.graph_name = graph_name or f"recallgraph_{self.user}"
        self.db = FalkorDB(host=self.host, port=self.port)
        self.graph = self.db.select_graph(self.graph_name)

    # -- low level ---------------------------------------------------------
    def query(self, cypher: str, params: dict | None = None):
        return self.graph.query(cypher, params or {})

    def ping(self) -> bool:
        return self.query("RETURN 1 AS one").result_set[0][0] == 1

    def clear(self) -> None:
        self.query("MATCH (n) DETACH DELETE n")

    def delete_graph(self) -> None:
        try:
            self.graph.delete()
        except Exception:
            pass

    # -- schema ------------------------------------------------------------
    def ensure_schema(self) -> None:
        """Create indexes for the lookup properties of every node label.

        FalkorDB creates the index if missing; re-running is expected to be
        safe for the build (errors for existing indexes are ignored).
        """
        for label, prop in (("Paper", "id"), ("Concept", "id"),
                            ("Claim", "id"), ("Question", "id"),
                            ("Concept", "name")):
            try:
                self.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
            except Exception:
                # Index already exists (or server variant without IF NOT EXISTS)
                pass

    # -- node upserts --------------------------------------------------------
    def upsert_paper(self, paper_id: str, title: str, authors: str = "",
                     year: int | None = None, source: str = "") -> None:
        self.query(
            "MERGE (p:Paper {id: $id}) "
            "SET p.title = $title, p.authors = $authors, "
            "    p.year = $year, p.source = $source",
            {"id": paper_id, "title": title, "authors": authors,
             "year": year, "source": source},
        )

    def upsert_concept(self, concept_id: str, name: str,
                       description: str = "") -> None:
        self.query(
            "MERGE (c:Concept {id: $id}) SET c.name = $name, "
            "c.description = $description",
            {"id": concept_id, "name": name, "description": description},
        )

    def upsert_claim(self, claim_id: str, text: str,
                     confidence: float = 0.5) -> None:
        self.query(
            "MERGE (c:Claim {id: $id}) SET c.text = $text, "
            "c.confidence = $confidence",
            {"id": claim_id, "text": text, "confidence": float(confidence)},
        )

    def upsert_question(self, question_id: str, text: str) -> None:
        self.query(
            "MERGE (q:Question {id: $id}) SET q.text = $text",
            {"id": question_id, "text": text},
        )

    # -- edges ---------------------------------------------------------------
    def add_edge(self, edge_type: str, from_label: str, from_id: str,
                 to_label: str, to_id: str) -> None:
        if edge_type not in ALL_EDGE_TYPES:
            raise ValueError(f"unknown edge type: {edge_type}")
        if from_label not in NODE_LABELS or to_label not in NODE_LABELS:
            raise ValueError(f"unknown node label: {from_label}/{to_label}")
        # Labels / edge types come from the whitelists above; ids are params.
        self.query(
            f"MATCH (a:{from_label} {{id: $from_id}}), "
            f"(b:{to_label} {{id: $to_id}}) "
            f"MERGE (a)-[:{edge_type}]->(b)",
            {"from_id": from_id, "to_id": to_id},
        )

    # Convenience wrappers with the semantics from the build plan.
    def paper_states_claim(self, paper_id: str, claim_id: str) -> None:
        self.add_edge("STATES", "Paper", paper_id, "Claim", claim_id)

    def claim_about_concept(self, claim_id: str, concept_id: str) -> None:
        self.add_edge("ABOUT", "Claim", claim_id, "Concept", concept_id)

    def claim_supports(self, claim_id: str, target_label: str,
                       target_id: str) -> None:
        self.add_edge("SUPPORTS", "Claim", claim_id, target_label, target_id)

    def claim_contradicts(self, claim_id: str, other_claim_id: str) -> None:
        self.add_edge("CONTRADICTS", "Claim", claim_id, "Claim", other_claim_id)

    def claim_answers_question(self, claim_id: str, question_id: str) -> None:
        self.add_edge("ANSWERS", "Claim", claim_id, "Question", question_id)

    def paper_cites_paper(self, paper_id: str, cited_paper_id: str) -> None:
        self.add_edge("CITES", "Paper", paper_id, "Paper", cited_paper_id)

    def question_asks_about(self, question_id: str, concept_id: str) -> None:
        self.add_edge("ASKS_ABOUT", "Question", question_id,
                      "Concept", concept_id)

    # -- ingest --------------------------------------------------------------
    def ingest_document(self, doc: dict) -> dict:
        """Ingest one structured document (see demo_data / extract output).

        Expected keys (all optional except where an item needs an id):
          paper:     {id, title, authors, year, source}
          concepts:  [{id, name, description}]
          claims:    [{id, text, confidence, about: [concept_id],
                       supports: [{label, id}], contradicts: [claim_id],
                       answers: [question_id]}]
          questions: [{id, text, asks_about: [concept_id]}]
          cites:     [paper_id]  (papers the doc's paper cites)
        Returns counts of what was written.
        """
        counts = {"papers": 0, "concepts": 0, "claims": 0, "questions": 0,
                  "edges": 0}
        paper = doc.get("paper")
        if paper:
            self.upsert_paper(paper["id"], paper.get("title", ""),
                              paper.get("authors", ""), paper.get("year"),
                              paper.get("source", ""))
            counts["papers"] += 1
        for concept in doc.get("concepts", []):
            self.upsert_concept(concept["id"], concept.get("name", ""),
                                concept.get("description", ""))
            counts["concepts"] += 1
        for question in doc.get("questions", []):
            self.upsert_question(question["id"], question.get("text", ""))
            counts["questions"] += 1
        for claim in doc.get("claims", []):
            self.upsert_claim(claim["id"], claim.get("text", ""),
                              claim.get("confidence", 0.5))
            counts["claims"] += 1
            if paper:
                self.paper_states_claim(paper["id"], claim["id"])
                counts["edges"] += 1
            for concept_id in claim.get("about", []):
                self.claim_about_concept(claim["id"], concept_id)
                counts["edges"] += 1
            for target in claim.get("supports", []):
                self.claim_supports(claim["id"], target["label"],
                                    target["id"])
                counts["edges"] += 1
            for other_id in claim.get("contradicts", []):
                self.claim_contradicts(claim["id"], other_id)
                counts["edges"] += 1
            for question_id in claim.get("answers", []):
                self.claim_answers_question(claim["id"], question_id)
                counts["edges"] += 1
        if paper:
            for cited_id in doc.get("cites", []):
                self.paper_cites_paper(paper["id"], cited_id)
                counts["edges"] += 1
        for question in doc.get("questions", []):
            for concept_id in question.get("asks_about", []):
                self.question_asks_about(question["id"], concept_id)
                counts["edges"] += 1
        return counts

    # -- basic queries (day-1 verified surface) ------------------------------
    def stats(self) -> dict:
        nodes = {}
        for label in NODE_LABELS:
            rows = self.query(
                f"MATCH (n:{label}) RETURN count(n) AS c").result_set
            nodes[label] = rows[0][0]
        edges = {}
        for edge_type in ALL_EDGE_TYPES:
            rows = self.query(
                f"MATCH ()-[r:{edge_type}]->() RETURN count(r) AS c"
            ).result_set
            if rows[0][0]:
                edges[edge_type] = rows[0][0]
        return {"graph": self.graph_name, "nodes": nodes, "edges": edges,
                "total_nodes": sum(nodes.values()),
                "total_edges": sum(edges.values())}

    def claims_about(self, concept_name: str) -> list[dict]:
        rows = self.query(
            "MATCH (c:Claim)-[:ABOUT]->(k:Concept) "
            "WHERE toLower(k.name) = toLower($name) "
            "RETURN c.id, c.text, c.confidence ORDER BY c.confidence DESC",
            {"name": concept_name}).result_set
        return [{"id": r[0], "text": r[1], "confidence": r[2]} for r in rows]

    def supporting_claims(self, claim_id: str) -> list[dict]:
        rows = self.query(
            "MATCH (s:Claim)-[:SUPPORTS]->(c:Claim {id: $id}) "
            "RETURN s.id, s.text, s.confidence",
            {"id": claim_id}).result_set
        return [{"id": r[0], "text": r[1], "confidence": r[2]} for r in rows]

    def contradictions(self) -> list[dict]:
        rows = self.query(
            "MATCH (a:Claim)-[:CONTRADICTS]->(b:Claim) "
            "RETURN a.id, a.text, b.id, b.text").result_set
        return [{"a_id": r[0], "a_text": r[1], "b_id": r[2], "b_text": r[3]}
                for r in rows]

    def answer_question(self, question_id: str) -> dict:
        """Return answering claims plus the human-readable reasoning path."""
        qrows = self.query(
            "MATCH (q:Question {id: $id}) RETURN q.text",
            {"id": question_id}).result_set
        if not qrows:
            return {"question_id": question_id, "question": None,
                    "answers": [], "paths": []}
        question_text = qrows[0][0]
        rows = self.query(
            "MATCH path = (p:Paper)-[:STATES]->(c:Claim)-[:ANSWERS]->"
            "(q:Question {id: $id}) "
            "RETURN c.id, c.text, c.confidence, p.id, p.title",
            {"id": question_id}).result_set
        answers, paths = [], []
        for r in rows:
            answers.append({"claim_id": r[0], "text": r[1],
                            "confidence": r[2], "paper_id": r[3],
                            "paper_title": r[4]})
            paths.append(
                f"Paper[{r[4]}] -STATES-> Claim[{r[1]}] "
                f"-ANSWERS-> Question[{question_text}]")
        # Claims that answer without a known paper still count as answers.
        extra = self.query(
            "MATCH (c:Claim)-[:ANSWERS]->(q:Question {id: $id}) "
            "WHERE NOT ( (:Paper)-[:STATES]->(c) ) "
            "RETURN c.id, c.text, c.confidence",
            {"id": question_id}).result_set
        for r in extra:
            answers.append({"claim_id": r[0], "text": r[1],
                            "confidence": r[2], "paper_id": None,
                            "paper_title": None})
            paths.append(
                f"Claim[{r[1]}] -ANSWERS-> Question[{question_text}]")
        return {"question_id": question_id, "question": question_text,
                "answers": answers, "paths": paths}

    def support_chain(self, claim_id: str, max_depth: int = 5) -> list[str]:
        """Multi-hop SUPPORTS chain ending at a concept or root claim."""
        rows = self.query(
            "MATCH path = (start:Claim {id: $id})-[:SUPPORTS*1.."
            + str(int(max_depth)) + "]->(end) "
            "RETURN [n IN nodes(path) | coalesce(n.text, n.name, n.title)] "
            "AS labels",
            {"id": claim_id}).result_set
        chains = []
        for (labels,) in rows:
            chains.append(" -SUPPORTS-> ".join(str(x) for x in labels))
        return chains

    def cited_by(self, paper_id: str) -> list[dict]:
        rows = self.query(
            "MATCH (p:Paper)-[:CITES]->(cited:Paper {id: $id}) "
            "RETURN p.id, p.title",
            {"id": paper_id}).result_set
        return [{"id": r[0], "title": r[1]} for r in rows]
