"""Tests for the hub's pure logic — the status join, the grouped row model,
and the stage-at-a-glance rendering (paint-path strings verify by pilot probe,
per the standing TUI craft)."""

from cjm_workflow_hub_tui.spine import (HubData, build_rows, join_pipeline_status,
                                        stage_glance)


def test_join_pipeline_status():
    asegs = [{"id": "a1", "source_id": "s1"}, {"id": "a2", "source_id": "s1"},
             {"id": "a3", "source_id": "s2"}]
    rends = [{"id": "r1", "audio_segment_id": "a1"},
             {"id": "r2", "audio_segment_id": "a2"},
             {"id": "r3", "audio_segment_id": "a3"}]
    transcripts = [{"id": "t1", "rendition_id": "r1"},
                   {"id": "t2", "rendition_id": "r1"},
                   {"id": "t3", "rendition_id": "r2"}]
    fsegs = [{"id": "f1", "rendition_id": "r1"}, {"id": "f2", "rendition_id": "r1"}]
    st = join_pipeline_status(asegs, rends, transcripts, fsegs)
    assert st["s1"] == {"audio_segs": 2, "transcripts": 3, "fine_segs": 2}
    assert st["s2"] == {"audio_segs": 1, "transcripts": 0, "fine_segs": 0}
    # orphan rows (unknown rendition/segment parents) never crash the join
    st2 = join_pipeline_status(asegs, rends, [{"id": "tx", "rendition_id": "gone"}],
                               [{"id": "fx", "rendition_id": None}])
    assert "gone" not in st2 and None not in st2


def test_build_rows_grouping_order_and_unfiled():
    data = HubData(
        collections=[{"id": "cB", "title": "Beta Series", "status": "confirmed"},
                     {"id": "cA", "title": "Alpha Book", "status": "proposed"}],
        members={"cA": [("s2", "Chapter 2"), ("s1", "Chapter 1")],
                 "cB": [("s3", "Ep Z"), ("s4", "Ep A")]},
        order={"cA": ["s1", "s2"], "cB": []},
        sources=[("s1", "Chapter 1"), ("s2", "Chapter 2"), ("s3", "Ep Z"),
                 ("s4", "Ep A"), ("s5", "Loose File")],
        status={"s1": {"transcripts": 2, "fine_segs": 5}})
    rows = build_rows(data)
    kinds = [(r["kind"], r["title"]) for r in rows]
    # collections alpha-sorted; ordered members ride the chain, unordered alpha;
    # unfiled sources land under the synthetic tail header
    assert kinds == [("collection", "Alpha Book"),
                     ("source", "Chapter 1"), ("source", "Chapter 2"),
                     ("collection", "Beta Series"),
                     ("source", "Ep A"), ("source", "Ep Z"),
                     ("collection", "Unfiled"), ("source", "Loose File")]
    assert rows[0]["status"] == "proposed" and rows[0]["count"] == 2
    assert rows[1]["ordered"] is True and rows[2]["ordered"] is True
    assert rows[4]["ordered"] is False, "no chain = alpha tail, never fabricated order"
    assert rows[7]["coll_id"] is None
    assert rows[1]["counts"] == {"transcripts": 2, "fine_segs": 5}

    # a partial chain: reachable members first, the rest alpha
    data.order["cA"] = ["s2"]
    rows = build_rows(data)
    assert [r["title"] for r in rows[1:3]] == ["Chapter 2", "Chapter 1"]
    assert rows[1]["ordered"] is True and rows[2]["ordered"] is False


def test_stage_glance():
    assert stage_glance({}) == "tdc"
    assert stage_glance({"transcripts": 2}) == "Tdc"
    full = stage_glance({"transcripts": 2, "fine_segs": 214,
                         "corrections": 3, "marks": 1})
    assert full == "TDC 214segs 3corr 1⚑"
    assert stage_glance({"fine_segs": 7}) == "tDc 7segs"
