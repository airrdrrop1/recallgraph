#!/usr/bin/env python3
"""Ingest the sample documents into FalkorDB and run the day-1 basic queries.

Usage:
  .venv/bin/python scripts/ingest_demo.py [--user demo] [--reset]

Requires a running FalkorDB on 127.0.0.1:6379 (see README for the Podman
command used in this workspace).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graphmem.demo_data import DOCUMENTS
from graphmem.store import RecallGraphStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="demo")
    parser.add_argument("--reset", action="store_true",
                        help="clear the user's graph before ingesting")
    args = parser.parse_args()

    store = RecallGraphStore(user=args.user)
    print(f"ping: {store.ping()}  graph: {store.graph_name}")
    store.ensure_schema()
    if args.reset:
        store.clear()
        print("graph cleared")

    totals = {"papers": 0, "concepts": 0, "claims": 0, "questions": 0,
              "edges": 0}
    for doc in DOCUMENTS:
        counts = store.ingest_document(doc)
        for key in totals:
            totals[key] += counts[key]
    print("ingested:", json.dumps(totals))

    stats = store.stats()
    print("stats:", json.dumps(stats, indent=2))

    print("\nQ: Why should an AI agent store memory in a graph?")
    answer = store.answer_question("q-why-graph")
    print(json.dumps(answer, indent=2))

    print("\nClaims about 'Graph Memory':")
    for claim in store.claims_about("Graph Memory"):
        print(f"  [{claim['confidence']}] {claim['text']}")

    print("\nContradictions:")
    for pair in store.contradictions():
        print(f"  {pair['a_id']} CONTRADICTS {pair['b_id']}")

    print("\nSupport chain for claim-answer-why-graph:")
    for chain in store.support_chain("claim-answer-why-graph"):
        print(f"  {chain}")

    print("\nPapers citing paper-graph-memory-2025:")
    for paper in store.cited_by("paper-graph-memory-2025"):
        print(f"  {paper['id']}: {paper['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
