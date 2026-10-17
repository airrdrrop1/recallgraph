# RecallGraph

**Agent memory that shows its work.** RecallGraph stores what an AI agent
learns in a **FalkorDB** graph — and every answer it gives comes with the
exact reasoning path it traversed to get there.

Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB),
targeting **Track 2 — Agent Memory and Coordination** (primary) and
**Track 1 — Agents That Act on Connected Data** (secondary).
Build window: 15–18 October 2026; the FalkorDB implementation in this
repository was written during the event, as the rules require.

## Why a graph — and why show the path?

Flat retrieval (chunk + embed) loses the relations between facts: you
cannot ask *why* an answer is believed, *what contradicts it*, or *which
source stated it*. RecallGraph keeps those relations as first-class
edges, so an answer is a traversal, not a guess:

1. **Question match** — the question is matched to a stored `Question` node.
2. **ANSWERS** — incoming `ANSWERS` edges lead to the answering claims.
3. **SUPPORTS (multi-hop)** — each claim's evidence chain is expanded,
   several hops deep.
4. **CONTRADICTS** — contested answers are flagged, never presented as settled.
5. **STATES citations** — every claim traces back to the `Paper` that stated it.

If no path exists, RecallGraph says **"No answer in memory yet"** and
shows the steps it tried — it never invents an answer the graph does
not contain.

## Two agents, one shared memory

- **Librarian** (write side) — ingests documents, reports which claims
  are genuinely new, and audits the memory (open contradictions,
  unanswered questions, strongest claims).
- **Scout** (read side) — answers questions through the reasoning engine
  and derives **suggested actions from the same reasoning path**: a
  contested answer → resolve the contradiction first; a cited paper →
  read/verify the source; a deep support chain → promote it into a note;
  no answer → ingest a source. It also drafts a brief of what is known,
  contested, and missing.

Both agents hold a handle on the *same* per-user FalkorDB graph, so a
document only the Librarian ever touched is immediately answerable by
the Scout — no re-teaching, no message bus. The test suite proves this
handoff explicitly.

## Memory model

One FalkorDB graph per user (`recallgraph_<user>`), which keeps
memories isolated (also test-verified).

| Nodes | Edges |
|---|---|
| `Paper {id, title, authors, year, source}` | `(Claim)-[:SUPPORTS]->(Claim\|Concept)` |
| `Concept {id, name, description}` | `(Claim)-[:CONTRADICTS]->(Claim)` |
| `Claim {id, text, confidence}` | `(Claim)-[:ANSWERS]->(Question)` |
| `Question {id, text}` | `(Paper)-[:CITES]->(Paper)` |
| | structural: `(Paper)-[:STATES]->(Claim)`, `(Claim)-[:ABOUT]->(Concept)`, `(Question)-[:ASKS_ABOUT]->(Concept)` |

The reasoning engine is deterministic (concept/keyword matching, no
LLM), so the demo and the tests are reproducible. Document ingestion
uses a deterministic marked-up-text extractor (`PAPER:` / `CONCEPT:` /
`CLAIM [conf]:` / `QUESTION:` lines) behind the same document-dict shape
an LLM extractor can later produce.

## Repository layout

```
app.py               # Day-3 web UI (stdlib http.server): graph view,
                     # ingest form, ask + reasoning-path panel, Scout brief
graphmem/
  store.py           # FalkorDB wrapper — all Cypher lives here
  extract.py         # deterministic document extractor
  reasoning.py       # ReasoningEngine: question -> traversal -> answer + path
  agents.py          # Librarian (write) + Scout (read/act)
  demo_data.py       # 3 sample papers: 17 nodes / 30 edges
scripts/
  ingest_demo.py     # seed the demo graph, run the basic queries
  ask_demo.py        # terminal demo: questions, reasoning paths, brief
tests/               # 27 integration tests (days 1-3), live FalkorDB
demo/                # demo video + its production script
DEMO-SCRIPT-day3.md  # the 5-beat demo narration script (EN, ±2:30)
```

## Setup (local — verified end-to-end 17 Oct 2026)

RecallGraph runs against a local FalkorDB instance (Redis protocol,
`127.0.0.1:6379`, browser UI on `:3000`).

**Generic (Docker):**

```bash
docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

**This workspace (rootful Podman, custom storage root + crun):**

```bash
P="podman --root /home/hatch/podman-storage --runroot /home/hatch/podman-runroot --storage-driver vfs --runtime /home/hatch/bin/crun"
$P ps -a                       # if falkordb-prep is not Up:
$P start falkordb-prep
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000   # expect 200
```

**App:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Smoke test — expect [[1]]
.venv/bin/python -c "from falkordb import FalkorDB; print(FalkorDB(host='127.0.0.1',port=6379).select_graph('kick').query('RETURN 1').result_set)"

# Seed the demo graph (3 papers -> 17 nodes / 30 edges)
.venv/bin/python scripts/ingest_demo.py --reset

# Tests — 27 integration tests against the live instance
# (dedicated graphs, self-cleaning)
.venv/bin/python -m pytest tests/ -v
```

Environment overrides: `FALKORDB_HOST`, `FALKORDB_PORT`.

## Run the demo

**Web UI (recommended):**

```bash
.venv/bin/python app.py --port 8765    # http://localhost:8765
```

Ask *"Why should an AI agent store memory in a graph?"* — you get the
answer (confidence 0.8), the 5-step reasoning path, the citation
(*Limits of Flat Retrieval for Long-lived Agents*) and 2 suggested
actions. Try *"Tell me about Multi-hop Reasoning"* (concept fallback),
*"What is the capital of France?"* (honest gap), then ingest the Zebra
sample in the Ingest panel and ask about it — the Scout answers from
memory only the Librarian wrote. Restart the FalkorDB container and
reload: the graph is still there.

**Terminal (same outputs, no browser):**

```bash
.venv/bin/python scripts/ask_demo.py
.venv/bin/python scripts/ask_demo.py "Tell me about Multi-hop Reasoning"
```

**Video:** `demo/recallgraph-demo-day3.mp4` (±2:30, English narration,
following `DEMO-SCRIPT-day3.md`) — every beat is rendered from live
output of the pipeline/UI APIs above, including a real FalkorDB
container restart proving persistence. Production script:
`demo/make_demo_video.py`.

## Build log

- **Day 1 (15 Oct)** — FalkorDB store + schema, demo ingest, basic
  queries (claims-by-concept, answer-with-path, contradictions,
  multi-hop support chains, citations), per-user isolation, persistence
  across a container restart. 8 tests.
- **Day 2 (16 Oct)** — the brain: `ReasoningEngine` (stored-Question →
  ANSWERS → multi-hop SUPPORTS → CONTRADICTS → STATES citations, with
  layered honest fallbacks) and Librarian/Scout on one shared graph.
  18 tests.
- **Day 3 (17 Oct)** — the face: web UI (graph view + ingest + ask +
  reasoning-path panel + Scout brief), `graph_snapshot()` API, demo
  video, final README. **27/27 tests passing.**

## License

MIT — see `LICENSE`.
