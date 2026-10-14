# RecallGraph

An AI research assistant that remembers everything in a graph — and shows its reasoning path.

RecallGraph stores what it learns (people, projects, topics, decisions, tasks, sources) in a **FalkorDB** graph, one graph per user. When asked a question, it answers from a multi-hop graph traversal and shows the exact path it used, then turns that path into suggested actions.

Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB), targeting Track 2 (Agent Memory and Coordination) and Track 1 (Agents That Act on Connected Data).

> Build window: 15–18 October 2026. The FalkorDB implementation in this repository is written during the event, as the rules require. This README, the license, and the folder structure are general preparation only.

## What it does

1. **Ingest** — paste notes, chat excerpts, or small documents. Entities and relations are extracted and written to FalkorDB. Facts that change are linked with a timestamped `SUPERSEDES` relation instead of being deleted.
2. **Remember** — every session becomes an `Episode` node linked to the entities it touched, so memory persists across restarts.
3. **Recall & act** — questions are answered from a relevant subgraph only. Every answer includes the human-readable reasoning path (node → relation → node). Two agents share one graph: a **Librarian** that writes and tidies memory, and a **Scout** that reads it and drafts a brief of suggested actions.

## Planned structure

```
app.py            # single-page web UI (stdlib http.server): ingest, ask, reasoning-path panel
graphmem/
  store.py        # FalkorDB client wrapper — all Cypher lives here
  extract.py      # entity/relation extraction (LLM with deterministic fallback)
  agents.py       # Librarian (write) + Scout (read/brief)
  demo_data.py    # fictional mini-company data for the demo
tests/            # persistence across restart, multi-hop recall, supersede, per-user isolation
```

## Setup (local, verified 15 Oct 2026)

RecallGraph runs against a local FalkorDB instance (Redis protocol,
`127.0.0.1:6379`, browser UI on `:3000`). In this workspace the instance
runs under rootful Podman with a custom storage root:

```bash
# 1. Start (or check) FalkorDB
P="podman --root /home/hatch/podman-storage --runroot /home/hatch/podman-runroot --storage-driver vfs --runtime /home/hatch/bin/crun"
$P ps -a                       # if falkordb-prep is not Up:
$P start falkordb-prep
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000   # expect 200

# (generic equivalent: docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest)

# 2. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Smoke test — expect [[1]]
.venv/bin/python -c "from falkordb import FalkorDB; print(FalkorDB(host='127.0.0.1',port=6379).select_graph('kick').query('RETURN 1').result_set)"

# 4. Ingest the sample documents and run the basic queries
.venv/bin/python scripts/ingest_demo.py --reset

# 5. Tests (integration, against the live instance; dedicated graph, self-cleaning)
.venv/bin/python -m pytest tests/ -v
```

Day-1 status: schema (Paper / Concept / Claim / Question; SUPPORTS /
CONTRADICTS / ANSWERS / CITES plus structural STATES / ABOUT / ASKS_ABOUT),
ingest of 3 sample papers (17 nodes, 30 edges), basic queries
(claims-by-concept, answer-with-reasoning-path, contradictions, multi-hop
support chains, citations), per-user graph isolation, and persistence
across a container restart are all implemented and test-verified.
A demo video link will be added before submission (deadline 19 October
2026, 01:29 WIB).

## License

MIT — see `LICENSE`.
