# Submission draft — Graph Hacks (WeMakeDevs x FalkorDB)

Deadline: Monday 19 October 2026, 01:29 WIB. Internal target: submit by 18 October, 20:00 WIB.

- **Project:** RecallGraph
- **Tracks:** Track 2 — Agent Memory and Coordination (primary); Track 1 — Agents That Act on Connected Data (secondary)
- **Repo:** (GitHub public URL — fill in when published, 18 Oct)
- **Demo:** video `demo/recallgraph-demo-day3.mp4` (±2:30, in repo) + local setup instructions in README (no live deployment — FalkorDB runs locally; the video shows the real UI/pipeline incl. a container restart)

## Description

- **What it does:** RecallGraph is an AI research assistant that stores
  everything it learns in a FalkorDB graph (Paper / Concept / Claim /
  Question) and answers questions by graph traversal, always showing
  the step-by-step reasoning path behind the answer.
- **How FalkorDB shapes what the agent does (central, not a side store):**
  the graph *is* the memory and the reasoning substrate. Answers exist
  only if a traversal path exists (Question → ANSWERS → multi-hop
  SUPPORTS → CONTRADICTS check → STATES citation); with no path, the
  agent reports the gap instead of answering. Suggested actions are
  derived from the traversed edges themselves.
- **Memory model:** one graph per user (isolation test-verified);
  semantic memory as Claim/Concept nodes with confidence, provenance
  via Paper/STATES, contested knowledge kept explicit via CONTRADICTS
  instead of being overwritten; persistence across restarts verified.
- **Reasoning-path explanation feature:** every answer returns an
  ordered list of reasoning steps naming the exact traversal per step
  (node → relation → node), the supporting multi-hop chains, citations,
  and contradiction warnings — rendered in the web UI's reasoning-path
  panel and in the terminal demo.
- **Two-agent coordination (Librarian / Scout handoff):** the Librarian
  writes (ingest, dedupe report, audit) and the Scout reads/acts
  (answer, path-derived actions, brief) over one shared per-user graph;
  the handoff is proven by a test where Scout answers about a document
  only the Librarian ingested.

## Checklist before submitting

- [x] Demo works end-to-end from a cold start (persistence across restart shown, day-1 test + day-3 video)
- [x] Tests: 27/27 integration tests passing against live local FalkorDB (17 Oct)
- [x] README setup complete (Podman workspace + generic Docker), architecture + demo instructions
- [x] Demo video <3 min recorded from real pipeline/UI output (day-3, 17 Oct)
- [ ] Repo public, LICENSE visible (18 Oct)
- [ ] Blog post draft for the side prize (AirPods — best project blog post) — optional, if time remains 18 Oct
