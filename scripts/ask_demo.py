#!/usr/bin/env python3
"""Day-2 demo: ask RecallGraph questions and print the reasoning path.

Usage:
  .venv/bin/python scripts/ask_demo.py [--user demo] [question ...]

With no question argument it runs the canned demo: the two stored
questions, one concept-fallback question, one unknown question (honest
gap), plus the Scout brief. Ingest first: scripts/ingest_demo.py --reset
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graphmem.agents import Librarian, Scout
from graphmem.reasoning import ReasoningEngine
from graphmem.store import RecallGraphStore

DEMO_QUESTIONS = [
    "Why should an AI agent store memory in a graph?",
    "How can two agents share the same memory?",
    "What does the graph say about Graph Memory?",
    "What is the capital of France?",  # not in memory — must say so
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="demo")
    parser.add_argument("question", nargs="*")
    args = parser.parse_args()

    store = RecallGraphStore(user=args.user)
    print(f"ping: {store.ping()}  graph: {store.graph_name}")
    scout = Scout(store)
    engine = ReasoningEngine(store)

    questions = [" ".join(args.question)] if args.question else DEMO_QUESTIONS
    for q in questions:
        result = scout.answer_and_act(q)
        print("\n" + "=" * 72)
        print(engine.render_reasoning_path(result))
        print("Suggested actions:")
        for act in result["suggested_actions"]:
            print(f"  [{act['priority']}] {act['action']} — {act['reason']}")

    if not args.question:
        print("\n" + "=" * 72)
        print("SCOUT BRIEF (from the same shared graph, no re-teaching):")
        brief = scout.brief()
        print(" ", brief["summary"])
        for act in brief["suggested_actions"]:
            print(f"  [{act['priority']}] {act['action']}")
        print("\nLIBRARIAN AUDIT:")
        audit = Librarian(store).audit()
        print(f"  contradictions: {len(audit['contradictions'])}, "
              f"unanswered: {len(audit['unanswered_questions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
