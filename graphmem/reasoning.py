"""Day-2 reasoning engine — question -> traversal -> answer + visible path.

This is RecallGraph's differentiator: an answer is never a bare string.
Every answer carries an ordered list of *reasoning steps*, each step naming
the exact graph traversal that produced it (node -> relation -> node), the
supporting evidence found along SUPPORTS edges, any CONTRADICTS warning,
and the Paper citations reached via STATES / CITES.

The engine is deterministic (keyword / concept matching, no LLM), so the
demo and the tests are reproducible. Matching strategy, in order:

1. Exact / high-overlap match against a stored Question node, then follow
   its incoming ANSWERS edges (the day-1 path, now explained step by step).
2. Concept match: concepts whose name appears in (or overlaps) the query,
   then claims ABOUT those concepts, ranked by confidence.
3. Keyword fallback over claim text.

If nothing matches, the engine says so explicitly and still returns the
steps it took — it never invents an answer the graph does not contain.
"""
from __future__ import annotations

import re

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "should", "would", "could", "can", "why", "how", "what", "when",
    "where", "who", "which", "for", "of", "in", "on", "to", "and", "or",
    "it", "its", "an", "agent", "agents",  # 'agent' is too generic here
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(t) > 2 and t not in STOPWORDS}


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


class ReasoningEngine:
    """Ask questions against one user's RecallGraph store."""

    def __init__(self, store):
        self.store = store

    # -- matching helpers --------------------------------------------------
    def _match_question(self, query_text: str):
        q_tokens = _tokens(query_text)
        best, best_score = None, 0.0
        for q in self.store.all_questions():
            score = _overlap(q_tokens, _tokens(q["text"]))
            # Exact normalised text match always wins.
            if query_text.strip().lower() == q["text"].strip().lower():
                score = 1.0
            if score > best_score:
                best, best_score = q, score
        if best and best_score >= 0.34:
            return best, best_score
        return None, best_score

    def _match_concepts(self, query_text: str) -> list[dict]:
        q_tokens = _tokens(query_text)
        lowered = query_text.lower()
        matched = []
        for concept in self.store.all_concepts():
            name_tokens = _tokens(concept["name"])
            # Precise on purpose: the full name is mentioned, or every
            # token of the name appears in the query. A single shared
            # generic word (e.g. 'memory') must not drag a concept in.
            if concept["name"].lower() in lowered or (
                    name_tokens and name_tokens <= q_tokens):
                matched.append(concept)
        return matched

    # -- evidence expansion --------------------------------------------------
    def _expand_claim(self, claim: dict) -> dict:
        """Attach support, contradiction, concept and citation context."""
        claim_id = claim["id"]
        supporters = self.store.supporting_claims(claim_id)
        chains = self.store.support_chain_structured(claim_id)
        contradictions = self.store.contradicting_claims(claim_id)
        paper = self.store.paper_for_claim(claim_id)
        concepts = self.store.concepts_for_claim(claim_id)
        return {
            **claim,
            "supporters": supporters,
            "support_chains": chains,
            "contradictions": contradictions,
            "paper": paper,
            "concepts": concepts,
        }

    # -- main entry point ----------------------------------------------------
    def ask(self, query_text: str) -> dict:
        steps: list[dict] = []

        def step(description: str, traversal: str, found: list[str]):
            steps.append({
                "step": len(steps) + 1,
                "description": description,
                "traversal": traversal,
                "found": found,
            })

        query_text = (query_text or "").strip()
        if not query_text:
            return {"query": query_text, "matched_question": None,
                    "answers": [], "reasoning_steps": steps,
                    "confidence": 0.0, "citations": [],
                    "contradiction_warnings": [],
                    "answer_text": "Empty question — nothing to traverse."}

        # Step 1 — try to land on a stored Question node.
        matched_q, q_score = self._match_question(query_text)
        if matched_q:
            step(f"Matched the question to stored Question node "
                 f"'{matched_q['text']}' (overlap {q_score:.2f}).",
                 "Question[text match]", [matched_q["id"]])
        else:
            step("No stored Question matched closely enough; falling back "
                 "to concept / keyword traversal.",
                 "Question[text match]", [])

        answers: list[dict] = []
        citations: dict[str, dict] = {}
        warnings: list[dict] = []

        if matched_q:
            # Step 2 — follow ANSWERS edges (the core multi-hop move).
            result = self.store.answer_question(matched_q["id"])
            step("Followed incoming ANSWERS edges to the claims that "
                 "answer this question.",
                 "(Claim)-[:ANSWERS]->(Question)",
                 [a["claim_id"] for a in result["answers"]])
            for raw in result["answers"]:
                claim = {"id": raw["claim_id"], "text": raw["text"],
                         "confidence": raw["confidence"]}
                answers.append(self._expand_claim(claim))
            if not answers:
                step("The matched Question has no ANSWERS edge yet — "
                     "falling back to concept traversal instead of "
                     "stopping at the gap.",
                     "(Claim)-[:ANSWERS]->(Question)", [])
        if not answers:
            # Fallback — concept traversal (no Question match, or the
            # matched Question is stored but still unanswered).
            concepts = self._match_concepts(query_text)
            step("Matched concepts mentioned by the question.",
                 "(Question)-[:ASKS_ABOUT]->(Concept) / name match",
                 [c["id"] for c in concepts])
            seen: set[str] = set()
            for concept in concepts:
                for claim in self.store.claims_about(concept["name"]):
                    if claim["id"] not in seen:
                        seen.add(claim["id"])
                        answers.append(self._expand_claim(claim))
            answers.sort(key=lambda c: -(c["confidence"] or 0))
            step("Collected claims ABOUT the matched concepts, ranked "
                 "by confidence.",
                 "(Claim)-[:ABOUT]->(Concept)",
                 [a["id"] for a in answers])
            if not answers:
                # Keyword fallback over claim text.
                q_tokens = _tokens(query_text)
                for claim in self.store.strongest_claims(limit=50):
                    if _overlap(q_tokens, _tokens(claim["text"])) >= 0.34:
                        answers.append(self._expand_claim(claim))
                if answers:
                    step("Keyword fallback matched claim text directly.",
                         "Claim[text keyword match]",
                         [a["id"] for a in answers])

        # Step 3 — expand SUPPORTS (evidence) for every answer.
        support_found: list[str] = []
        for ans in answers:
            support_found.extend(s["id"] for s in ans["supporters"])
            for chain in ans["support_chains"]:
                support_found.extend(n["id"] for n in chain[1:]
                                     if n.get("id"))
        if answers:
            step("Expanded SUPPORTS edges from each answering claim to "
                 "show the evidence underneath it (multi-hop).",
                 "(Claim)-[:SUPPORTS]->(Claim|Concept)",
                 sorted(set(support_found)))

        # Step 4 — contradiction check (a graph-only superpower).
        for ans in answers:
            for contra in ans["contradictions"]:
                warnings.append({"answer_claim": ans["id"],
                                 "contradicting_claim": contra["id"],
                                 "text": contra["text"]})
        if answers:
            step("Checked CONTRADICTS edges so a contested answer is "
                 "never presented as settled.",
                 "(Claim)-[:CONTRADICTS]->(Claim)",
                 [w["contradicting_claim"] for w in warnings])

        # Step 5 — citations via STATES (claim -> paper that stated it).
        for ans in answers:
            if ans.get("paper"):
                citations[ans["paper"]["id"]] = ans["paper"]
        if answers:
            step("Traced each answering claim back to the Paper that "
                 "stated it, for citation.",
                 "(Paper)-[:STATES]->(Claim)",
                 sorted(citations))

        confidence = (max((a["confidence"] or 0) for a in answers)
                      if answers else 0.0)
        if warnings:
            # A live contradiction caps how confidently we present this.
            confidence = round(min(confidence, 0.6), 3)

        if answers:
            lead = answers[0]
            answer_text = lead["text"]
            if len(answers) > 1:
                answer_text += (f" (+{len(answers) - 1} further claim(s) "
                                f"from the same traversal)")
            if warnings:
                answer_text += (" ⚠ This answer is contested in the graph "
                                "by a CONTRADICTS edge — see warnings.")
        elif matched_q:
            answer_text = ("This question is stored in memory but no "
                           "claim ANSWERS it yet. Ingest a source that "
                           "answers it, then re-ask.")
        else:
            answer_text = ("No answer in memory yet: no Question, Concept "
                           "or Claim in the graph matches this query. "
                           "Ingest a source first, or rephrase using a "
                           "stored concept name.")
            step("Traversal finished with no matching claims — reporting "
                 "the gap instead of inventing an answer.",
                 "(no path)", [])

        return {
            "query": query_text,
            "matched_question": matched_q,
            "answers": answers,
            "reasoning_steps": steps,
            "confidence": confidence,
            "citations": list(citations.values()),
            "contradiction_warnings": warnings,
            "answer_text": answer_text,
        }

    # -- claim explanation ---------------------------------------------------
    def explain_claim(self, claim_id: str) -> dict | None:
        """Full explanation bundle for one claim (for the UI panel)."""
        claim = self.store.get_claim(claim_id)
        if claim is None:
            return None
        expanded = self._expand_claim(claim)
        readable_paths = self.store.support_chain(claim_id)
        return {
            "claim": expanded,
            "readable_support_paths": readable_paths,
            "summary": (
                f"Claim '{claim['text']}' "
                f"(confidence {claim['confidence']}) is stated by "
                f"{expanded['paper']['title'] if expanded['paper'] else 'no known paper'}, "
                f"supported by {len(expanded['supporters'])} claim(s), "
                f"contested by {len(expanded['contradictions'])} claim(s), "
                f"about: {', '.join(c['name'] for c in expanded['concepts']) or '—'}."),
        }

    # -- rendering -----------------------------------------------------------
    @staticmethod
    def render_reasoning_path(result: dict) -> str:
        """Plain-text step-by-step path — exactly what the UI panel shows."""
        lines = [f"Q: {result['query']}", f"A: {result['answer_text']}",
                 "", "Reasoning path:"]
        for s in result["reasoning_steps"]:
            found = ", ".join(s["found"]) if s["found"] else "—"
            lines.append(f"  {s['step']}. {s['description']}")
            lines.append(f"     traversal: {s['traversal']}  →  {found}")
        for ans in result.get("answers", []):
            for chain in ans.get("support_chains", []):
                labels = " -SUPPORTS-> ".join(
                    str(n.get("label") or n.get("id")) for n in chain)
                lines.append(f"  support: {labels}")
        if result.get("citations"):
            lines.append("Citations: " + "; ".join(
                f"{c['title']} ({c['id']})" for c in result["citations"]))
        if result.get("contradiction_warnings"):
            lines.append("Contradiction warnings: " + "; ".join(
                w["contradicting_claim"] for w in
                result["contradiction_warnings"]))
        lines.append(f"Confidence: {result['confidence']}")
        return "\n".join(lines)
