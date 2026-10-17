#!/usr/bin/env python3
"""RecallGraph — single-page web UI (Python stdlib only).

Run (FalkorDB must be up on 127.0.0.1:6379, see README):

    .venv/bin/python scripts/ingest_demo.py --reset   # seed the demo graph
    .venv/bin/python app.py --port 8765               # http://localhost:8765

The page is the Day-3 demo surface for the Day-2 brain:

* **Graph view** — every node/edge of the user's FalkorDB graph, drawn as
  SVG from ``GET /api/graph`` (``RecallGraphStore.graph_snapshot``).
* **Ingest** — paste a marked-up document (see ``graphmem/extract.py``);
  the Librarian writes it to the shared graph (``POST /api/ingest``).
* **Ask** — a question goes through Scout/ReasoningEngine
  (``POST /api/ask``); the answer card shows the answer, its confidence,
  citations and contradiction warnings, the **step-by-step reasoning
  path**, and the suggested actions derived from that same path.
* **Scout brief** — memory health from traversal only (``GET /api/brief``).

No framework, no build step: ``http.server`` + vanilla JS, so the demo
runs anywhere the FalkorDB instance runs.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphmem.agents import Librarian, Scout  # noqa: E402
from graphmem.demo_data import DOCUMENTS  # noqa: E402
from graphmem.reasoning import ReasoningEngine  # noqa: E402
from graphmem.store import RecallGraphStore  # noqa: E402


class AppState:
    """One store (one per-user graph) shared by all request handlers."""

    def __init__(self, user: str = "demo"):
        self.store = RecallGraphStore(user=user)
        self.scout = Scout(self.store)
        self.librarian = Librarian(self.store)
        self.lock = threading.Lock()

    def seed_demo(self) -> dict:
        with self.lock:
            self.store.ensure_schema()
            self.store.clear()
            for doc in DOCUMENTS:
                self.store.ingest_document(doc)
            return self.store.stats()


def make_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RecallGraph/0.3"
        protocol_version = "HTTP/1.1"

        # -- plumbing ------------------------------------------------------
        def log_message(self, fmt, *args):  # quieter console
            sys.stderr.write("[ui] %s\n" % (fmt % args))

        def _send(self, code: int, body: bytes, content_type: str):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload):
            self._send(code, json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return {}

        # -- routes ----------------------------------------------------------
        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/":
                    self._send(200, INDEX_HTML.encode("utf-8"),
                               "text/html; charset=utf-8")
                elif path == "/api/stats":
                    with state.lock:
                        self._json(200, {"ok": True, "stats": state.store.stats(),
                                         "ping": state.store.ping()})
                elif path == "/api/graph":
                    with state.lock:
                        self._json(200, {"ok": True,
                                         "snapshot": state.store.graph_snapshot()})
                elif path == "/api/brief":
                    with state.lock:
                        brief = state.scout.brief()
                        audit = state.librarian.audit()
                    self._json(200, {"ok": True, "brief": brief,
                                     "audit_counts": {
                                         "contradictions": len(audit["contradictions"]),
                                         "unanswered": len(audit["unanswered_questions"])}})
                else:
                    self._json(404, {"ok": False, "error": "not found"})
            except Exception as exc:  # FalkorDB down etc. — say so honestly
                self._json(503, {"ok": False,
                                 "error": f"backend unavailable: {exc}"})

        def do_POST(self):
            path = urlparse(self.path).path
            payload = self._read_json()
            try:
                if path == "/api/ask":
                    question = str(payload.get("question") or "").strip()
                    if not question:
                        return self._json(400, {"ok": False,
                                                "error": "question is empty"})
                    with state.lock:
                        result = state.scout.answer_and_act(question)
                    result = dict(result)
                    result["reasoning_text"] = \
                        ReasoningEngine.render_reasoning_path(result)
                    self._json(200, {"ok": True, "result": result})
                elif path == "/api/ingest":
                    text = str(payload.get("text") or "")
                    if not text.strip():
                        return self._json(400, {"ok": False,
                                                "error": "text is empty"})
                    with state.lock:
                        report = state.librarian.ingest_text(
                            text, source=str(payload.get("source") or "ui"))
                        stats = state.store.stats()
                    report = {k: v for k, v in report.items()
                              if k != "document"}
                    self._json(200, {"ok": True, "report": report,
                                     "stats": stats})
                elif path == "/api/seed":
                    stats = state.seed_demo()
                    self._json(200, {"ok": True, "stats": stats})
                else:
                    self._json(404, {"ok": False, "error": "not found"})
            except Exception as exc:
                self._json(503, {"ok": False,
                                 "error": f"backend unavailable: {exc}"})

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8765,
                  user: str = "demo") -> ThreadingHTTPServer:
    state = AppState(user=user)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    server.app_state = state  # for tests / embedding
    return server


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RecallGraph — agent memory that shows its reasoning</title>
<style>
  :root { --bg:#0f1420; --panel:#171e2e; --panel2:#1e2740; --line:#2c3852;
          --text:#e8ecf4; --dim:#9aa7bd; --accent:#5ec8a5; --warn:#e8a13a;
          --bad:#e05d5d; --paper:#e8a13a; --concept:#5ea8e8; --claim:#5ec8a5;
          --question:#b48ae0; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:18px 24px 10px; display:flex; flex-wrap:wrap; gap:14px;
           align-items:baseline; }
  header h1 { margin:0; font-size:26px; }
  header h1 span { color:var(--accent); }
  header p { margin:0; color:var(--dim); font-size:14px; }
  .chips { display:flex; gap:8px; flex-wrap:wrap; margin-left:auto; }
  .chip { background:var(--panel2); border:1px solid var(--line);
          border-radius:999px; padding:4px 12px; font-size:13px; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%;
         background:var(--bad); margin-right:6px; }
  .dot.up { background:var(--accent); }
  main { display:grid; grid-template-columns:minmax(340px,5fr) 7fr; gap:16px;
         padding:8px 24px 28px; align-items:start; }
  @media (max-width:980px){ main{ grid-template-columns:1fr; } }
  section { background:var(--panel); border:1px solid var(--line);
            border-radius:12px; padding:16px; margin-bottom:16px; }
  section h2 { margin:0 0 10px; font-size:16px; }
  section h2 small { color:var(--dim); font-weight:400; font-size:12px; }
  svg { width:100%; height:auto; background:#121828; border-radius:8px; }
  .legend { display:flex; gap:14px; flex-wrap:wrap; font-size:12px;
            color:var(--dim); margin-top:8px; }
  .legend i { display:inline-block; width:10px; height:10px; border-radius:50%;
              margin-right:5px; }
  textarea, input[type=text] { width:100%; background:#0d1220; color:var(--text);
    border:1px solid var(--line); border-radius:8px; padding:10px;
    font:13px/1.45 ui-monospace,Menlo,Consolas,monospace; }
  textarea { min-height:118px; resize:vertical; }
  button { background:var(--accent); color:#0b1512; border:0; border-radius:8px;
           padding:9px 16px; font-weight:600; cursor:pointer; font-size:14px; }
  button.secondary { background:var(--panel2); color:var(--text);
                     border:1px solid var(--line); }
  button:hover { filter:brightness(1.1); }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .examples { margin-top:10px; display:flex; gap:6px; flex-wrap:wrap; }
  .examples button { background:transparent; color:var(--dim);
    border:1px dashed var(--line); font-weight:400; font-size:12.5px;
    padding:6px 10px; }
  .examples button:hover { color:var(--text); border-color:var(--accent); }
  .answer { background:var(--panel2); border-left:4px solid var(--accent);
            border-radius:8px; padding:12px 14px; font-size:15px; }
  .answer.none { border-left-color:var(--warn); }
  .meta { color:var(--dim); font-size:13px; margin-top:8px; }
  .steps { list-style:none; margin:0; padding:0; }
  .steps li { border-left:2px solid var(--line); padding:0 0 14px 16px;
              position:relative; }
  .steps li::before { content:attr(data-n); position:absolute; left:-11px;
    top:0; width:20px; height:20px; border-radius:50%; background:var(--accent);
    color:#0b1512; font-size:12px; font-weight:700; text-align:center;
    line-height:20px; }
  .steps .trav { font:12px ui-monospace,Menlo,Consolas,monospace;
                 color:var(--concept); }
  .steps .found { color:var(--dim); font-size:12.5px; word-break:break-word; }
  .pill { display:inline-block; border-radius:999px; padding:1px 9px;
          font-size:11.5px; font-weight:700; }
  .pill.high { background:#5a2323; color:#ffb3b3; }
  .pill.medium { background:#4d3d17; color:#ffd98a; }
  .pill.low { background:#23405a; color:#a8d4ff; }
  .warnbox { background:#3a2a12; border:1px solid var(--warn); color:#ffd98a;
             border-radius:8px; padding:9px 12px; font-size:13.5px;
             margin-top:10px; }
  ul.tight { margin:6px 0 0; padding-left:18px; }
  ul.tight li { margin-bottom:6px; font-size:14px; }
  .empty { color:var(--dim); font-size:14px; }
  .err { color:#ffb3b3; font-size:14px; }
  code { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12.5px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>Recall<span>Graph</span></h1>
    <p>Agent memory in FalkorDB — every answer shows the path it took.</p>
  </div>
  <div class="chips" id="chips"><span class="chip"><span class="dot" id="dbdot"></span>FalkorDB</span></div>
</header>
<main>
  <div>
    <section>
      <h2>Memory graph <small id="graphname"></small></h2>
      <svg id="graph" viewBox="0 0 640 520" role="img" aria-label="memory graph"></svg>
      <div class="legend">
        <span><i style="background:var(--paper)"></i>Paper</span>
        <span><i style="background:var(--concept)"></i>Concept</span>
        <span><i style="background:var(--claim)"></i>Claim</span>
        <span><i style="background:var(--question)"></i>Question</span>
        <span>Hover a node for its full text · click a node to explain its claim</span>
      </div>
    </section>
    <section>
      <h2>Ingest <small>Librarian writes — marked-up text, see format below</small></h2>
      <textarea id="ingestText" spellcheck="false"></textarea>
      <div class="row" style="margin-top:10px">
        <button id="ingestBtn">Ingest into memory</button>
        <button class="secondary" id="sampleBtn">Fill Zebra sample</button>
        <button class="secondary" id="seedBtn">Reset demo data</button>
      </div>
      <p class="meta">Format: <code>PAPER: Title | Authors | Year</code> ·
        <code>CONCEPT: Name — description</code> ·
        <code>CLAIM [0.85]: text ABOUT: Concept</code> ·
        <code>QUESTION: text ABOUT: Concept</code></p>
      <div id="ingestResult"></div>
    </section>
  </div>
  <div>
    <section>
      <h2>Ask <small>Scout answers by traversal — and shows its work</small></h2>
      <div class="row">
        <input type="text" id="question" style="flex:1;min-width:260px"
               placeholder="Why should an AI agent store memory in a graph?">
        <button id="askBtn">Ask</button>
      </div>
      <div class="examples" id="examples"></div>
      <div id="askResult" style="margin-top:14px">
        <p class="empty">Ask a question — the answer, its reasoning path and
        the actions Scout derives from that path will appear here.</p>
      </div>
    </section>
    <section>
      <h2>Reasoning path</h2>
      <div id="pathPanel"><p class="empty">No traversal yet.</p></div>
    </section>
    <section>
      <h2>Scout brief <small>from the same shared graph — no re-teaching</small></h2>
      <div id="briefPanel"><p class="empty">Loading…</p></div>
      <div class="row" style="margin-top:10px">
        <button class="secondary" id="briefBtn">Refresh brief</button>
      </div>
    </section>
  </div>
</main>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const COLORS = {Paper:"#e8a13a", Concept:"#5ea8e8", Claim:"#5ec8a5", Question:"#b48ae0"};
const SAMPLE = `PAPER: Zebra Indexing Field Notes | Demo Author | 2026
CONCEPT: Zebra Indexing — Indexing records by stripe-like keys
CLAIM [0.66]: Zebra indexing speeds recall for striped data ABOUT: Zebra Indexing
QUESTION: Does zebra indexing help? ABOUT: Zebra Indexing`;
$("ingestText").value = SAMPLE;

const EXAMPLES = [
  "Why should an AI agent store memory in a graph?",
  "How can two agents share the same memory?",
  "Tell me about Multi-hop Reasoning",
  "What is the capital of France?"
];
$("examples").innerHTML = EXAMPLES.map(q =>
  `<button data-q="${esc(q)}">${esc(q)}</button>`).join("");
document.querySelectorAll("#examples button").forEach(b =>
  b.addEventListener("click", () => { $("question").value = b.dataset.q; ask(); }));

async function call(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({ok:false, error:"bad response"}));
  if (!j.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}
const post = (path, body) => call(path, {method:"POST",
  headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});

function renderChips(stats, ping) {
  $("dbdot").className = "dot" + (ping ? " up" : "");
  const n = stats.nodes || {}, total = stats.total_nodes ?? 0,
        edges = stats.total_edges ?? 0;
  $("chips").innerHTML =
    `<span class="chip"><span class="dot${ping ? " up" : ""}"></span>FalkorDB</span>` +
    `<span class="chip">${total} nodes · ${edges} edges</span>` +
    Object.keys(n).map(k => `<span class="chip">${esc(k)}: ${n[k]}</span>`).join("");
  $("graphname").textContent = stats.graph ? "— " + stats.graph : "";
}

function drawGraph(snap) {
  const svg = $("graph"), W = 640, H = 520, cx = W/2, cy = H/2;
  const nodes = snap.nodes, pos = {};
  const groups = {};
  nodes.forEach(n => { (groups[n.label] = groups[n.label] || []).push(n); });
  // Papers/concepts near the centre ring, claims mid, questions outer —
  // deterministic layout so the demo recording is stable.
  const ring = {Paper:70, Concept:130, Claim:195, Question:245};
  Object.entries(groups).forEach(([label, list]) => {
    list.forEach((n, i) => {
      const a = (i / Math.max(1, list.length)) * Math.PI * 2 +
                (label.charCodeAt(0) % 7) * 0.35;
      const r = ring[label] || 180;
      pos[n.key] = {x: cx + r * Math.cos(a), y: cy + r * 0.82 * Math.sin(a), n};
    });
  });
  let out = "";
  snap.edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to]; if (!a || !b) return;
    out += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#2c3852" stroke-width="1.2"><title>${esc(e.type)}</title></line>`;
  });
  Object.values(pos).forEach(({x, y, n}) => {
    const label = n.title.length > 26 ? n.title.slice(0, 26) + "…" : n.title;
    out += `<g class="node" data-id="${esc(n.id)}" data-label="${esc(n.label)}" style="cursor:pointer">
      <circle cx="${x}" cy="${y}" r="13" fill="${COLORS[n.label]}" fill-opacity="0.9"/>
      <text x="${x}" y="${y + 26}" fill="#c7d0e0" font-size="9.5" text-anchor="middle">${esc(label)}</text>
      <title>${esc(n.label)} · ${esc(n.id)}\n${esc(n.title)}</title></g>`;
  });
  svg.innerHTML = out || `<text x="320" y="260" fill="#9aa7bd" text-anchor="middle">Graph is empty — ingest or reset the demo data.</text>`;
  svg.querySelectorAll(".node").forEach(g => g.addEventListener("click", () => {
    if (g.dataset.label === "Claim") explain(g.dataset.id);
  }));
}

async function refreshAll() {
  try {
    const s = await call("/api/stats");
    renderChips(s.stats, s.ping);
    const g = await call("/api/graph");
    drawGraph(g.snapshot);
    await refreshBrief();
  } catch (e) {
    $("briefPanel").innerHTML = `<p class="err">${esc(e.message)} — is FalkorDB running on 127.0.0.1:6379?</p>`;
  }
}

async function refreshBrief() {
  try {
    const {brief} = await call("/api/brief");
    const acts = (brief.suggested_actions || []).map(a =>
      `<li><span class="pill ${esc(a.priority)}">${esc(a.priority)}</span> ${esc(a.action)}</li>`).join("");
    $("briefPanel").innerHTML =
      `<p style="margin:0 0 6px">${esc(brief.summary)}</p>` +
      (brief.unanswered_questions?.length
        ? `<p class="meta">Unanswered: ${brief.unanswered_questions.map(q => esc(q.text)).join(" · ")}</p>` : "") +
      (brief.contradictions?.length
        ? `<p class="meta">Open contradictions: ${brief.contradictions.map(c => esc(c.a_id + " vs " + c.b_id)).join(" · ")}</p>` : "") +
      (acts ? `<ul class="tight">${acts}</ul>` : "");
  } catch (e) { $("briefPanel").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

function renderResult(result) {
  const none = !result.answers || result.answers.length === 0;
  const cites = (result.citations || []).map(c =>
    `${esc(c.title)} (${esc(c.id)})`).join("; ");
  const warns = (result.contradiction_warnings || []).map(w =>
    `<div class="warnbox">⚠ Contested by <b>${esc(w.contradicting_claim)}</b>: ${esc(w.text)}</div>`).join("");
  const acts = (result.suggested_actions || []).map(a =>
    `<li><span class="pill ${esc(a.priority)}">${esc(a.priority)}</span>
     <b>${esc(a.action)}</b><br><span class="meta">${esc(a.reason)} · via <code>${esc(a.based_on)}</code></span></li>`).join("");
  $("askResult").innerHTML =
    `<div class="answer${none ? " none" : ""}">${esc(result.answer_text)}</div>` +
    `<p class="meta">Confidence: <b>${esc(result.confidence)}</b>` +
    (result.matched_question ? ` · matched Question <code>${esc(result.matched_question.id)}</code>` : " · no stored Question matched (fallback traversal)") +
    (cites ? `<br>Citation: ${cites}` : "") + `</p>` + warns +
    (acts ? `<h3 style="font-size:14px;margin:14px 0 4px">Suggested actions — derived from this path</h3><ul class="tight">${acts}</ul>` : "");

  const steps = (result.reasoning_steps || []).map(s =>
    `<li data-n="${s.step}"><div>${esc(s.description)}</div>
     <div class="trav">${esc(s.traversal)}</div>
     <div class="found">→ ${s.found && s.found.length ? esc(s.found.join(", ")) : "—"}</div></li>`).join("");
  const chains = [];
  (result.answers || []).forEach(a => (a.support_chains || []).forEach(ch =>
    chains.push(ch.map(n => n.label || n.id).join(" —SUPPORTS→ "))));
  $("pathPanel").innerHTML =
    `<ol class="steps">${steps}</ol>` +
    (chains.length ? `<p class="meta">Support chains:<br>${chains.map(esc).join("<br>")}</p>` : "");
}

async function ask() {
  const q = $("question").value.trim();
  if (!q) return;
  $("askResult").innerHTML = `<p class="empty">Traversing the graph…</p>`;
  try { renderResult((await post("/api/ask", {question: q})).result); }
  catch (e) { $("askResult").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

async function explain(claimId) {
  // Reuse the ask pipeline's path view via a concept-style query is overkill;
  // clicking a claim asks the engine about its own text instead.
  $("question").value = "";
  $("askResult").innerHTML = `<p class="empty">Claim <code>${esc(claimId)}</code> — ask a question above to see it inside a reasoning path, or run <code>explain_claim</code> from the API tests.</p>`;
}

$("askBtn").addEventListener("click", ask);
$("question").addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
$("sampleBtn").addEventListener("click", () => { $("ingestText").value = SAMPLE; });
$("ingestBtn").addEventListener("click", async () => {
  $("ingestResult").innerHTML = `<p class="empty">Ingesting…</p>`;
  try {
    const j = await post("/api/ingest", {text: $("ingestText").value, source: "ui"});
    const r = j.report;
    $("ingestResult").innerHTML =
      `<p class="meta">Librarian wrote ${esc(JSON.stringify(r.counts))} — new claims: ` +
      `${esc((r.new_claim_ids || []).join(", ") || "none (already known)")} · graph now ` +
      `${esc(r.nodes_after)} nodes.</p>`;
    await refreshAll();
  } catch (e) { $("ingestResult").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
});
$("seedBtn").addEventListener("click", async () => {
  try { await post("/api/seed", {}); await refreshAll();
    $("ingestResult").innerHTML = `<p class="meta">Demo data reset to the 3 sample papers.</p>`;
  } catch (e) { $("ingestResult").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
});
$("briefBtn").addEventListener("click", refreshBrief);
refreshAll();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="RecallGraph web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--user", default="demo",
                        help="per-user graph suffix (recallgraph_<user>)")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.user)
    print(f"RecallGraph UI on http://{args.host}:{args.port} "
          f"(graph: recallgraph_{args.user}) — Ctrl-C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
