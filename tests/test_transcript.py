from pathlib import Path

from peb.transcript import (
    Line, anchor_window, clean_vtt, find_anchor_start, normalize,
    parse_transcript, question_chapters, render_transcript, spoken_question_chapters,
)

FIXTURE = Path(__file__).parent / "fixtures" / "youtube-auto.vtt"


def test_clean_vtt_dedupes_youtube_rolling_captions():
    assert clean_vtt(FIXTURE.read_text(encoding="utf-8")) == [
        Line(0, "Hello and welcome, I'm your host"),
        Line(3, "recording from a small home studio"),
        Line(5, "somewhere in the hills."),
        Line(8, "This series walks through sample questions for a"),
        Line(11, "cloud exam, one topic at a time today"),
    ]


def test_clean_vtt_strips_tags_and_decodes_entities():
    vtt = "WEBVTT\n\n00:01:05.000 --> 00:01:07.000\nQ&amp;A <c.colorE5E5E5>time</c>\n"
    assert clean_vtt(vtt) == [Line(65, "Q&A time")]


def test_question_chapters_drop_leading_intro_and_number_from_one():
    chapters = [
        {"startSec": 0, "endSec": 65, "title": "Introduction and setup"},
        {"startSec": 65, "endSec": 339, "title": "Managing application secrets"},
        {"startSec": 339, "endSec": 600, "title": "KMS envelope encryption"},
    ]
    assert question_chapters(chapters) == [
        {"q": 1, "startSec": 65, "endSec": 339, "title": "Managing application secrets"},
        {"q": 2, "startSec": 339, "endSec": 600, "title": "KMS envelope encryption"},
    ]


def test_question_chapters_keep_first_chapter_when_not_intro():
    assert question_chapters([{"startSec": 0, "endSec": 60, "title": "Lambda layers"}])[0]["q"] == 1


def test_question_chapters_of_no_chapters_is_empty():
    assert question_chapters([]) == []


CH = [
    {"q": 1, "startSec": 65, "endSec": 339, "title": "Managing secrets – café"},
    {"q": 2, "startSec": 339, "endSec": 600, "title": "KMS envelope encryption"},
]


def test_render_inserts_chapter_headers_before_first_line_at_or_after_start():
    lines = [Line(10, "intro talk"), Line(64, "Question one."), Line(66, "A company runs"), Line(340, "Question two")]
    assert render_transcript(lines, CH).splitlines() == [
        "[0:00:10] intro talk",
        "[0:01:04] Question one.",
        "=== Q01 [0:01:05–0:05:39] Managing secrets – café ===",
        "[0:01:06] A company runs",
        "=== Q02 [0:05:39–0:10:00] KMS envelope encryption ===",
        "[0:05:40] Question two",
    ]


def test_render_appends_headers_for_chapters_after_last_line():
    assert render_transcript([Line(1, "hi")], CH).splitlines()[-1].startswith("=== Q02")


def test_parse_transcript_round_trips_lines_and_skips_headers():
    lines = [Line(64, "Question one."), Line(66, "A company runs")]
    assert parse_transcript(render_transcript(lines, CH)) == lines


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("  AWS  Lambda's   (limits)! ") == "aws lambda s limits"


LINES = [
    Line(64, "started. Question one. A team hosts"),
    Line(66, "an inventory service on Amazon"),
    Line(70, "EC2 instances behind a load balancer."),
]


def test_find_anchor_start_spans_lines_and_returns_start_of_first_line():
    assert find_anchor_start(LINES, "A team hosts an inventory service") == 64


def test_find_anchor_start_returns_line_where_match_begins():
    assert find_anchor_start(LINES, "inventory service on Amazon EC2 instances") == 66


def test_find_anchor_start_matches_whole_words_only():
    assert find_anchor_start([Line(0, "problem 10 today")], "problem 1 today") is None


def test_find_anchor_start_missing_returns_none():
    assert find_anchor_start(LINES, "something never said") is None


def test_anchor_window_leads_chapter_by_15_seconds_and_clamps_at_zero():
    assert anchor_window({"startSec": 339, "endSec": 600}) == (324, 585)
    assert anchor_window({"startSec": 5, "endSec": 60}) == (0, 45)


SPOKEN = [
    Line(0, "Welcome to part three."),
    Line(14, "Question 41. A company runs"),
    Line(20, "an app. Option A is incorrect."),
    Line(100, "as we saw, question 41 matters. Question"),
    Line(101, "42. A developer needs"),
    Line(200, "Question 43. Which solution"),
]


def test_spoken_question_chapters_follow_markers_in_order_even_across_lines():
    assert spoken_question_chapters(SPOKEN, 41, 3, 300) == [
        {"q": 1, "startSec": 14, "endSec": 100, "title": "Question 41"},
        {"q": 2, "startSec": 100, "endSec": 200, "title": "Question 42"},
        {"q": 3, "startSec": 200, "endSec": 300, "title": "Question 43"},
    ]


def test_spoken_question_chapters_stop_at_first_missing_number():
    assert [c["title"] for c in spoken_question_chapters(SPOKEN, 41, 5, 300)] == ["Question 41", "Question 42", "Question 43"]


def test_spoken_question_chapters_match_whole_numbers_only():
    assert spoken_question_chapters([Line(0, "Question 410 is not it")], 41, 1, 60) == []
