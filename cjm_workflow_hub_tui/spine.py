"""The hub's spine: pure/graph logic below the paint path (sources.py precedent
— everything that CAN live below the paint path SHOULD). Composes the graph
rungs (stack open, source/collection reads via transcription-core's curation
vocabulary, 4-bulk-query pipeline-status join) into the grouped row model the
app paints. The stack-open trio is a deliberate CARRIED COPY of
cjm_transcript_correction_tui.spine's rungs (N=2, decomp-TUI discovery.py
precedent: kept near-verbatim so the contract cannot fork before the c3c21f99
shared-scaffolding home decision moves BOTH)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cjm_context_graph_layer.ops import graph_task
from cjm_context_graph_primitives.query import NodeQuery
from cjm_substrate.core.manager import CapabilityManager
from cjm_substrate.core.queue import JobQueue
from cjm_transcript_correction_core.graph import (active_corrections, load_source_corrections,
                                                  open_marks)
from cjm_transcript_graph_schema.schema import TranscriptGraphLabels
from cjm_transcription_core.cli import load_capabilities
from cjm_transcription_core.curation import collection_members, collection_order, list_collections


async def open_stack(
    graph_db_path: Optional[str],            # Explicit graph db, or None = the workspace answers
    *, manifests_dir: str = ".cjm/manifests",  # Capability manifests directory
    graph_capability: str = "cjm-capability-graph-sqlite",
) -> Tuple[CapabilityManager, JobQueue, str]:  # (manager, started queue, effective db path)
    """Bootstrap the graph capability stack, resolving the db path.

    CARRIED COPY of cjm_transcript_correction_tui.spine.open_stack (2ce81638
    shape; N=2 — near-verbatim per the decomp-TUI discovery.py precedent, both
    move together at the c3c21f99 home decision). Explicit path > the
    capability's PERSISTED config (workspace-scoped under CJM_WORKSPACE,
    5daadfc4); none anywhere = loud refusal naming both outs."""
    manager = CapabilityManager(search_paths=[Path(manifests_dir)])
    configs = ({graph_capability: {"db_path": str(graph_db_path)}}
               if graph_db_path else None)
    load_capabilities(manager, [graph_capability], configs=configs)
    effective = graph_db_path or (
        (manager.instances[graph_capability].config or {}).get("db_path"))
    if not effective:
        raise ValueError(
            f"no graph db path: pass --graph-db-path, or persist one on "
            f"{graph_capability} in the active workspace's config store")
    queue = JobQueue(deps=manager)
    await queue.start()
    return manager, queue, str(effective)


async def list_sources(
    queue: JobQueue,      # Started queue over the loaded graph capability
    graph_id: str,        # The graph capability name
) -> List[Tuple[str, str]]:  # [(source_id, title)] in query order
    """Enumerate the graph's Source nodes (CARRIED COPY, see `open_stack`)."""
    sq = NodeQuery(label=TranscriptGraphLabels.SOURCE, project=["title"])
    res = await graph_task(queue, graph_id, "query_nodes", query=sq.to_dict())
    return [(r["id"], str(r.get("title") or "")) for r in (res.rows or [])]


def join_pipeline_status(
    asegs: List[Dict[str, Any]],        # AudioSegment rows: {"id", "source_id"}
    rends: List[Dict[str, Any]],        # AudioRendition rows: {"id", "audio_segment_id"}
    transcripts: List[Dict[str, Any]],  # Transcript rows: {"id", "rendition_id"}
    fsegs: List[Dict[str, Any]],        # Segment rows: {"id", "rendition_id"}
) -> Dict[str, Dict[str, int]]:  # source_id -> {"audio_segs", "transcripts", "fine_segs"}
    """Join the four bulk layer projections into per-source pipeline counts.

    Pure — the join walks Segment/Transcript -> rendition -> AudioSegment ->
    source entirely client-side, so status for EVERY source costs four bulk
    queries total instead of a per-source query fan-out. Stage-at-a-glance
    derives: transcribed = transcripts > 0, decomposed = fine_segs > 0."""
    aseg_src = {a["id"]: a.get("source_id") for a in asegs}
    rend_src = {r["id"]: aseg_src.get(r.get("audio_segment_id")) for r in rends}
    out: Dict[str, Dict[str, int]] = {}

    def bump(source_id: Optional[str], key: str) -> None:
        if source_id:
            out.setdefault(source_id, {"audio_segs": 0, "transcripts": 0,
                                       "fine_segs": 0})[key] += 1

    for a in asegs:
        bump(a.get("source_id"), "audio_segs")
    for t in transcripts:
        bump(rend_src.get(t.get("rendition_id")), "transcripts")
    for s in fsegs:
        bump(rend_src.get(s.get("rendition_id")), "fine_segs")
    return out


async def fetch_pipeline_status(
    queue: JobQueue,   # Started queue over the loaded graph capability
    graph_id: str,     # The graph capability name
) -> Dict[str, Dict[str, int]]:  # source_id -> {"audio_segs", "transcripts", "fine_segs"}
    """The four bulk layer projections, joined (`join_pipeline_status`)."""
    async def rows(label: str, props: List[str]) -> List[Dict[str, Any]]:
        q = NodeQuery(label=label, project=props)
        res = await graph_task(queue, graph_id, "query_nodes", query=q.to_dict())
        return list(res.rows or [])

    return join_pipeline_status(
        await rows(TranscriptGraphLabels.AUDIO_SEGMENT, ["source_id"]),
        await rows(TranscriptGraphLabels.AUDIO_RENDITION, ["audio_segment_id"]),
        await rows(TranscriptGraphLabels.TRANSCRIPT, ["rendition_id"]),
        await rows(TranscriptGraphLabels.SEGMENT, ["rendition_id"]))


async def correction_status(
    queue: JobQueue,        # Started queue over the loaded graph capability
    graph_id: str,          # The graph capability name
    source_ids: List[str],  # Sources to summarize (callers pass only decomposed ones)
) -> Dict[str, Dict[str, int]]:  # source_id -> {"corrections": active, "marks": open}
    """Correction-layer status per source (the correction TUI's source_status
    semantics: ACTIVE set after supersession, OPEN marks).

    Per-source reads by necessity — the active/open computations are
    correction-core vocabulary; callers keep this cheap by passing only the
    sources that HAVE a fine spine (correction is meaningless before decomp)."""
    out: Dict[str, Dict[str, int]] = {}
    for sid in source_ids:
        corrections, superseded = await load_source_corrections(queue, graph_id, sid)
        out[sid] = {"corrections": len(active_corrections(corrections, superseded)),
                    "marks": len(open_marks(corrections, superseded))}
    return out


@dataclass
class HubData:
    """Everything one hub reload pulls off the graph (paint-ready inputs)."""
    collections: List[Dict[str, Any]] = field(default_factory=list)  # [{"id","title","status"}]
    members: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # coll_id -> [(src_id, title)]
    order: Dict[str, List[str]] = field(default_factory=dict)         # coll_id -> ordered member ids
    sources: List[Tuple[str, str]] = field(default_factory=list)      # ALL sources [(id, title)]
    status: Dict[str, Dict[str, int]] = field(default_factory=dict)   # src -> pipeline+correction counts


async def load_hub_data(
    queue: JobQueue,   # Started queue over the loaded graph capability
    graph_id: str,     # The graph capability name
) -> HubData:
    """One reload: collections + membership + order + sources + status."""
    data = HubData()
    data.sources = await list_sources(queue, graph_id)
    data.collections = await list_collections(queue, graph_id)
    for c in data.collections:
        members = await collection_members(queue, graph_id, c["id"])
        data.members[c["id"]] = members
        ordered, _ = await collection_order(queue, graph_id, c["id"],
                                            [m for m, _ in members])
        data.order[c["id"]] = ordered
    data.status = await fetch_pipeline_status(queue, graph_id)
    decomposed = [s for s, st in data.status.items() if st.get("fine_segs")]
    for sid, corr in (await correction_status(queue, graph_id, decomposed)).items():
        data.status.setdefault(sid, {}).update(corr)
    return data


def build_rows(
    data: HubData,  # One reload's graph pulls
) -> List[Dict[str, Any]]:  # Flat paint rows: {"kind": "collection"|"source", ...}
    """The grouped listing: collection headers (⚑ when proposed) with their
    members — chain order first, unordered tail alphabetical — then every
    unfiled source under a synthetic Unfiled header. Pure; the app paints
    windows of it and the cursor indexes into it."""
    rows: List[Dict[str, Any]] = []
    filed: set = set()
    titles = dict(data.sources)
    for c in sorted(data.collections, key=lambda c: c["title"].lower()):
        members = data.members.get(c["id"], [])
        rows.append({"kind": "collection", "id": c["id"], "title": c["title"],
                     "status": c["status"], "count": len(members)})
        ordered = [m for m in data.order.get(c["id"], []) if m in {i for i, _ in members}]
        tail = sorted((i for i, _ in members if i not in set(ordered)),
                      key=lambda i: (titles.get(i) or "").lower())
        for pos, sid in enumerate(ordered + tail):
            rows.append({"kind": "source", "id": sid,
                         "title": titles.get(sid) or dict(members).get(sid) or sid,
                         "coll_id": c["id"],
                         "ordered": pos < len(ordered),
                         "counts": data.status.get(sid, {})})
            filed.add(sid)
    unfiled = [(i, t) for i, t in data.sources if i not in filed]
    if unfiled:
        rows.append({"kind": "collection", "id": None, "title": "Unfiled",
                     "status": "none", "count": len(unfiled)})
        for sid, title in sorted(unfiled, key=lambda p: p[1].lower()):
            rows.append({"kind": "source", "id": sid, "title": title,
                         "coll_id": None, "ordered": False,
                         "counts": data.status.get(sid, {})})
    return rows


def stage_glance(
    counts: Dict[str, int],  # One source's status counts (possibly empty)
) -> str:  # e.g. "T·D·C 214segs 3corr 1⚑" — the source row's status suffix
    """Stage-at-a-glance for one source row (pure; spans are the app's job).

    T = transcribed (coarse spine + at least one Transcript), D = decomposed
    (fine spine exists), C = corrected (active corrections); lowercase = that
    stage hasn't happened. Counts append only when they say something."""
    t = "T" if counts.get("transcripts") else "t"
    d = "D" if counts.get("fine_segs") else "d"
    c = "C" if counts.get("corrections") else "c"
    bits = [f"{t}{d}{c}"]
    if counts.get("fine_segs"):
        bits.append(f"{counts['fine_segs']}segs")
    if counts.get("corrections"):
        bits.append(f"{counts['corrections']}corr")
    if counts.get("marks"):
        bits.append(f"{counts['marks']}⚑")
    return " ".join(bits)
