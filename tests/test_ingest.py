import json

from fakes import VTT, FakeClient, chapters, entry
from peb.ingest import FAILED, ingest, merge_manifest, pick_caption_track

A, B, C = "aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"


def pairs(manifest):
    return [(e["index"], e["videoId"]) for e in manifest]


def test_merge_manifest_first_run_numbers_in_playlist_order():
    manifest, missing = merge_manifest([], [entry(A), entry(B)])
    assert pairs(manifest) == [(1, A), (2, B)]
    assert missing == []


def test_merge_manifest_keeps_pinned_indices_when_playlist_reorders():
    existing, _ = merge_manifest([], [entry(A), entry(B)])
    manifest, _ = merge_manifest(existing, [entry(B), entry(A)])
    assert pairs(manifest) == [(1, A), (2, B)]


def test_merge_manifest_appends_new_videos_and_reports_missing_ones():
    existing, _ = merge_manifest([], [entry(A), entry(B)])
    manifest, missing = merge_manifest(existing, [entry(B), entry(C)])
    assert pairs(manifest) == [(1, A), (2, B), (3, C)]
    assert missing == [A]


def test_pick_caption_track_prefers_manual_english():
    assert pick_caption_track({"subtitles": ["en-GB"], "automatic_captions": ["en-orig", "en"]}) == ("en-GB", False)


def test_pick_caption_track_automatic_prefers_en_orig():
    assert pick_caption_track({"subtitles": [], "automatic_captions": ["de", "en", "en-orig"]}) == ("en-orig", True)


def test_pick_caption_track_falls_back_to_any_english_variant():
    assert pick_caption_track({"subtitles": [], "automatic_captions": ["en-AU", "fr"]}) == ("en-AU", True)


def test_pick_caption_track_without_english_is_none():
    assert pick_caption_track({"subtitles": ["fr"], "automatic_captions": ["de"]}) is None


def run(tmp_path, client, **kw):
    kw.setdefault("sleep", lambda seconds: None)
    return ingest(client, "playlist-url", tmp_path / "sources", **kw)


def test_ingest_writes_manifest_metadata_captions_and_transcript(tmp_path):
    results = run(tmp_path, FakeClient([A]))
    folder = tmp_path / "sources" / f"01-{A}"
    assert results == [{"index": 1, "videoId": A, "status": "ok", "detail": "en-orig (auto)"}]
    assert json.loads((tmp_path / "sources" / "playlist.json").read_text(encoding="utf-8"))[0]["index"] == 1
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert len(meta["questionChapters"]) == 20
    assert meta["questionChapters"][0] == {"q": 1, "startSec": 10, "endSec": 20, "title": "Topic 1 – é"}
    assert (folder / "captions.vtt").read_text(encoding="utf-8") == VTT
    transcript = (folder / "transcript.txt").read_text(encoding="utf-8")
    assert "[0:00:01] hello there" in transcript
    assert "=== Q01 [0:00:10–0:00:20] Topic 1 – é ===" in transcript


def test_ingest_skips_already_ingested_videos_unless_forced(tmp_path):
    client = FakeClient([A])
    run(tmp_path, client)
    assert run(tmp_path, client)[0]["detail"] == "skipped (already ingested)"
    assert len(client.downloads) == 1
    run(tmp_path, client, force=True)
    assert len(client.downloads) == 2


def test_ingest_reports_no_captions(tmp_path):
    info = {"durationSec": 210, "chapters": chapters(20), "subtitles": [], "automatic_captions": ["fr"]}
    assert run(tmp_path, FakeClient([A], infos={A: info}))[0]["status"] == "no-captions"
    assert not (tmp_path / "sources" / f"01-{A}" / "transcript.txt").exists()


def test_ingest_reports_chapter_mismatch_but_keeps_transcript(tmp_path):
    info = {"durationSec": 210, "chapters": chapters(19), "subtitles": [], "automatic_captions": ["en"]}
    result = run(tmp_path, FakeClient([A], infos={A: info}))[0]
    assert result["status"] == "chapter-mismatch"
    assert "19 question chapters" in result["detail"]
    assert (tmp_path / "sources" / f"01-{A}" / "transcript.txt").exists()


def test_ingest_reports_errors_per_video_and_continues(tmp_path):
    results = run(tmp_path, FakeClient([A, B], fail=[A]))
    assert [(r["videoId"], r["status"]) for r in results] == [(A, "error"), (B, "ok")]
    assert "429" in results[0]["detail"]


def test_ingest_sleeps_between_fetched_videos_only(tmp_path):
    sleeps = []
    run(tmp_path, FakeClient([A, B, C]), delay=2.5, sleep=sleeps.append)
    assert sleeps == [2.5, 2.5]


def test_ingest_reports_videos_missing_from_playlist(tmp_path):
    run(tmp_path, FakeClient([A, B]))
    results = run(tmp_path, FakeClient([B]))
    assert [(r["videoId"], r["status"]) for r in results] == [(A, "missing"), (B, "ok")]


def test_failed_statuses():
    assert FAILED == {"no-captions", "chapter-mismatch", "error"}
