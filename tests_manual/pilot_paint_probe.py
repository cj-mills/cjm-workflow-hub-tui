"""Headless paint-path pilot for the hub (67335f7d: pilot probe, not pytest,
verifies TUI paint strings). Stands a REAL throwaway workspace graph (three
sources, one proposed ordered collection, one transcribed source), then drives
the full curation vocabulary through the painted surface: confirm (y),
file-with-existing-title two-phase (f, d544e250), rename (r), order mode
(g + J/K + enter), reload, quit.

    python tests_manual/pilot_paint_probe.py [manifests_dir]
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from textual.widgets import Input, Static

from cjm_context_graph_layer.journal import journal_extend
from cjm_substrate.core.manager import CapabilityManager
from cjm_substrate.core.queue import JobQueue
from cjm_transcription_core.cli import load_capabilities
from cjm_transcript_graph_schema.schema import (AudioRenditionNode, AudioSegmentNode,
                                                CollectionNode, SourceNode,
                                                TranscriptNode, collection_edges)
from cjm_workflow_hub_tui.app import HubApp

GRAPH = "cjm-capability-graph-sqlite"


async def plant(manifests_dir: str, db: str, journal: str) -> dict:
    """Stand the throwaway graph the drive walks (all writes journaled)."""
    manager = CapabilityManager(search_paths=[Path(manifests_dir)])
    load_capabilities(manager, [GRAPH], configs={GRAPH: {"db_path": db}})
    queue = JobQueue(deps=manager)
    await queue.start()
    try:
        chs = [SourceNode(content_hash=f"sha256:h{i}", path=f"/m/Chapter {i}.mp3",
                          title=f"Chapter {i}") for i in (1, 2)]
        loose = SourceNode(content_hash="sha256:loose", path="/m/Loose Talk.mp3",
                           title="Loose Talk")
        aseg = AudioSegmentNode(source=loose.id, index=0, start=0.0, end=100.0)
        rend = AudioRenditionNode(audio_segment=aseg.id, model_input_path="/m/w.wav",
                                  model_input_hash="sha256:w")
        tr = TranscriptNode(rendition=rend.id, transcriber="whisper", config_hash="c",
                            text="hello", audio_hash="sha256:w")
        coll = CollectionNode(title="Archive", status="proposed", actor="cli:probe")
        nodes = [n.to_graph_node() for n in (*chs, loose, aseg, rend, tr, coll)]
        edges = ([rend.derived_edge(), tr.derived_edge()]
                 + collection_edges(coll.id, [c.id for c in chs], ordered=True))
        await journal_extend(queue, GRAPH, nodes, edges, journal_path=journal,
                             verb="source-emission", actor="probe",
                             args={"probe": "plant"})
        return {"coll": coll.id, "ch": [c.id for c in chs], "loose": loose.id}
    finally:
        await queue.stop()
        manager.unload_capability(GRAPH)


async def drive(manifests_dir: str, db: str, ids: dict) -> None:
    app = HubApp(manifests_dir, graph_db_path=db)
    async with app.run_test() as pilot:
        def paint() -> str:
            app._paint()
            return str(app.query_one("#main", Static).render())

        def status() -> str:
            app._paint()
            return str(app.query_one("#status", Static).render())

        await pilot.pause()
        body = paint()
        assert "WORKSPACE HUB" in body, body[:200]
        assert "Archive" in body and "⚑ proposed" in body, body[:400]
        assert "Unfiled" in body and "Loose Talk" in body, body[:400]
        assert "Tdc" in body, body  # the transcribed loose source's glance
        assert "tdc" in body        # untranscribed members
        assert "·ordered" in body   # the planted chain paints

        # y on the collection header discharges the flag
        assert app.rows[app.cursor]["kind"] == "collection"
        await pilot.press("y")
        await pilot.pause()
        assert "⚑ proposed" not in paint()

        # f on the loose source, typing the EXISTING title: two-phase confirm
        while app.rows[app.cursor].get("id") != ids["loose"]:
            await pilot.press("j")
        await pilot.press("f")
        editor = app.query_one("#editor", Input)
        assert app.editing == "file" and editor.display
        editor.value = "Archive"
        await pilot.press("enter")
        assert app.pending_title == "Archive", "existing title must surface first"
        assert "attaches to EXISTING" in status(), status()
        await pilot.press("enter")           # second enter commits
        await pilot.pause()
        body = paint()
        assert "(3)" in body, body[:400]     # membership unioned
        assert "Unfiled" not in body

        # r renames (no existing 'Library'): straight commit
        while app.rows[app.cursor]["kind"] != "collection":
            await pilot.press("k")
        await pilot.press("r")
        editor = app.query_one("#editor", Input)
        assert editor.value == "Archive", "rename prefills the current title"
        editor.value = "Library"
        await pilot.press("enter")
        await pilot.pause()
        body = paint()
        assert "Library" in body and "Archive" not in body, body[:400]

        # g order mode: demote the first member, commit, chain repaints
        await pilot.press("g")
        assert app.mode == "order" and len(app.order_work) == 3
        first = app.order_work[0]
        await pilot.press("j")               # onto the first member row
        await pilot.press("J")               # demote it
        assert app.order_work[1] == first
        await pilot.press("enter")
        await pilot.pause()
        assert app.mode == "browse"
        ordered_rows = [r for r in app.rows if r["kind"] == "source" and r["ordered"]]
        assert len(ordered_rows) == 3, "full chain rematerialized"
        assert ordered_rows[1]["id"] == first

        # escape is inert in browse; q tears down
        await pilot.press("escape")
        await pilot.press("q")
    assert app.return_value is None
    print("pilot OK: grouped paint + glance, confirm, two-phase file-to-existing,"
          " rename, order commit, teardown")


def main() -> None:
    manifests_dir = sys.argv[1] if len(sys.argv) > 1 else ".cjm/manifests"
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "hub_probe.db")
        journal = str(Path(td) / "hub_probe.writes.jsonl")
        ids = asyncio.run(plant(manifests_dir, db, journal))
        asyncio.run(drive(manifests_dir, db, ids))


if __name__ == "__main__":
    main()
