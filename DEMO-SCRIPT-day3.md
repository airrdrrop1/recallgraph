# RecallGraph — Demo Video Script (Day-3 draft, prepared 16 Oct 2026)

Target: <3 minutes, English narration, screen-recorded from the Day-3 UI.
Every beat below uses output already verified on Day-2 (18/18 tests, `scripts/ask_demo.py`
on the demo graph: 17 nodes / 30 edges, 3 papers, 7 claims) — no invented features.
If Day-3 UI wording differs, keep the beats, adjust the on-screen text only.

## Shot list & narration (total ≈ 2:30)

**0:00–0:15 — Hook (graph view, full screen)**
VO: "AI agents forget. RecallGraph gives them a memory they can explain —
a FalkorDB graph where every answer shows the path it took."
On screen: demo graph (17 nodes / 30 edges). Title card: RecallGraph — Graph Hacks, Track 2 + Track 1.

**0:15–0:50 — Beat 1: a real answer, with its reasoning path**
Action: ask "Why should an AI agent store memory in a graph?"
VO: "Ask a question, and RecallGraph doesn't just answer — it walks the graph:
question, answer edge, supporting claims, even a two-hop evidence chain,
then checks for contradictions and cites the paper."
On screen: answer claim (confidence 0.8), the 5-step reasoning path panel,
citation "Limits of Flat Retrieval for Long-lived Agents", 2 suggested actions.

**0:50–1:15 — Beat 2: fallback that still works**
Action: ask "Tell me about Multi-hop Reasoning"
VO: "No stored question matches — so it falls back to concept traversal
and still finds the claim, with its citation. Nothing is faked; the path shows the detour."
On screen: concept-fallback path → claim-multihop-path (0.78) + citation.

**1:15–1:40 — Beat 3: honesty + contradiction**
Action: ask "What is the capital of France?"
VO: "And when the memory doesn't know, it says so — no hallucinated answer,
just the steps it tried and a high-priority action: ingest a source."
On screen: "No answer in memory yet" (conf 0.0) + ingest action.
Then show Scout brief line: "1 question(s) unanswered, 1 contradiction(s) open"
(claim-flat-is-enough vs claim-graph-beats-flat).

**1:40–2:10 — Beat 4: two agents, one memory (the Day-2 handoff test)**
Action: Librarian ingests a new document ("Zebra Indexing"); Scout answers a question about it.
VO: "Two agents share one graph. The Librarian writes; the Scout reads and acts.
A document only the Librarian ever touched — the Scout can already answer from it."
On screen: ingest report (new claims), then Scout answer + suggested actions from the same path.

**2:10–2:30 — Close: persistence**
Action: restart the FalkorDB container, reload UI, graph still there.
VO: "Restart the database — the memory survives. RecallGraph: agent memory
that shows its work. Built on FalkorDB for Graph Hacks."
On screen: graph reloads intact; repo URL + Track 2 / Track 1 card.

## Recording notes
- Cold-start the UI before recording so Beat order matches the script.
- Keep each reasoning-path panel on screen ≥4 seconds (judges read paths, not narration).
- If UI is not ready by recording time, same script works over `scripts/ask_demo.py`
  terminal output — beats and verified outputs are identical.
