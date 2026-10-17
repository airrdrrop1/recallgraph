#!/usr/bin/env python3
"""Capture LIVE RecallGraph output as JSON for the demo-video renderer.

Run with the project venv python. Every number/text the video shows comes
from these captures — the renderer (make_demo_video.py) invents nothing.

Subcommands:
  seed                      reset the demo graph to the 3 sample papers
  capture <out.json>        snapshot + 3 demo asks + Scout brief
  zebra <out.json>          Librarian ingests the Zebra doc, Scout answers
  stats <out.json>          current stats only (persistence before/after)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graphmem.agents import Librarian, Scout  # noqa: E402
from graphmem.demo_data import DOCUMENTS  # noqa: E402
from graphmem.store import RecallGraphStore  # noqa: E402

ZEBRA_TEXT = (
    "PAPER: Handoff Probe Notes | Tester | 2026\n"
    "CONCEPT: Zebra Indexing — Indexing by stripes\n"
    "CLAIM [0.66]: Zebra indexing speeds recall for striped data "
    "ABOUT: Zebra Indexing\n"
    "QUESTION: Does zebra indexing help? ABOUT: Zebra Indexing\n"
)

QUESTIONS = [
    "Why should an AI agent store memory in a graph?",
    "Tell me about Multi-hop Reasoning",
    "What is the capital of France?",
]


def _plain(obj):
    return json.loads(json.dumps(obj, default=str))


def main() -> int:
    cmd = sys.argv[1]
    store = RecallGraphStore(user="demo")
    assert store.ping(), "FalkorDB unreachable"

    if cmd == "seed":
        store.ensure_schema()
        store.clear()
        for doc in DOCUMENTS:
            store.ingest_document(doc)
        print(json.dumps(store.stats()))
    elif cmd == "capture":
        scout = Scout(store)
        data = {
            "snapshot": store.graph_snapshot(),
            "stats": store.stats(),
            "asks": [_plain(scout.answer_and_act(q)) for q in QUESTIONS],
            "brief": _plain(scout.brief()),
        }
        Path(sys.argv[2]).write_text(json.dumps(data, indent=1))
        print(f"captured: {data['stats']['total_nodes']} nodes / "
              f"{data['stats']['total_edges']} edges")
    elif cmd == "zebra":
        librarian = Librarian(store)
        report = librarian.ingest_text(ZEBRA_TEXT, source="demo-video")
        scout = Scout(store)
        data = {
            "ingest": {k: v for k, v in _plain(report).items()
                       if k != "document"},
            "answer": _plain(scout.answer_and_act(
                "Tell me about Zebra Indexing")),
            "stats": store.stats(),
        }
        Path(sys.argv[2]).write_text(json.dumps(data, indent=1))
        print(f"zebra: nodes {report['nodes_before']} -> "
              f"{report['nodes_after']}")
    elif cmd == "stats":
        Path(sys.argv[2]).write_text(json.dumps(
            {"stats": store.stats(), "ping": store.ping()}, indent=1))
        print(json.dumps(store.stats()))
    else:
        print(f"unknown subcommand: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
