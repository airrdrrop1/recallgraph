"""RecallGraph — graph memory for an AI research assistant.

Built during Graph Hacks (WeMakeDevs x FalkorDB), 15-18 Oct 2026.
Day-1 foundation: FalkorDB store, deterministic extractor, demo ingest.
Day-2 brain: reasoning engine (question -> traversal -> answer + visible
reasoning path) and the Librarian / Scout two-agent coordination layer.
"""

__all__ = ["store", "extract", "demo_data", "reasoning", "agents"]
__version__ = "0.2.0"
