# cjm-workflow-hub-tui

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

The transcription workspace's front door — one keyboard surface answering 'what is in this workspace and where is each source in the pipeline'. Paints the graph spine's grouped rows (collections with flagged proposals, per-source stage-at-a-glance status across transcription -> decomposition -> correction), launches the stage TUIs on a source (each resolved into its own core's conda env, via Textual suspend), and drives the curation vocabulary: confirm, file/refile, rename-or-merge, and collection ordering. Every curation commit rides the graph db's sidecar journal (DEC ccbab9f5) so the workspace stays rebuildable; batch runs hand off to the decomp core with the confirmed plan's flags (including --sentence-split). Hub v0 shipped under DEC 66d35baa / e5849229; hub-drive findings shape v0.1.

## Modules

- **`cjm_workflow_hub_tui`**
- **`cjm_workflow_hub_tui.app`** — The workspace front door (hub v0, e5849229): one keyboard surface answering
- **`cjm_workflow_hub_tui.cli`** — The console-script driver (cjm-workflow-hub): resolve the workspace, export
- **`cjm_workflow_hub_tui.spine`** — The hub's spine: pure/graph logic below the paint path (sources.py precedent

## API

### `cjm_workflow_hub_tui.app`

- `HubApp` _class_ — The hub surface: grouped browse + curation gestures + stage-TUI launch.

### `cjm_workflow_hub_tui.cli`

- `build_parser` _function_ — The hub driver's argument surface (everything else the workspace answers).
- `main` _function_ — Resolve the workspace, export it, run the hub.

### `cjm_workflow_hub_tui.spine`

- `HubData` _class_ — Everything one hub reload pulls off the graph (paint-ready inputs).
- `build_rows` _function_ — The grouped listing: collection headers (⚑ when proposed) with their
- `correction_status` _function_ — Correction-layer status per source (the correction TUI's source_status
- `fetch_pipeline_status` _function_ — The four bulk layer projections, joined (`join_pipeline_status`).
- `join_pipeline_status` _function_ — Join the four bulk layer projections into per-source pipeline counts.
- `list_sources` _function_ — Enumerate the graph's Source nodes (CARRIED COPY, see `open_stack`).
- `load_hub_data` _function_ — One reload: collections + membership + order + sources + status.
- `open_stack` _function_ — Bootstrap the graph capability stack, resolving the db path.
- `resolve_stage_tui` _function_ — Resolve a stage TUI's executable across the CORE-ENV pattern.
- `stage_glance` _function_ — Stage-at-a-glance for one source row (pure; spans are the app's job).

## Dependencies

**Depends on:** `cjm-context-graph-layer`, `cjm-context-graph-primitives`, `cjm-substrate-tui-kit`, `cjm-transcript-correction-core`, `cjm-transcript-graph-schema`, `cjm-transcription-core`, `textual`
