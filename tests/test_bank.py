import json

import pytest

from factory import anchor_text, make_root, rewrite, video_id
from peb.bank import load_bank, validate_bank

Q1 = f"{video_id(1)}-q01"


def bank1(root):
    return root / "bank" / f"01-{video_id(1)}.json"


def errors(root, files=None):
    return [v for v in validate_bank(root, files) if not v.warning]


def messages(root, files=None):
    return [f"{v.qid}: {v.message}" for v in errors(root, files)]


def first(mutate):
    return lambda b: mutate(b["questions"][0])


def test_valid_bank_has_no_violations(tmp_path):
    assert validate_bank(make_root(tmp_path)) == []


@pytest.mark.parametrize("mutate,expected", [
    (first(lambda q: q.update(domain=5)), f"{Q1}: domain must be 1-4"),
    (first(lambda q: q.update(domain=True)), f"{Q1}: domain must be 1-4"),
    (first(lambda q: q.update(selectN=True)), f"{Q1}: selectN must be 1 or 2"),
    (first(lambda q: q.update(task="2.1")), f"{Q1}: task '2.1' is not a task of domain 1"),
    (first(lambda q: q.update(selectN=3)), f"{Q1}: selectN must be 1 or 2"),
    (first(lambda q: q.update(correct=["B", "C"])), f"{Q1}: correct must list selectN distinct keys"),
    (first(lambda q: q.update(correct=["E"])), f"{Q1}: correct references a missing option"),
    (first(lambda q: q.update(options=q["options"][:3])), f"{Q1}: options must have 4-6 entries"),
    (first(lambda q: q["options"][1].update(k="C")), f"{Q1}: option keys must be A, B, C… in order"),
    (first(lambda q: q["options"][2].update(why=" ")), f"{Q1}: option C needs non-empty t and why"),
    (first(lambda q: q.update(topic="")), f"{Q1}: topic must be non-empty"),
    (first(lambda q: q.update(anchor="too short")), f"{Q1}: anchor must be 6-12 words"),
    (first(lambda q: q.update(n=99)), f"{Q1}: n must be 1"),
    (first(lambda q: q.update(id="wrong")), f"wrong: id must be {Q1}"),
    (first(lambda q: q.update(videoId="x")), f"{Q1}: video/videoId do not match file"),
    (first(lambda q: q.update(chapterTitle="Other")), f"{Q1}: chapterTitle must be 'Topic 1-1 – café'"),
    (first(lambda q: q.update(timestampSec=5)), f"{Q1}: timestampSec must be 200"),
    (first(lambda q: q.update(anchor="words that were never said in this video")),
     f"{Q1}: anchor not found in transcript"),
    (first(lambda q: q.update(anchor=anchor_text(1, 2))),
     f"{Q1}: anchor first occurs at 0:06:41, outside chapter window 0:03:05–0:06:25"),
    (lambda b: b.update(video=2), "-: video/videoId do not match filename"),
    (lambda b: b.update(title=""), "-: title must be non-empty"),
    (lambda b: b["questions"].pop(), "-: has 19 questions, expectedCount is 20"),
])
def test_rule_violations_are_reported(tmp_path, mutate, expected):
    root = make_root(tmp_path)
    rewrite(bank1(root), mutate)
    assert expected in messages(root)


def test_choose_two_question_with_five_options_is_valid(tmp_path):
    root = make_root(tmp_path)

    def choose_two(q):
        q["options"].append({"k": "E", "t": "Option E", "why": "Why E"})
        q.update(selectN=2, correct=["B", "E"])
    rewrite(bank1(root), first(choose_two))
    assert errors(root) == []


def test_non_default_expected_count_needs_a_note_then_warns(tmp_path):
    root = make_root(tmp_path)
    rewrite(bank1(root), lambda b: (b["questions"].pop(), b.update(expectedCount=19)))
    assert "-: expectedCount 19 requires a countNote" in messages(root)
    rewrite(bank1(root), lambda b: b.update(countNote="Chapter 20 is a recap with no question"))
    assert errors(root) == []
    warnings = [v for v in validate_bank(root) if v.warning]
    assert len(warnings) == 1 and "recap" in warnings[0].message


def test_filename_must_match_pattern(tmp_path):
    root = make_root(tmp_path)
    bank1(root).rename(root / "bank" / "1-bad.json")
    assert "-: filename must be <nn>-<videoId>.json" in messages(root)


def test_unreadable_json_is_reported(tmp_path):
    root = make_root(tmp_path)
    bank1(root).write_text("{", encoding="utf-8")
    assert any("unreadable JSON" in m for m in messages(root))


def test_missing_sources_are_reported(tmp_path):
    root = make_root(tmp_path)
    (root / "sources" / f"01-{video_id(1)}" / "transcript.txt").unlink()
    assert "-: missing sources metadata.json/transcript.txt" in messages(root)


def test_duplicate_stems_across_files_are_reported(tmp_path):
    root = make_root(tmp_path)
    stem = json.loads(bank1(root).read_text(encoding="utf-8"))["questions"][0]["stem"]
    rewrite(root / "bank" / f"02-{video_id(2)}.json", lambda b: b["questions"][3].update(stem=stem.upper() + "!"))
    assert any("duplicate stem" in m for m in messages(root))


def test_partial_validation_skips_quota_check(tmp_path):
    root = make_root(tmp_path, videos=1)
    assert errors(root, [bank1(root)]) == []
    assert "-: domain 1 has 6 questions; an exam needs 21" in messages(root)


def test_violation_str_format(tmp_path):
    root = make_root(tmp_path)
    rewrite(bank1(root), first(lambda q: q.update(domain=5)))
    assert str(errors(root)[0]) == f"01-{video_id(1)}.json {Q1} : domain must be 1-4"


def test_load_bank_returns_videos_and_questions_in_global_order(tmp_path):
    videos, questions = load_bank(make_root(tmp_path, videos=2))
    assert videos == [{"index": 1, "videoId": video_id(1), "title": "Part 1"},
                      {"index": 2, "videoId": video_id(2), "title": "Part 2"}]
    assert [q["n"] for q in questions] == list(range(1, 41))


def test_spoken_source_allows_extractor_written_chapter_title(tmp_path):
    root = make_root(tmp_path)
    rewrite(root / "sources" / f"01-{video_id(1)}" / "metadata.json", lambda m: m.update(questionSource="spoken"))
    rewrite(bank1(root), first(lambda q: q.update(chapterTitle="Managing application secrets")))
    assert errors(root) == []


def test_spoken_source_still_requires_timestamp_and_anchor_window(tmp_path):
    root = make_root(tmp_path)
    rewrite(root / "sources" / f"01-{video_id(1)}" / "metadata.json", lambda m: m.update(questionSource="spoken"))
    rewrite(bank1(root), first(lambda q: q.update(timestampSec=5)))
    assert f"{Q1}: timestampSec must be 200" in messages(root)


def make_duplicate(root):
    """Video 2 q04 repeats video 1 q01's stem."""
    stem = json.loads(bank1(root).read_text(encoding="utf-8"))["questions"][0]["stem"]
    rewrite(root / "bank" / f"02-{video_id(2)}.json", lambda b: b["questions"][3].update(stem=stem))


def test_duplicate_stem_hint_names_the_earliest_question(tmp_path):
    root = make_root(tmp_path)
    make_duplicate(root)
    assert f'{video_id(2)}-q04: duplicate stem (same as {Q1}); mark the later one "duplicateOf": "{Q1}"' in messages(root)


def test_duplicate_marked_with_duplicate_of_is_valid(tmp_path):
    root = make_root(tmp_path)
    make_duplicate(root)
    rewrite(root / "bank" / f"02-{video_id(2)}.json", lambda b: b["questions"][3].update(duplicateOf=Q1))
    assert errors(root) == []


@pytest.mark.parametrize("target", ["nope-q01", f"{video_id(1)}-q02", f"{video_id(3)}-q01"])
def test_duplicate_of_must_reference_an_earlier_question_with_the_same_stem(tmp_path, target):
    root = make_root(tmp_path)
    make_duplicate(root)
    rewrite(root / "bank" / f"02-{video_id(2)}.json", lambda b: b["questions"][3].update(duplicateOf=target))
    assert f"{video_id(2)}-q04: duplicateOf must reference an earlier question with the same stem" in messages(root)
