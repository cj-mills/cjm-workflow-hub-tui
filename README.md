# cjm-workflow-hub-tui

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

_No purpose recorded on-graph yet — author it with_ `assert e77a7cd6-290b-55c9-a3b0-f782e7ab0da1 purpose "…"` _(or by the repo's entity key)._

## Modules

- **`cjm_workflow_hub_tui.app`**
- **`cjm_workflow_hub_tui.cli`**
- **`cjm_workflow_hub_tui.spine`**

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
