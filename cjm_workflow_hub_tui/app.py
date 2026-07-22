"""The workspace front door (hub v0, e5849229): one keyboard surface answering
'what is in this workspace and where is each source in the pipeline'. Paints
the spine's grouped rows (collections with ⚑-flagged proposals, stage-at-a-
glance status per source), launches the stage TUIs on a source (1/2/3, via
Textual suspend), and drives the curation vocabulary — confirm (y), file/refile
(f), rename-or-merge (r), order mode (g + J/K). Every curation commit rides the
sidecar journal (ccbab9f5). Presentation lessons carried: spans-only Rich
styling, one-line rows, AUTO_FOCUS None, transient #editor Input with the
two-phase existing-title confirm (d544e250: surface, never block)."""

import getpass
import subprocess
from typing import Any, Dict, List, Optional

from cjm_context_graph_layer.journal import sidecar_journal_path
from cjm_substrate_tui_kit.viewport import tail, visible_slice
from cjm_transcript_graph_schema.schema import collection_node_id
from cjm_transcription_core.curation import (confirm_collection, file_sources, refile_members,
                                             rename_collection, set_collection_order)
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, Static

from .spine import build_rows, HubData, load_hub_data, open_stack, stage_glance


class HubApp(App):
    """The hub surface: grouped browse + curation gestures + stage-TUI launch.

    One Static pane over the spine's flat row list, cursor-windowed
    (transcription-TUI idiom). The transient #editor Input serves f (file/
    refile) and r (rename/merge) with the d544e250 two-phase confirm: a title
    that resolves to an EXISTING collection paints what it attaches to and
    takes a second enter — surfacing, never a gate. Order mode (g) reorders a
    collection's members in place (J/K) and commits the chain on enter."""

    AUTO_FOCUS = None

    CSS = """
    #main { height: 1fr; }
    #status { dock: bottom; height: 1; }
    #editor { dock: bottom; height: 3; }
    """

    BINDINGS = [
        Binding("j", "move(1)", "down"),
        Binding("down", "move(1)", "down", show=False),
        Binding("k", "move(-1)", "up"),
        Binding("up", "move(-1)", "up", show=False),
        Binding("space", "toggle_select", "select source", show=False),
        Binding("y", "confirm", "confirm collection"),
        Binding("f", "file", "file/refile"),
        Binding("r", "rename", "rename/merge"),
        Binding("g", "order_mode", "order mode"),
        Binding("J", "order_shift(1)", "move member down", show=False),
        Binding("K", "order_shift(-1)", "move member up", show=False),
        Binding("enter", "commit", "commit"),
        Binding("1", "launch('transcription')", "transcribe", show=False),
        Binding("2", "launch('decomp')", "decompose", show=False),
        Binding("3", "launch('correction')", "correct", show=False),
        Binding("R", "reload", "reload", show=False),
        Binding("escape", "cancel", "cancel", show=False, priority=True),
        Binding("q", "quit_app", "quit"),
    ]

    LAUNCH_COMMANDS = {
        "transcription": ["cjm-transcription-tui"],
        "decomp": ["cjm-transcript-decomp-tui"],
        "correction": ["cjm-transcript-correction-tui", "--source"],  # + source id
    }

    def __init__(self, manifests_dir: str,                    # Capability manifests directory
                 *, graph_db_path: Optional[str] = None,      # Explicit db (None = workspace answers)
                 graph_capability: str = "cjm-capability-graph-sqlite"):
        super().__init__()
        self.manifests_dir = manifests_dir
        self.graph_capability = graph_capability
        self.graph_db_path = graph_db_path
        self.manager = None
        self.queue = None
        self.journal_path: Optional[str] = None
        self.actor = f"human:{getpass.getuser()}"
        self.data = HubData()
        self.rows: List[Dict[str, Any]] = []
        self.cursor = 0
        self.selected: set = set()           # source ids picked for f (space)
        self.mode = "browse"                 # "browse" | "order"
        self.order_coll: Optional[str] = None
        self.order_work: List[str] = []      # member ids being reordered
        self.editing: Optional[str] = None   # None | "file" | "rename"
        self.pending_title: Optional[str] = None  # two-phase existing-title confirm
        self.busy: Optional[str] = None
        self.error: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Static(id="main")
        yield Static(id="status")
        editor = Input(id="editor")
        editor.display = False
        yield editor

    async def on_mount(self) -> None:
        self.busy = "opening workspace graph…"
        self._paint()
        try:
            self.manager, self.queue, db = await open_stack(
                self.graph_db_path, manifests_dir=self.manifests_dir,
                graph_capability=self.graph_capability)
            self.graph_db_path = db
            self.journal_path = sidecar_journal_path(db)
            await self._reload()
        except Exception as e:
            self.busy = None
            self.error = str(e)
            self._paint()

    async def _reload(self) -> None:
        self.busy = "loading…"
        self._paint()
        self.data = await load_hub_data(self.queue, self.graph_capability)
        self.rows = build_rows(self.data)
        self.cursor = max(0, min(self.cursor, len(self.rows) - 1))
        self.selected &= {r["id"] for r in self.rows if r["kind"] == "source"}
        self.busy = None
        self._paint()

    # ---- painting (spans only; one-line rows) ----

    def _paint(self) -> None:
        try:
            main = self.query_one("#main", Static)
            status = self.query_one("#status", Static)
        except Exception:
            return
        main.update(self._paint_rows())
        status.update(self._paint_status())

    def _paint_rows(self) -> Text:
        width = max(20, self.size.width)
        out = Text()
        title_line = Text()
        title_line.append(" WORKSPACE HUB ", style="bold")
        title_line.append(tail(str(self.graph_db_path or ""), width - 16), style="dim")
        out.append_text(title_line)
        out.append("\n")
        if not self.rows:
            out.append("   (no sources on the graph yet — 1 launches the "
                       "transcription TUI)\n", style="dim")
            return out
        budget = max(3, max(4, self.size.height - 1) - 3)
        start, end, above, below = visible_slice(len(self.rows), self.cursor, budget)
        if above:
            out.append(f"   … {above} above\n", style="dim")
        for i in range(start, end):
            out.append_text(self._paint_row(i, width))
            out.append("\n")
        if below:
            out.append(f"   … {below} below\n", style="dim")
        return out

    def _paint_row(self, i: int, width: int) -> Text:
        row = self.rows[i]
        focus = (i == self.cursor)
        line = Text()
        line.append(" > " if focus else "   ", style="bold cyan" if focus else "dim")
        if row["kind"] == "collection":
            style = {"proposed": "yellow", "confirmed": "green",
                     "none": "dim"}[row["status"]]
            line.append(row["title"], style=("bold " + style).strip())
            if row["status"] == "proposed":
                line.append(" ⚑ proposed", style="yellow")
            line.append(f"  ({row['count']})", style="dim")
        else:
            in_order = (self.mode == "order" and row.get("coll_id") == self.order_coll)
            if in_order:
                pos = self.order_work.index(row["id"]) if row["id"] in self.order_work else -1
                line.append(f"{pos + 1:>4}. ", style="bold magenta")
            else:
                picked = row["id"] in self.selected
                line.append("[x] " if picked else "[ ] ",
                            style="green" if picked else "dim")
                line.append("  " if row["coll_id"] else "")
            line.append(row["title"], style="bold" if focus else "")
            glance = stage_glance(row.get("counts") or {})
            if glance:
                line.append(f"  {glance}", style="dim cyan")
            if row.get("ordered"):
                line.append("  ·ordered", style="dim")
        line.truncate(width, overflow="ellipsis")
        return line

    def _paint_status(self) -> Text:
        status = Text()
        if self.error:
            status.append(f" {self.error} ", style="bold red")
        elif self.busy:
            status.append(f" {self.busy} ", style="yellow")
        elif self.pending_title:
            existing = self._existing_by_title(self.pending_title)
            n = len(self.data.members.get(existing, [])) if existing else 0
            status.append(f" '{self.pending_title}' attaches to EXISTING "
                          f"collection ({n} members) — enter again to confirm ",
                          style="bold yellow")
        elif self.editing:
            status.append(" enter title (empty cancels) · esc cancel ", style="dim")
        elif self.mode == "order":
            status.append(" ORDER MODE  ·  J/K move member · enter commit · esc cancel ",
                          style="bold magenta")
        else:
            status.append(" space select · f file/refile · r rename/merge · y confirm"
                          " · g order · 1/2/3 launch t/d/c · R reload · q quit",
                          style="dim")
        return status

    # ---- gestures ----

    def _focused(self) -> Optional[Dict[str, Any]]:
        return self.rows[self.cursor] if self.rows else None

    def _existing_by_title(self, title: str) -> Optional[str]:
        cid = collection_node_id(title)
        return cid if any(c["id"] == cid for c in self.data.collections) else None

    def action_move(self, delta: int) -> None:
        if not self.rows or self.editing:
            return
        self.cursor = max(0, min(self.cursor + delta, len(self.rows) - 1))
        self._paint()

    def action_toggle_select(self) -> None:
        row = self._focused()
        if self.mode != "browse" or self.editing or not row or row["kind"] != "source":
            return
        if row["id"] in self.selected:
            self.selected.discard(row["id"])
        else:
            self.selected.add(row["id"])
        self._paint()

    async def action_confirm(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]
                or row["status"] != "proposed"):
            return
        await confirm_collection(self.queue, self.graph_capability, row["id"],
                                 self.actor, journal_path=self.journal_path)
        await self._reload()

    def action_file(self) -> None:
        row = self._focused()
        if self.mode != "browse" or self.editing or self.busy or not row:
            return
        targets = self.selected or ({row["id"]} if row["kind"] == "source" else set())
        if not targets:
            self.error = "select sources (space) or focus one before f"
            self._paint()
            return
        self._open_editor("file")

    def action_rename(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]):
            return
        self._open_editor("rename", prefill=row["title"])

    def _open_editor(self, kind: str, prefill: str = "") -> None:
        editor = self.query_one("#editor", Input)
        editor.value = prefill
        editor.display = True
        editor.focus()
        self.editing = kind
        self.pending_title = None
        self.error = None
        self._paint()

    def _close_editor(self) -> None:
        editor = self.query_one("#editor", Input)
        editor.display = False
        editor.value = ""
        self.set_focus(None)
        self.editing = None
        self.pending_title = None

    async def on_input_submitted(self, event) -> None:
        if not self.editing:
            return
        title = event.value.strip()
        if not title:
            self._close_editor()
            self._paint()
            return
        # d544e250: an existing title surfaces before it commits (two-phase)
        if self._existing_by_title(title) and self.pending_title != title:
            self.pending_title = title
            self._paint()
            return
        kind = self.editing
        self._close_editor()
        self.busy = "curating…"
        self._paint()
        try:
            if kind == "rename":
                row = self._focused()
                await rename_collection(self.queue, self.graph_capability,
                                        row["id"], title, self.actor,
                                        journal_path=self.journal_path)
            else:
                await self._commit_file(title)
            self.selected.clear()
            self.error = None
        except Exception as e:
            self.error = str(e)
        await self._reload()

    async def _commit_file(self, title: str) -> None:
        """File/refile the picked sources into `title` (grouped by the
        collection they leave, so each move is one journaled op)."""
        row = self._focused()
        targets = self.selected or ({row["id"]} if row and row["kind"] == "source" else set())
        by_coll: Dict[Optional[str], List[str]] = {}
        for r in self.rows:
            if r["kind"] == "source" and r["id"] in targets:
                by_coll.setdefault(r.get("coll_id"), []).append(r["id"])
        for coll_id, ids in by_coll.items():
            if coll_id:
                await refile_members(self.queue, self.graph_capability, ids,
                                     coll_id, title, self.actor,
                                     journal_path=self.journal_path)
            else:
                await file_sources(self.queue, self.graph_capability, title, ids,
                                   self.actor, journal_path=self.journal_path)

    def action_order_mode(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]):
            return
        members = [r["id"] for r in self.rows
                   if r["kind"] == "source" and r.get("coll_id") == row["id"]]
        if len(members) < 2:
            self.error = "order mode needs at least two members"
            self._paint()
            return
        self.mode = "order"
        self.order_coll = row["id"]
        self.order_work = members
        self._paint()

    def action_order_shift(self, delta: int) -> None:
        row = self._focused()
        if (self.mode != "order" or not row or row["kind"] != "source"
                or row.get("coll_id") != self.order_coll):
            return
        i = self.order_work.index(row["id"])
        j = i + delta
        if not (0 <= j < len(self.order_work)):
            return
        self.order_work[i], self.order_work[j] = self.order_work[j], self.order_work[i]
        self._paint()

    async def action_commit(self) -> None:
        if self.mode != "order" or self.busy:
            return
        coll, order = self.order_coll, list(self.order_work)
        self.mode, self.order_coll, self.order_work = "browse", None, []
        self.busy = "ordering…"
        self._paint()
        await set_collection_order(self.queue, self.graph_capability, coll, order,
                                   self.actor, journal_path=self.journal_path)
        await self._reload()

    async def action_launch(self, which: str) -> None:
        row = self._focused()
        if self.mode != "browse" or self.editing or self.busy:
            return
        cmd = list(self.LAUNCH_COMMANDS[which])
        if which == "correction":
            if not row or row["kind"] != "source":
                self.error = "focus a source row to open it in the correction TUI"
                self._paint()
                return
            cmd.append(row["id"])
        try:
            with self.suspend():
                subprocess.run(cmd)
        except FileNotFoundError:
            self.error = f"{cmd[0]} not installed in this environment"
            self._paint()
            return
        except Exception as e:
            self.error = f"launch failed: {e}"
            self._paint()
            return
        await self._reload()

    def action_cancel(self) -> None:
        if self.editing:
            self._close_editor()
        elif self.mode == "order":
            self.mode, self.order_coll, self.order_work = "browse", None, []
        self.error = None
        self._paint()

    async def action_reload(self) -> None:
        if self.mode == "browse" and not self.editing and not self.busy:
            await self._reload()

    async def action_quit_app(self) -> None:
        await self._teardown()
        self.exit(None)

    async def _teardown(self) -> None:
        if self.queue is not None:
            try:
                await self.queue.stop()
            except Exception:
                pass
        if self.manager is not None:
            try:
                self.manager.unload_capability(self.graph_capability)
            except Exception:
                pass

    def on_resize(self, event) -> None:
        self._paint()
