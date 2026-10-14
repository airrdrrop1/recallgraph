"""Fictional-but-plausible sample research documents for the day-1 demo.

Topic: graph memory for AI agents (the hackathon theme itself), so the demo
data doubles as an explanation of why RecallGraph is built the way it is.
All papers/authors below are sample data written for this demo.
"""

DOCUMENTS = [
    {
        "paper": {
            "id": "paper-graph-memory-2025",
            "title": "Graph Memory for Persistent AI Agents",
            "authors": "Sample Author A; Sample Author B",
            "year": 2025,
            "source": "demo-data",
        },
        "concepts": [
            {"id": "concept-graph-memory", "name": "Graph Memory",
             "description": "Storing agent memory as nodes and edges in a graph database."},
            {"id": "concept-multi-hop", "name": "Multi-hop Reasoning",
             "description": "Answering a question by traversing several edges."},
        ],
        "claims": [
            {"id": "claim-graph-beats-flat", "confidence": 0.82,
             "text": "A graph store preserves relations between facts, so an agent can retrieve connected context instead of isolated text chunks.",
             "about": ["concept-graph-memory"]},
            {"id": "claim-multihop-path", "confidence": 0.78,
             "text": "Multi-hop traversal returns an explicit path that can be shown to the user as the reasoning behind an answer.",
             "about": ["concept-multi-hop", "concept-graph-memory"],
             "supports": [{"label": "Claim", "id": "claim-graph-beats-flat"}]},
        ],
        "questions": [
            {"id": "q-why-graph", "text": "Why should an AI agent store memory in a graph?",
             "asks_about": ["concept-graph-memory"]},
        ],
        "cites": [],
    },
    {
        "paper": {
            "id": "paper-flat-rag-critique-2026",
            "title": "Limits of Flat Retrieval for Long-lived Agents",
            "authors": "Sample Author C",
            "year": 2026,
            "source": "demo-data",
        },
        "concepts": [
            {"id": "concept-flat-rag", "name": "Flat Retrieval",
             "description": "Chunk-and-embed retrieval with no explicit relations between chunks."},
        ],
        "claims": [
            {"id": "claim-flat-loses-relations", "confidence": 0.74,
             "text": "Flat retrieval loses explicit relations between facts, which makes contradiction checks unreliable.",
             "about": ["concept-flat-rag", "concept-graph-memory"],
             "supports": [{"label": "Claim", "id": "claim-graph-beats-flat"}]},
            {"id": "claim-flat-is-enough", "confidence": 0.31,
             "text": "Flat retrieval alone is sufficient for long-lived agent memory.",
             "about": ["concept-flat-rag"],
             "contradicts": ["claim-graph-beats-flat"]},
            {"id": "claim-answer-why-graph", "confidence": 0.8,
             "text": "Agents should use a graph because relations stay explicit, contradictions stay checkable, and every answer can carry its traversal path.",
             "about": ["concept-graph-memory"],
             "answers": ["q-why-graph"],
             "supports": [{"label": "Claim", "id": "claim-graph-beats-flat"},
                          {"label": "Claim", "id": "claim-multihop-path"}]},
        ],
        "questions": [
            {"id": "q-flat-enough", "text": "Is flat retrieval enough for agent memory?",
             "asks_about": ["concept-flat-rag"]},
        ],
        "cites": ["paper-graph-memory-2025"],
    },
    {
        "paper": {
            "id": "paper-agent-coordination-2026",
            "title": "Shared Graph State for Coordinating Two Agents",
            "authors": "Sample Author D; Sample Author A",
            "year": 2026,
            "source": "demo-data",
        },
        "concepts": [
            {"id": "concept-agent-coordination", "name": "Agent Coordination",
             "description": "Two or more agents reading and writing one shared memory graph."},
        ],
        "claims": [
            {"id": "claim-shared-graph-handoff", "confidence": 0.77,
             "text": "When a writer agent and a reader agent share one graph, handoff needs no re-teaching: the reader traverses what the writer stored.",
             "about": ["concept-agent-coordination", "concept-graph-memory"],
             "supports": [{"label": "Concept", "id": "concept-graph-memory"}]},
            {"id": "claim-answer-coordination", "confidence": 0.76,
             "text": "A shared graph lets a second agent answer from the first agent's memory because both traverse the same nodes and edges.",
             "about": ["concept-agent-coordination"],
             "answers": ["q-shared-memory"]},
        ],
        "questions": [
            {"id": "q-shared-memory", "text": "How can two agents share the same memory?",
             "asks_about": ["concept-agent-coordination"]},
        ],
        "cites": ["paper-graph-memory-2025"],
    },
]
