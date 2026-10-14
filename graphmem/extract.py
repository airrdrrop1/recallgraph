"""Deterministic extractor — day-1 fallback that never depends on an LLM.

Input format (plain text, one marker per line)::

    PAPER: <title> | <authors> | <year>
    CONCEPT: <name> — <description>
    CLAIM [0.85]: <text> ABOUT: <concept name>
    QUESTION: <text> ABOUT: <concept name>

Unmarked lines are ignored. Ids are slugified from the visible text, so the
same input always produces the same document dict for store.ingest_document.
An LLM extractor can replace this module later behind the same dict shape.
"""
from __future__ import annotations

import re


def slugify(text: str, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return f"{prefix}-{slug[:60].strip('-')}"


def extract_document(text: str, source: str = "text") -> dict:
    doc: dict = {"concepts": [], "claims": [], "questions": [], "cites": []}
    concept_ids: dict[str, str] = {}

    def concept_id_for(name: str) -> str:
        key = name.strip().lower()
        if key not in concept_ids:
            concept_ids[key] = slugify(name, "concept")
        return concept_ids[key]

    paper_match = re.search(r"^PAPER:\s*(.+)$", text, re.MULTILINE)
    if paper_match:
        parts = [p.strip() for p in paper_match.group(1).split("|")]
        title = parts[0]
        year = None
        if len(parts) > 2 and parts[2].isdigit():
            year = int(parts[2])
        doc["paper"] = {
            "id": slugify(title, "paper"), "title": title,
            "authors": parts[1] if len(parts) > 1 else "",
            "year": year, "source": source,
        }

    for m in re.finditer(r"^CONCEPT:\s*([^—]+?)(?:\s*—\s*(.*))?$", text,
                         re.MULTILINE):
        name = m.group(1).strip()
        cid = concept_id_for(name)
        doc["concepts"].append({"id": cid, "name": name,
                                "description": (m.group(2) or "").strip()})

    for m in re.finditer(
            r"^CLAIM(?:\s*\[([0-9.]+)\])?:\s*(.+?)(?:\s+ABOUT:\s*(.+))?$",
            text, re.MULTILINE):
        body = m.group(2).strip()
        claim = {"id": slugify(body, "claim"), "text": body,
                 "confidence": float(m.group(1)) if m.group(1) else 0.5,
                 "about": []}
        if m.group(3):
            for name in m.group(3).split(","):
                name = name.strip()
                if name:
                    cid = concept_id_for(name)
                    claim["about"].append(cid)
                    if all(c["id"] != cid for c in doc["concepts"]):
                        doc["concepts"].append(
                            {"id": cid, "name": name, "description": ""})
        doc["claims"].append(claim)

    for m in re.finditer(
            r"^QUESTION:\s*(.+?)(?:\s+ABOUT:\s*(.+))?$", text, re.MULTILINE):
        body = m.group(1).strip()
        question = {"id": slugify(body, "q"), "text": body, "asks_about": []}
        if m.group(2):
            for name in m.group(2).split(","):
                name = name.strip()
                if name:
                    cid = concept_id_for(name)
                    question["asks_about"].append(cid)
                    if all(c["id"] != cid for c in doc["concepts"]):
                        doc["concepts"].append(
                            {"id": cid, "name": name, "description": ""})
        doc["questions"].append(question)

    return doc
