# DVA-C02 Practice Exam Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local pipeline that ingests the 25-video DVA-C02 YouTube playlist, holds the 500 faithfully extracted questions in a validated bank, and builds one offline HTML study app. The app offers a no-repeat practice mode, a weighted 65-question timed exam, and persistent accuracy statistics.

**Architecture:** Python package `peb` (`src/peb/`) with four commands:
- `ingest`: yt-dlp subprocess → `sources/`
- extraction: Claude Code subagents write `bank/*.json` from the transcripts
- `validate`: bank rules plus source cross-checks
- `build`: injects the bank and the pure-JS core into `template/app.html`, writing `dist/dva-c02-practice.html`

All app logic that can be pure lives in `template/app-core.js`, which is tested with `node --test`. `app.html` holds only DOM wiring.

**Tech Stack:**
- Python ≥ 3.12 (the machine has 3.14) and pytest
- yt-dlp 2026.8.19, called as a subprocess
- Vanilla JS (ES2020), with no npm dependencies, tested via Node 22's `node:test`
- A single self-contained HTML/CSS file

**Spec:** `docs/superpowers/specs/2026-09-30-dva-c02-practice-exam-builder-design.md`. Read it before starting any task.

## Global Constraints

**Commands and dependencies**
- Run every command from the project root: `C:\Users\user\Software Development\LiminalArc\practice-exam-builder`.
- Use the Bash tool (Git Bash), with the venv Python at `.venv/Scripts/python`.
- Runtime dependency: only `yt-dlp==2026.8.19`. Dev dependency: only `pytest`. No other packages.
- JavaScript: no npm, no `package.json`, no bundler. Tests run with `node --test tests-js/`.

**File I/O**
- Every Python file read or write passes `encoding="utf-8"` explicitly. Windows defaults to cp1252.
- JSON is written with `ensure_ascii=False`.

**The built app**
- Must work offline from `file://`, with no external scripts, fonts or stylesheets. The only network use is YouTube links the user clicks.
- Title is exactly `DVA-C02 Practice (unofficial)`, with no AWS logos.
- Palette tokens:
  - squid ink `#232F3E` / `#161E2D`
  - orange `#FF9900`, hover `#EC7211`
  - background `#F2F3F3`, borders `#D5DBDB`
  - correct `#1D8102` on `#F2FCF3`
  - incorrect `#D13212` on `#FDF3F1`

**Exam and data constants**
- Exam: 65 questions, 130 minutes, pass line 72%. Domain quotas 21/17/15/12 via largest remainder over weights 32/26/24/18.
- Question id `<videoId>-q<nn>`. `n = (video − 1) × 20 + q`. Video ids are 11 characters.
- `localStorage` key `peb:dva-c02`, `schemaVersion` 1.

**Commits**
- Plain commit messages with **no `Co-Authored-By` trailer**. This is the user's standing rule.
- Tests pass at every commit.

## Review Focus

Five conditions the spec implies but which are easy to leave untested. Each has a test pinned in its owning task.

1. **Corrupted or partial stored progress** (`"{"`, `{}`, an old `schemaVersion`) must make the app start fresh, not crash. Tested in Task 8, `loadState starts fresh…`.
2. **Stems containing HTML-like text** (`</script>`, `<!--`, `&`, `<b>`, common in CloudFormation or IAM snippets) must be embedded safely and round-trip unchanged. Tested in Task 5 (`test_render_escapes…`) and Task 10 (`test_dist_smoke`).
3. **Non-ASCII chapter titles** (for example an en dash or `é`) must survive ingest → transcript → validate on Windows. Tested in Tasks 2, 3 and 4, where the factory titles contain `– café`.
4. **The narrator starting a question just before the chapter mark** must still validate. A stem 1s before the chapter start is valid; one that belongs to the next chapter is flagged. Tested in Task 2 (`anchor_window`) and Task 4 (`outside chapter window`).
5. **Malformed import files** (wrong types inside `questionStats`, a non-array `examHistory`) must be rejected with a reason, leaving state untouched. Tested in Task 9, `validateImport rejects…`.

---

## File Structure

```
practice-exam-builder/
  pyproject.toml                  T1  package metadata, console script, pytest config
  README.md                       T11 usage
  src/peb/__init__.py             T1  empty
  src/peb/__main__.py             T6  `python -m peb`
  src/peb/dva_c02.py              T1  exam guide constants + quotas
  src/peb/timecode.py             T1  h:mm:ss ⇄ seconds
  src/peb/transcript.py           T2  VTT cleaning, chapter headers, transcript parsing, anchor search
  src/peb/ingest.py               T3  YtDlpClient adapter, manifest pinning, caption choice, ingest loop
  src/peb/bank.py                 T4  Violation, validate_bank, load_bank
  src/peb/build.py                T5  bank_version, render, build
  src/peb/cli.py                  T6  argparse CLI
  template/app-core.js            T7–T9 pure logic (PebCore)
  template/app.html               T10 UI
  tests/fixtures/youtube-auto.vtt T2  real YouTube auto-caption sample
  tests/factory.py                T4  synthetic sources+bank builder (T5 adds template helper)
  tests/fakes.py                  T3  FakeClient for ingest
  tests/make_demo.py              T10 builds a demo app from synthetic data
  tests/test_*.py                 per task
  tests-js/*.test.js              T7–T9
  docs/extraction.md              T11 extraction procedure for subagents
  sources/ bank/                  T12–T14 real data (committed)
```

---

### Task 1: Project scaffold, exam constants, timecodes

**Files:**
- Create: `pyproject.toml`, `src/peb/__init__.py`, `src/peb/dva_c02.py`, `src/peb/timecode.py`
- Test: `tests/test_dva_c02.py`, `tests/test_timecode.py`

**Interfaces:**
- Produces:
  - `peb.dva_c02.QUESTIONS_PER_VIDEO: int = 20`
  - `EXAM: dict = {"questions": 65, "minutes": 130, "passPct": 72}`
  - `DOMAINS: list[dict]`, each `{"id": int, "name": str, "weight": int, "tasks": dict[str, str]}`
  - `exam_quotas(total: int = 65) -> dict[int, int]`
  - `peb.timecode.format_hms(seconds: float) -> str` (`"h:mm:ss"`)
  - `parse_hms(text: str) -> float`

- [ ] **Step 1: Create the scaffold and venv**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "peb"
version = "0.1.0"
description = "Practice exam builder: ingest study videos, build an offline practice-exam app"
requires-python = ">=3.12"
dependencies = ["yt-dlp==2026.8.19"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
peb = "peb.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "tests"]
```

`src/peb/__init__.py`: empty file.

Run:
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -q -e ".[dev]"
```
Expected: exits 0.

- [ ] **Step 2: Write the failing tests**

`tests/test_dva_c02.py`:
```python
from peb.dva_c02 import DOMAINS, EXAM, exam_quotas


def test_exam_quotas_match_guide_for_65():
    assert exam_quotas(65) == {1: 21, 2: 17, 3: 15, 4: 12}


def test_quotas_default_to_exam_length():
    assert sum(exam_quotas().values()) == EXAM["questions"] == 65


def test_quotas_use_largest_remainder_for_small_totals():
    assert exam_quotas(10) == {1: 3, 2: 3, 3: 2, 4: 2}


def test_weights_sum_to_100_and_tasks_are_numbered_by_domain():
    assert sum(d["weight"] for d in DOMAINS) == 100
    assert [len(d["tasks"]) for d in DOMAINS] == [3, 3, 4, 3]
    for d in DOMAINS:
        assert all(t.startswith(f"{d['id']}.") for t in d["tasks"])
```

`tests/test_timecode.py`:
```python
import pytest

from peb.timecode import format_hms, parse_hms


@pytest.mark.parametrize("sec,text", [(0, "0:00:00"), (59, "0:00:59"), (639, "0:10:39"), (4449, "1:14:09")])
def test_format_hms(sec, text):
    assert format_hms(sec) == text


def test_format_truncates_fractions():
    assert format_hms(3.99) == "0:00:03"


@pytest.mark.parametrize("text,sec", [("10:39", 639), ("1:14:09", 4449), ("00:00:03.270", 3.27)])
def test_parse_hms(text, sec):
    assert parse_hms(text) == pytest.approx(sec)


@pytest.mark.parametrize("bad", ["", "12", "1:2:3:4", "a:bc"])
def test_parse_rejects_bad_timecodes(bad):
    with pytest.raises(ValueError):
        parse_hms(bad)
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'peb.dva_c02'`.

- [ ] **Step 4: Implement**

`src/peb/dva_c02.py`:
```python
"""DVA-C02 exam guide reference data — the single source of truth."""

QUESTIONS_PER_VIDEO = 20
EXAM = {"questions": 65, "minutes": 130, "passPct": 72}

DOMAINS = [
    {"id": 1, "name": "Development with AWS Services", "weight": 32, "tasks": {
        "1.1": "Develop code for applications hosted on AWS",
        "1.2": "Develop code for AWS Lambda",
        "1.3": "Use data stores in application development",
    }},
    {"id": 2, "name": "Security", "weight": 26, "tasks": {
        "2.1": "Implement authentication and/or authorization for applications and AWS services",
        "2.2": "Implement encryption by using AWS services",
        "2.3": "Manage sensitive data in application code",
    }},
    {"id": 3, "name": "Deployment", "weight": 24, "tasks": {
        "3.1": "Prepare application artifacts to be deployed to AWS",
        "3.2": "Test applications in development environments",
        "3.3": "Automate deployment testing",
        "3.4": "Deploy code by using AWS CI/CD services",
    }},
    {"id": 4, "name": "Troubleshooting and Optimization", "weight": 18, "tasks": {
        "4.1": "Assist in a root cause analysis",
        "4.2": "Instrument code for observability",
        "4.3": "Optimize applications by using AWS services and features",
    }},
]


def exam_quotas(total: int = EXAM["questions"]) -> dict[int, int]:
    """Largest-remainder apportionment of `total` questions by domain weight."""
    weight_sum = sum(d["weight"] for d in DOMAINS)
    exact = {d["id"]: total * d["weight"] / weight_sum for d in DOMAINS}
    quotas = {k: int(v) for k, v in exact.items()}
    leftover = total - sum(quotas.values())
    by_remainder = sorted(exact, key=lambda k: (-(exact[k] - quotas[k]), k))
    for k in by_remainder[:leftover]:
        quotas[k] += 1
    return quotas
```

`src/peb/timecode.py`:
```python
"""Convert between seconds and h:mm:ss timecodes."""


def format_hms(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def parse_hms(text: str) -> float:
    """Parse m:ss, h:mm:ss or VTT hh:mm:ss.mmm into seconds."""
    parts = text.strip().split(":")
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"bad timecode: {text!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src tests
git commit -m "Scaffold peb package with DVA-C02 constants and timecodes"
```

---

### Task 2: Transcript cleaning, chapter headers, anchor search

**Files:**
- Create: `src/peb/transcript.py`, `tests/fixtures/youtube-auto.vtt`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Consumes: `format_hms` and `parse_hms` (Task 1).
- Produces, all in `peb.transcript`:
  - `Line(start: int, text: str)`: a frozen dataclass.
  - `clean_vtt(vtt: str) -> list[Line]`
  - `question_chapters(chapters: list[dict]) -> list[dict]`. Input items look like `{"startSec", "endSec", "title"}`; output items add `"q"`, numbered from 1.
  - `render_transcript(lines: list[Line], qchapters: list[dict]) -> str`
  - `parse_transcript(text: str) -> list[Line]`
  - `normalize(text: str) -> str`
  - `find_anchor_start(lines: list[Line], anchor: str) -> int | None`
  - `anchor_window(chapter: dict) -> tuple[int, int]`
  - `ANCHOR_LEAD_SEC = 15`

Background: YouTube auto-caption VTT is "rolling". Each cue repeats the previous line and then adds a new line with inline word timings, and 10ms "transition" cues repeat the text again. Stripping tags and dropping any line equal to the last emitted line yields clean, non-duplicated lines.

- [ ] **Step 1: Add the caption fixture**

Create `tests/fixtures/youtube-auto.vtt`, a made-up caption file with the same rolling structure as a real YouTube auto-caption (`en-orig`) track. Reproduce it exactly, including the lines that contain a single space:
```
WEBVTT
Kind: captions
Language: en

00:00:00.240 --> 00:00:03.270 align:start position:0%
 
Hello<00:00:00.640><c> and</c><00:00:01.600><c> welcome,</c><00:00:01.920><c> I'm</c><00:00:02.560><c> your</c><00:00:02.800><c> host</c>

00:00:03.270 --> 00:00:03.280 align:start position:0%
Hello and welcome, I'm your host
 

00:00:03.280 --> 00:00:05.670 align:start position:0%
Hello and welcome, I'm your host
recording<00:00:03.840><c> from</c><00:00:04.240><c> a</c><00:00:04.480><c> small</c><00:00:04.640><c> home</c><00:00:04.880><c> studio</c>

00:00:05.670 --> 00:00:05.680 align:start position:0%
recording from a small home studio
 

00:00:05.680 --> 00:00:08.390 align:start position:0%
recording from a small home studio
somewhere<00:00:06.160><c> in</c><00:00:06.480><c> the</c><00:00:06.720><c> hills.</c>

00:00:08.390 --> 00:00:08.400 align:start position:0%
somewhere in the hills.
 

00:00:08.400 --> 00:00:11.270 align:start position:0%
somewhere in the hills.
This<00:00:08.800><c> series</c><00:00:09.040><c> walks</c><00:00:09.360><c> through</c><00:00:09.679><c> sample</c><00:00:10.000><c> questions</c><00:00:10.880><c> for</c><00:00:11.120><c> a</c>

00:00:11.270 --> 00:00:11.280 align:start position:0%
This series walks through sample questions for a
 

00:00:11.280 --> 00:00:13.509 align:start position:0%
This series walks through sample questions for a
cloud<00:00:11.840><c> exam,</c><00:00:12.080><c> one</c><00:00:12.240><c> topic</c><00:00:12.320><c> at</c><00:00:12.480><c> a</c><00:00:12.719><c> time</c><00:00:13.040><c> today</c>
```

- [ ] **Step 2: Write the failing tests**

`tests/test_transcript.py`:
```python
from pathlib import Path

from peb.transcript import (
    Line, anchor_window, clean_vtt, find_anchor_start, normalize,
    parse_transcript, question_chapters, render_transcript,
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
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest tests/test_transcript.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'peb.transcript'`.

- [ ] **Step 4: Implement**

`src/peb/transcript.py`:
```python
"""Caption cleaning and chapter-sectioned transcripts."""
import html
import re
from dataclasses import dataclass

from peb.timecode import format_hms, parse_hms

ANCHOR_LEAD_SEC = 15
_TAG = re.compile(r"<[^>]+>")
_CUE_TIMING = re.compile(r"^(\S+)\s+-->\s+")
_LINE = re.compile(r"^\[(\d+:\d{2}:\d{2})\] (.*)$")
_INTRO = re.compile(r"intro", re.IGNORECASE)


@dataclass(frozen=True)
class Line:
    start: int
    text: str


def clean_vtt(vtt: str) -> list[Line]:
    """YouTube (auto-)caption VTT -> de-duplicated caption lines."""
    lines: list[Line] = []
    start = None
    for raw in vtt.splitlines():
        timing = _CUE_TIMING.match(raw)
        if timing:
            start = int(parse_hms(timing.group(1)))
        elif start is not None:
            text = " ".join(html.unescape(_TAG.sub("", raw)).split())
            if text and (not lines or lines[-1].text != text):
                lines.append(Line(start, text))
    return lines


def question_chapters(chapters: list[dict]) -> list[dict]:
    """Drop a leading intro chapter and number the rest from 1."""
    rest = chapters[1:] if chapters and _INTRO.search(chapters[0]["title"]) else chapters
    return [{"q": i, **chapter} for i, chapter in enumerate(rest, start=1)]


def render_transcript(lines: list[Line], qchapters: list[dict]) -> str:
    out, pending = [], list(qchapters)
    for line in lines:
        while pending and line.start >= pending[0]["startSec"]:
            out.append(_header(pending.pop(0)))
        out.append(f"[{format_hms(line.start)}] {line.text}")
    out.extend(_header(chapter) for chapter in pending)
    return "\n".join(out) + "\n"


def _header(chapter: dict) -> str:
    span = f"{format_hms(chapter['startSec'])}–{format_hms(chapter['endSec'])}"
    return f"=== Q{chapter['q']:02d} [{span}] {chapter['title']} ==="


def parse_transcript(text: str) -> list[Line]:
    """Caption lines of a rendered transcript; chapter headers are skipped."""
    lines = []
    for raw in text.splitlines():
        match = _LINE.match(raw)
        if match:
            lines.append(Line(int(parse_hms(match.group(1))), match.group(2)))
    return lines


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def find_anchor_start(lines: list[Line], anchor: str) -> int | None:
    """Start second of the line where the first whole-word match of `anchor` begins."""
    target = normalize(anchor)
    if not target:
        return None
    joined, offsets = "", []
    for line in lines:
        piece = normalize(line.text)
        if not piece:
            continue
        if joined:
            joined += " "
        offsets.append((len(joined), line.start))
        joined += piece
    pos = f" {joined} ".find(f" {target} ")
    if pos < 0:
        return None
    start = offsets[0][1]
    for offset, second in offsets:
        if offset > pos:
            break
        start = second
    return start


def anchor_window(chapter: dict) -> tuple[int, int]:
    """[lo, hi) seconds where a chapter's stem may begin (the narrator starts early)."""
    return max(0, chapter["startSec"] - ANCHOR_LEAD_SEC), chapter["endSec"] - ANCHOR_LEAD_SEC
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/peb/transcript.py tests/test_transcript.py tests/fixtures
git commit -m "Clean YouTube captions into chapter-sectioned transcripts"
```

---

### Task 3: Ingest (manifest pinning, caption choice, per-video loop)

**Files:**
- Create: `src/peb/ingest.py`, `tests/fakes.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `clean_vtt`, `question_chapters`, `render_transcript` (Task 2), and `QUESTIONS_PER_VIDEO` (Task 1).
- Produces, all in `peb.ingest`:
  - `YtDlpClient(cookies_from_browser: str | None = None)` with these methods:
    - `.list_playlist(url) -> list[dict]`. Items are `{videoId, title, url, durationSec}`.
    - `.video_info(video_id) -> dict`, shaped `{durationSec, chapters: [{startSec, endSec, title}], subtitles: [lang], automatic_captions: [lang]}`.
    - `.download_captions(video_id, lang, automatic, dest_dir) -> str`, which returns the VTT text.
  - `merge_manifest(existing, entries) -> (manifest, missing_ids)`
  - `pick_caption_track(info) -> (lang, automatic) | None`
  - `ingest(client, url, sources_dir, force=False, delay=5.0, sleep=time.sleep) -> list[dict]`. Items are `{index, videoId, status, detail}`.
  - `FAILED = {"no-captions", "chapter-mismatch", "error"}`
- `tests/fakes.py` produces `entry(video_id)`, `chapters(n)`, `VTT` and `FakeClient(videos, infos=None, fail=())`. Task 6 reuses them.

- [ ] **Step 1: Write the fake and the failing tests**

`tests/fakes.py`:
```python
"""Test doubles for the yt-dlp adapter."""

VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello there\n"


def entry(video_id):
    return {"videoId": video_id, "title": f"T {video_id}",
            "url": f"https://www.youtube.com/watch?v={video_id}", "durationSec": 100}


def chapters(n):
    intro = [{"startSec": 0, "endSec": 10, "title": "Introduction and setup"}]
    return intro + [{"startSec": 10 * i, "endSec": 10 * (i + 1), "title": f"Topic {i} – é"} for i in range(1, n + 1)]


class FakeClient:
    def __init__(self, videos, infos=None, fail=()):
        self.videos, self.infos, self.fail = videos, infos or {}, set(fail)
        self.downloads = []

    def list_playlist(self, url):
        return [entry(v) for v in self.videos]

    def video_info(self, video_id):
        if video_id in self.fail:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        default = {"durationSec": 210, "chapters": chapters(20), "subtitles": [], "automatic_captions": ["en-orig"]}
        return self.infos.get(video_id, default)

    def download_captions(self, video_id, lang, automatic, dest_dir):
        self.downloads.append((video_id, lang, automatic))
        return VTT
```

`tests/test_ingest.py`:
```python
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
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest tests/test_ingest.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'peb.ingest'`.

- [ ] **Step 3: Implement**

`src/peb/ingest.py`:
```python
"""Ingest a YouTube playlist into sources/ (manifest, metadata, captions, transcript)."""
import json
import subprocess
import sys
import time
from pathlib import Path

from peb.dva_c02 import QUESTIONS_PER_VIDEO
from peb.transcript import clean_vtt, question_chapters, render_transcript

MANUAL_LANGS = ["en", "en-US", "en-GB", "en-orig"]
AUTO_LANGS = ["en-orig", "en", "en-US", "en-GB"]
FAILED = {"no-captions", "chapter-mismatch", "error"}


class YtDlpClient:
    """Thin adapter over the yt-dlp CLI. Exercised by the real ingest run, not unit tests."""

    def __init__(self, cookies_from_browser: str | None = None):
        self._base = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node", "--no-warnings"]
        if cookies_from_browser:
            self._base += ["--cookies-from-browser", cookies_from_browser]

    def _run(self, args: list[str]) -> str:
        proc = subprocess.run(self._base + args, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            lines = [line for line in proc.stderr.splitlines() if line.strip()]
            raise RuntimeError(lines[-1] if lines else f"yt-dlp exited with {proc.returncode}")
        return proc.stdout

    def list_playlist(self, url: str) -> list[dict]:
        data = json.loads(self._run(["--flat-playlist", "-J", url]))
        return [{"videoId": e["id"], "title": e.get("title") or "",
                 "url": f"https://www.youtube.com/watch?v={e['id']}",
                 "durationSec": int(e.get("duration") or 0)} for e in data["entries"]]

    def video_info(self, video_id: str) -> dict:
        data = json.loads(self._run(["-J", f"https://www.youtube.com/watch?v={video_id}"]))
        return {
            "durationSec": int(data.get("duration") or 0),
            "chapters": [{"startSec": int(c["start_time"]), "endSec": int(c["end_time"]), "title": c["title"]}
                         for c in data.get("chapters") or []],
            "subtitles": sorted((data.get("subtitles") or {}).keys()),
            "automatic_captions": sorted((data.get("automatic_captions") or {}).keys()),
        }

    def download_captions(self, video_id: str, lang: str, automatic: bool, dest_dir: Path) -> str:
        dest_dir.mkdir(parents=True, exist_ok=True)
        flag = "--write-auto-subs" if automatic else "--write-subs"
        self._run(["--skip-download", flag, "--sub-langs", lang, "--sub-format", "vtt",
                   "-o", str(dest_dir / "captions.%(ext)s"), f"https://www.youtube.com/watch?v={video_id}"])
        path = dest_dir / f"captions.{lang}.vtt"
        text = path.read_text(encoding="utf-8")
        path.unlink()
        return text


def merge_manifest(existing: list[dict], entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Keep pinned indices, append new videos, report pinned videos no longer listed."""
    known = {e["videoId"] for e in existing}
    manifest = [dict(e) for e in existing]
    next_index = max((e["index"] for e in existing), default=0) + 1
    for item in entries:
        if item["videoId"] not in known:
            manifest.append({"index": next_index, **item})
            next_index += 1
    listed = {item["videoId"] for item in entries}
    return manifest, [e["videoId"] for e in existing if e["videoId"] not in listed]


def pick_caption_track(info: dict) -> tuple[str, bool] | None:
    for available, preferred, automatic in ((info["subtitles"], MANUAL_LANGS, False),
                                            (info["automatic_captions"], AUTO_LANGS, True)):
        for lang in preferred:
            if lang in available:
                return lang, automatic
        variants = sorted(lang for lang in available if lang.startswith("en-"))
        if variants:
            return variants[0], automatic
    return None


def ingest(client, url: str, sources_dir: Path, force: bool = False,
           delay: float = 5.0, sleep=time.sleep) -> list[dict]:
    sources_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = sources_dir / "playlist.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    manifest, missing = merge_manifest(existing, client.list_playlist(url))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    results, fetched_any = [], False
    for item in manifest:
        folder = sources_dir / f"{item['index']:02d}-{item['videoId']}"
        if item["videoId"] in missing:
            results.append(_result(item, "missing", "no longer in the playlist"))
        elif (folder / "transcript.txt").exists() and not force:
            results.append(_result(item, "ok", "skipped (already ingested)"))
        else:
            if fetched_any:
                sleep(delay)
            fetched_any = True
            results.append(_ingest_video(client, item, folder))
    return results


def _ingest_video(client, item: dict, folder: Path) -> dict:
    try:
        info = client.video_info(item["videoId"])
        qchapters = question_chapters(info["chapters"])
        folder.mkdir(parents=True, exist_ok=True)
        metadata = {**item, "durationSec": info["durationSec"] or item["durationSec"],
                    "chapters": info["chapters"], "questionChapters": qchapters}
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        track = pick_caption_track(info)
        if track is None:
            return _result(item, "no-captions", "no English captions available")
        vtt = client.download_captions(item["videoId"], track[0], track[1], folder)
        (folder / "captions.vtt").write_text(vtt, encoding="utf-8")
        (folder / "transcript.txt").write_text(render_transcript(clean_vtt(vtt), qchapters), encoding="utf-8")
    except Exception as exc:  # boundary: report per video and keep going
        return _result(item, "error", str(exc) or type(exc).__name__)
    if len(qchapters) != QUESTIONS_PER_VIDEO:
        return _result(item, "chapter-mismatch",
                       f"{len(qchapters)} question chapters (expected {QUESTIONS_PER_VIDEO})")
    return _result(item, "ok", f"{track[0]}{' (auto)' if track[1] else ''}")


def _result(item: dict, status: str, detail: str) -> dict:
    return {"index": item["index"], "videoId": item["videoId"], "status": status, "detail": detail}
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/peb/ingest.py tests/fakes.py tests/test_ingest.py
git commit -m "Ingest playlist with pinned order, caption choice and per-video reporting"
```

---

### Task 4: Bank validation and loading

**Files:**
- Create: `src/peb/bank.py`, `tests/factory.py`
- Test: `tests/test_bank.py`

**Interfaces:**
- Consumes:
  - From Task 1: `DOMAINS`, `QUESTIONS_PER_VIDEO`, `exam_quotas`, `format_hms`.
  - From Task 2: `anchor_window`, `find_anchor_start`, `normalize`, `parse_transcript`, `Line`, `question_chapters`, `render_transcript`.
- Produces, in `peb.bank`:
  - `Violation(file: str, qid: str, message: str, warning: bool = False)`, whose `str()` is `"[warning: ]<file> <qid> : <message>"`.
  - `validate_bank(root: Path, files: list[Path] | None = None) -> list[Violation]`
  - `validate_bank_file(path, sources_dir, playlist) -> list[Violation]`
  - `load_bank(root: Path) -> tuple[list[dict], list[dict]]`, returning videos `[{index, videoId, title}]` sorted by index, and questions sorted by `n`.
- Produces, in `tests/factory.py`: `video_id(i)`, `anchor_text(i, q)`, `chapter_title(i, q)`, `make_question(i, q, domain)`, `write_json(path, data)`, `rewrite(path, mutate)` and `make_root(root, videos=4) -> Path`.
  - It writes a valid synthetic root: `sources/playlist.json`, `sources/<nn>-<id>/{metadata.json, transcript.txt}` and `bank/<nn>-<id>.json`.
  - Four videos give a domain spread of 24/20/20/16, which covers the 21/17/15/12 quotas with slack.

- [ ] **Step 1: Write the factory**

`tests/factory.py`:
```python
"""Synthetic sources + bank builder for tests. Four videos satisfy the exam quotas."""
import json
from pathlib import Path

from peb.transcript import Line, question_chapters, render_transcript

CHAPTER_SEC = 200
DEFAULT_DOMAINS = [1] * 6 + [2] * 5 + [3] * 5 + [4] * 4


def video_id(index: int) -> str:
    return f"vid{index:08d}"


def anchor_text(index: int, q: int) -> str:
    return f"a developer in video {index} faces problem {q} today"


def chapter_title(index: int, q: int) -> str:
    return f"Topic {index}-{q} – café"


def make_question(index: int, q: int, domain: int = 1) -> dict:
    vid = video_id(index)
    return {
        "id": f"{vid}-q{q:02d}", "video": index, "videoId": vid, "n": (index - 1) * 20 + q,
        "chapterTitle": chapter_title(index, q), "timestampSec": q * CHAPTER_SEC,
        "anchor": anchor_text(index, q), "domain": domain, "task": f"{domain}.1", "selectN": 1,
        "stem": f"Stem for video {index} question {q}?",
        "options": [{"k": k, "t": f"Option {k}", "why": f"Why {k}"} for k in "ABCD"],
        "correct": ["B"], "topic": "Topic discussion.", "correctWhy": "B is right.",
    }


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def rewrite(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    write_json(path, data)


def write_video(root: Path, index: int, count: int = 20) -> dict:
    vid = video_id(index)
    chapters = [{"startSec": 0, "endSec": CHAPTER_SEC, "title": "Introduction and setup"}] + [
        {"startSec": q * CHAPTER_SEC, "endSec": (q + 1) * CHAPTER_SEC, "title": chapter_title(index, q)}
        for q in range(1, count + 1)]
    qchapters = question_chapters(chapters)
    entry = {"index": index, "videoId": vid, "title": f"Part {index}",
             "url": f"https://www.youtube.com/watch?v={vid}", "durationSec": (count + 1) * CHAPTER_SEC}
    folder = root / "sources" / f"{index:02d}-{vid}"
    write_json(folder / "metadata.json", {**entry, "chapters": chapters, "questionChapters": qchapters})
    lines = [Line(5, "Welcome to the series.")]
    for q in range(1, count + 1):
        start = q * CHAPTER_SEC
        lines += [Line(start - 1, f"Question {q}."), Line(start + 1, anchor_text(index, q) + "."),
                  Line(start + 60, "Option A is incorrect.")]
    (folder / "transcript.txt").write_text(render_transcript(lines, qchapters), encoding="utf-8")
    questions = [make_question(index, q, DEFAULT_DOMAINS[(q - 1) % len(DEFAULT_DOMAINS)])
                 for q in range(1, count + 1)]
    write_json(root / "bank" / f"{index:02d}-{vid}.json",
               {"video": index, "videoId": vid, "title": f"Part {index}",
                "expectedCount": 20, "countNote": None, "questions": questions})
    return entry


def make_root(root: Path, videos: int = 4) -> Path:
    entries = [write_video(root, i) for i in range(1, videos + 1)]
    write_json(root / "sources" / "playlist.json", entries)
    return root
```

- [ ] **Step 2: Write the failing tests**

`tests/test_bank.py`:
```python
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
```

Where the window numbers come from: Q1's chapter runs 200–400, so its window is [185, 385), which formats as `0:03:05–0:06:25`. Q2's anchor sits at 401s (`0:06:41`).

- [ ] **Step 3: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest tests/test_bank.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'peb.bank'`.

- [ ] **Step 4: Implement**

`src/peb/bank.py`:
```python
"""Load and validate the question bank (bank/*.json) against its sources."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from peb.dva_c02 import DOMAINS, QUESTIONS_PER_VIDEO, exam_quotas
from peb.timecode import format_hms
from peb.transcript import anchor_window, find_anchor_start, normalize, parse_transcript

FILENAME = re.compile(r"^(\d{2})-([A-Za-z0-9_-]{11})\.json$")
TASKS = {d["id"]: set(d["tasks"]) for d in DOMAINS}


@dataclass(frozen=True)
class Violation:
    file: str
    qid: str
    message: str
    warning: bool = False

    def __str__(self) -> str:
        prefix = "warning: " if self.warning else ""
        return f"{prefix}{self.file} {self.qid} : {self.message}"


def validate_bank(root: Path, files: list[Path] | None = None) -> list[Violation]:
    """Validate every bank file (or only `files`) plus bank-wide rules.

    Duplicate checks always span the whole bank; domain quotas only apply to a full validation.
    """
    bank_dir, sources_dir = root / "bank", root / "sources"
    playlist = _read_json(sources_dir / "playlist.json")
    playlist = playlist if isinstance(playlist, list) else []
    all_paths = sorted(bank_dir.glob("*.json"))
    paths = all_paths if files is None else [Path(f) for f in files]
    violations = []
    for path in paths:
        violations += validate_bank_file(path, sources_dir, playlist)
    return violations + _bank_problems(all_paths, check_quotas=files is None)


def load_bank(root: Path) -> tuple[list[dict], list[dict]]:
    videos, questions = [], []
    for path in sorted((root / "bank").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        videos.append({"index": data["video"], "videoId": data["videoId"], "title": data["title"]})
        questions += data["questions"]
    return sorted(videos, key=lambda v: v["index"]), sorted(questions, key=lambda q: q["n"])


def validate_bank_file(path: Path, sources_dir: Path, playlist: list[dict]) -> list[Violation]:
    match = FILENAME.match(path.name)
    if not match:
        return [Violation(path.name, "-", "filename must be <nn>-<videoId>.json")]
    data = _read_json(path)
    if not isinstance(data, dict):
        return [Violation(path.name, "-", "unreadable JSON (expected an object)")]
    index, video_id = int(match.group(1)), match.group(2)
    source = _load_source(sources_dir / f"{index:02d}-{video_id}")
    violations = [Violation(path.name, "-", m) for m in _file_problems(data, index, video_id, playlist, source)]
    violations += _count_warning(path.name, data)
    questions = data.get("questions")
    for pos, q in enumerate(questions if isinstance(questions, list) else [], start=1):
        qid = str(q["id"]) if isinstance(q, dict) and q.get("id") else f"#{pos}"
        violations += [Violation(path.name, qid, m) for m in question_problems(q, index, video_id, pos, source)]
    return violations


def question_problems(q, index: int, video_id: str, pos: int, source: dict | None) -> list[str]:
    if not isinstance(q, dict):
        return ["question must be an object"]
    problems = []
    n = (index - 1) * QUESTIONS_PER_VIDEO + pos
    if q.get("id") != f"{video_id}-q{pos:02d}":
        problems.append(f"id must be {video_id}-q{pos:02d}")
    if q.get("video") != index or q.get("videoId") != video_id:
        problems.append("video/videoId do not match file")
    if q.get("n") != n:
        problems.append(f"n must be {n}")
    problems += _domain_problems(q) + _option_problems(q)
    for field in ("stem", "topic", "correctWhy", "chapterTitle", "anchor"):
        if not _text(q.get(field)):
            problems.append(f"{field} must be non-empty")
    if _text(q.get("anchor")) and not 6 <= len(q["anchor"].split()) <= 12:
        problems.append("anchor must be 6-12 words")
    if source is not None:
        problems += _source_problems(q, pos, source)
    return problems


def _file_problems(data: dict, index: int, video_id: str, playlist: list[dict], source: dict | None) -> list[str]:
    problems = []
    if not any(isinstance(e, dict) and e.get("index") == index and e.get("videoId") == video_id for e in playlist):
        problems.append("video not in sources/playlist.json at this index")
    if data.get("video") != index or data.get("videoId") != video_id:
        problems.append("video/videoId do not match filename")
    if not _text(data.get("title")):
        problems.append("title must be non-empty")
    questions = data.get("questions")
    if not isinstance(questions, list):
        return problems + ["questions must be a list"]
    expected = data.get("expectedCount", QUESTIONS_PER_VIDEO)
    has_note = _text(data.get("countNote"))
    if len(questions) != expected:
        problems.append(f"has {len(questions)} questions, expectedCount is {expected}")
    if expected != QUESTIONS_PER_VIDEO and not has_note:
        problems.append(f"expectedCount {expected} requires a countNote")
    if source is None:
        problems.append("missing sources metadata.json/transcript.txt")
    elif len(source["chapters"]) != expected and not has_note:
        problems.append(f"{len(source['chapters'])} question chapters but expectedCount is {expected}")
    return problems


def _count_warning(file: str, data: dict) -> list[Violation]:
    expected = data.get("expectedCount", QUESTIONS_PER_VIDEO)
    if expected != QUESTIONS_PER_VIDEO and _text(data.get("countNote")):
        return [Violation(file, "-", f"expectedCount {expected}: {data['countNote']}", warning=True)]
    return []


def _domain_problems(q: dict) -> list[str]:
    domain, task = q.get("domain"), q.get("task")
    if not isinstance(domain, int) or domain not in TASKS:
        return ["domain must be 1-4"]
    if not isinstance(task, str) or task not in TASKS[domain]:
        return [f"task {task!r} is not a task of domain {domain}"]
    return []


def _option_problems(q: dict) -> list[str]:
    options, correct, select_n = q.get("options"), q.get("correct"), q.get("selectN")
    problems, keys = [], []
    if not isinstance(options, list) or not 4 <= len(options) <= 6 or not all(isinstance(o, dict) for o in options):
        problems.append("options must have 4-6 entries")
    else:
        keys = [o.get("k") for o in options]
        if keys != [chr(ord("A") + i) for i in range(len(options))]:
            problems.append("option keys must be A, B, C… in order")
        for o in options:
            if not _text(o.get("t")) or not _text(o.get("why")):
                problems.append(f"option {o.get('k')} needs non-empty t and why")
    if select_n not in (1, 2):
        problems.append("selectN must be 1 or 2")
    if not isinstance(correct, list) or len(correct) != select_n or len(set(map(str, correct))) != len(correct):
        problems.append("correct must list selectN distinct keys")
    elif keys and any(k not in keys for k in correct):
        problems.append("correct references a missing option")
    return problems


def _source_problems(q: dict, pos: int, source: dict) -> list[str]:
    chapters = source["chapters"]
    if pos > len(chapters):
        return [f"no question chapter {pos} in metadata.json"]
    chapter = chapters[pos - 1]
    problems = []
    if q.get("chapterTitle") != chapter["title"]:
        problems.append(f"chapterTitle must be {chapter['title']!r}")
    if q.get("timestampSec") != chapter["startSec"]:
        problems.append(f"timestampSec must be {chapter['startSec']}")
    if _text(q.get("anchor")):
        start = find_anchor_start(source["lines"], q["anchor"])
        lo, hi = anchor_window(chapter)
        if start is None:
            problems.append("anchor not found in transcript")
        elif not lo <= start < hi:
            problems.append(f"anchor first occurs at {format_hms(start)}, "
                            f"outside chapter window {format_hms(lo)}–{format_hms(hi)}")
    return problems


def _bank_problems(paths: list[Path], check_quotas: bool) -> list[Violation]:
    problems, seen_ids, seen_stems = [], {}, {}
    counts = {d["id"]: 0 for d in DOMAINS}
    for path in paths:
        data = _read_json(path)
        questions = data.get("questions") if isinstance(data, dict) else None
        for q in questions if isinstance(questions, list) else []:
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id"))
            if qid in seen_ids:
                problems.append(Violation(path.name, qid, f"duplicate id (also in {seen_ids[qid]})"))
            seen_ids.setdefault(qid, path.name)
            stem = normalize(q["stem"]) if _text(q.get("stem")) else ""
            if stem and stem in seen_stems:
                problems.append(Violation(path.name, qid, f"duplicate stem (same as {seen_stems[stem]})"))
            seen_stems.setdefault(stem, qid)
            if isinstance(q.get("domain"), int) and q["domain"] in counts:
                counts[q["domain"]] += 1
    if check_quotas:
        for domain, quota in exam_quotas().items():
            if counts[domain] < quota:
                problems.append(Violation("bank", "-", f"domain {domain} has {counts[domain]} questions; "
                                                       f"an exam needs {quota}"))
    return problems


def _load_source(folder: Path) -> dict | None:
    metadata = _read_json(folder / "metadata.json")
    try:
        transcript = (folder / "transcript.txt").read_text(encoding="utf-8")
    except OSError:
        return None
    if not isinstance(metadata, dict) or not isinstance(metadata.get("questionChapters"), list):
        return None
    return {"chapters": metadata["questionChapters"], "lines": parse_transcript(transcript)}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass. If a parametrized case fails, compare the printed `messages(root)` list against the expected string character for character. The en dash `–` and the ellipsis `…` must match exactly.

- [ ] **Step 6: Commit**

```bash
git add src/peb/bank.py tests/factory.py tests/test_bank.py
git commit -m "Validate question bank against chapters and transcripts"
```

---

### Task 5: Build (bank version, template injection)

**Files:**
- Create: `src/peb/build.py`
- Modify: `tests/factory.py` (append `write_minimal_template`)
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `validate_bank` and `load_bank` (Task 4), and `DOMAINS` and `EXAM` (Task 1).
- Produces, in `peb.build`:
  - `BuildError(Exception)`
  - `bank_version(questions: list[dict]) -> str` (12 hex characters)
  - `render(template: str, core: str, payload: dict) -> str`
  - `build(root: Path) -> Path`. It reads `root/template/app.html` and `root/template/app-core.js`, and writes `root/dist/dva-c02-practice.html`.
- The payload keys are `bankVersion`, `exam`, `domains`, `videos` and `questions`. Task 10's UI reads the global `BANK` object with exactly these keys.

- [ ] **Step 1: Add the template helper to the factory**

Append to `tests/factory.py`:
```python
MINIMAL_TEMPLATE = "<html><title>DVA-C02 Practice (unofficial)</title><script>/*__CORE__*/</script><script>/*__BANK__*/</script></html>"


def write_minimal_template(root: Path) -> Path:
    folder = root / "template"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "app.html").write_text(MINIMAL_TEMPLATE, encoding="utf-8")
    (folder / "app-core.js").write_text("var PebCore = {};", encoding="utf-8")
    return root
```

- [ ] **Step 2: Write the failing tests**

`tests/test_build.py`:
```python
import json

import pytest

from factory import make_root, rewrite, video_id, write_minimal_template
from peb.build import BuildError, bank_version, build, render

TEMPLATE = "<script>/*__CORE__*/</script><script>/*__BANK__*/</script>"


def test_bank_version_is_stable_and_content_sensitive():
    qs = [{"id": "a", "stem": "x"}]
    assert bank_version(qs) == bank_version([{"stem": "x", "id": "a"}])
    assert len(bank_version(qs)) == 12
    assert bank_version(qs) != bank_version([{"id": "a", "stem": "y"}])


def test_render_injects_core_and_bank():
    html = render(TEMPLATE, "var CORE = 1;", {"a": 1})
    assert html == '<script>var CORE = 1;</script><script>const BANK = {"a": 1};</script>'


def test_render_escapes_angle_brackets_in_bank_json():
    html = render(TEMPLATE, "", {"stem": "</script><!-- <b>"})
    bank_script = html.split("<script>")[2]
    assert "</script><!--" not in bank_script.rsplit("</script>", 1)[0]
    assert "\\u003c/script>\\u003c!-- \\u003cb>" in html


@pytest.mark.parametrize("template", [
    "<script>/*__BANK__*/</script>",
    "<script>/*__CORE__*/</script>",
    "/*__CORE__*//*__CORE__*//*__BANK__*/",
])
def test_render_requires_each_placeholder_exactly_once(template):
    with pytest.raises(BuildError):
        render(template, "", {})


def test_build_refuses_invalid_bank(tmp_path):
    root = write_minimal_template(make_root(tmp_path))
    rewrite(root / "bank" / f"01-{video_id(1)}.json", lambda b: b["questions"][0].update(domain=9))
    with pytest.raises(BuildError, match="domain must be 1-4"):
        build(root)
    assert not (root / "dist").exists()


def test_build_ignores_warnings_and_writes_dist_html(tmp_path):
    root = write_minimal_template(make_root(tmp_path))
    rewrite(root / "bank" / f"01-{video_id(1)}.json",
            lambda b: (b["questions"].pop(), b.update(expectedCount=19, countNote="recap chapter")))
    out = build(root)
    assert out == root / "dist" / "dva-c02-practice.html"
    html = out.read_text(encoding="utf-8")
    payload = json.loads(html.split("const BANK = ", 1)[1].rsplit(";</script>", 1)[0])
    assert set(payload) == {"bankVersion", "exam", "domains", "videos", "questions"}
    assert len(payload["questions"]) == 79
    assert payload["exam"] == {"questions": 65, "minutes": 130, "passPct": 72}
    assert payload["videos"][0] == {"index": 1, "videoId": video_id(1), "title": "Part 1"}
    assert "Topic 1-1 – café" in html
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest tests/test_build.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'peb.build'`.

- [ ] **Step 4: Implement**

`src/peb/build.py`:
```python
"""Build dist/dva-c02-practice.html from the template, core logic and validated bank."""
import hashlib
import json
from pathlib import Path

from peb.bank import load_bank, validate_bank
from peb.dva_c02 import DOMAINS, EXAM

CORE_MARK = "/*__CORE__*/"
BANK_MARK = "/*__BANK__*/"
OUTPUT = Path("dist") / "dva-c02-practice.html"


class BuildError(Exception):
    pass


def bank_version(questions: list[dict]) -> str:
    canonical = json.dumps(questions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def render(template: str, core: str, payload: dict) -> str:
    for mark in (CORE_MARK, BANK_MARK):
        if template.count(mark) != 1:
            raise BuildError(f"template must contain {mark} exactly once")
    # Escaping "<" keeps "</script>" and "<!--" inside question text from ending the script block.
    bank_js = "const BANK = " + json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c") + ";"
    return template.replace(BANK_MARK, bank_js).replace(CORE_MARK, core, 1)


def build(root: Path) -> Path:
    problems = [v for v in validate_bank(root) if not v.warning]
    if problems:
        raise BuildError("bank is invalid:\n" + "\n".join(str(v) for v in problems))
    videos, questions = load_bank(root)
    payload = {"bankVersion": bank_version(questions), "exam": EXAM, "domains": DOMAINS,
               "videos": videos, "questions": questions}
    template = (root / "template" / "app.html").read_text(encoding="utf-8")
    core = (root / "template" / "app-core.js").read_text(encoding="utf-8")
    html = render(template, core, payload)
    out = root / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
```

`BANK_MARK` is replaced first so that core source text can never be scanned for the bank marker.

- [ ] **Step 5: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/peb/build.py tests/factory.py tests/test_build.py
git commit -m "Build the study app by injecting core logic and bank into the template"
```

---

### Task 6: CLI

**Files:**
- Create: `src/peb/cli.py`, `src/peb/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ingest`, `YtDlpClient` and `FAILED` (Task 3); `validate_bank` (Task 4); `build` and `BuildError` (Task 5).
- Produces: `peb.cli.main(argv: list[str] | None = None) -> int`. The subcommands are:
  - `--root PATH` (global; must come before the subcommand; default is the working directory)
  - `ingest URL [--force] [--delay SECONDS] [--cookies-from-browser BROWSER]`
  - `validate [PATH...]`
  - `build`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
from factory import make_root, rewrite, video_id, write_minimal_template
from fakes import FakeClient
from peb import cli

A, B = "aaaaaaaaaaa", "bbbbbbbbbbb"


def break_first_question(root):
    rewrite(root / "bank" / f"01-{video_id(1)}.json", lambda b: b["questions"][0].update(domain=7))


def test_validate_exits_zero_for_valid_bank(tmp_path, capsys):
    assert cli.main(["--root", str(make_root(tmp_path)), "validate"]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out


def test_validate_prints_violations_and_exits_one(tmp_path, capsys):
    root = make_root(tmp_path)
    break_first_question(root)
    assert cli.main(["--root", str(root), "validate"]) == 1
    assert f"01-{video_id(1)}.json {video_id(1)}-q01 : domain must be 1-4" in capsys.readouterr().out


def test_validate_accepts_specific_files(tmp_path):
    root = make_root(tmp_path, videos=1)
    assert cli.main(["--root", str(root), "validate", str(root / "bank" / f"01-{video_id(1)}.json")]) == 0


def test_build_writes_output(tmp_path, capsys):
    root = write_minimal_template(make_root(tmp_path))
    assert cli.main(["--root", str(root), "build"]) == 0
    assert "dva-c02-practice.html" in capsys.readouterr().out


def test_build_reports_failure_on_stderr(tmp_path, capsys):
    root = write_minimal_template(make_root(tmp_path))
    break_first_question(root)
    assert cli.main(["--root", str(root), "build"]) == 1
    assert "domain must be 1-4" in capsys.readouterr().err


def test_ingest_prints_summary_and_fails_when_any_video_fails(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "YtDlpClient", lambda cookies_from_browser=None: FakeClient([A, B], fail=[B]))
    assert cli.main(["--root", str(tmp_path), "ingest", "url", "--delay", "0"]) == 1
    out = capsys.readouterr().out
    assert f"01 {A} ok" in out
    assert f"02 {B} error" in out
    assert "1/2 ok" in out


def test_ingest_exits_zero_when_all_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "YtDlpClient", lambda cookies_from_browser=None: FakeClient([A]))
    assert cli.main(["--root", str(tmp_path), "ingest", "url", "--delay", "0"]) == 0
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -q`
Expected: FAIL with `ImportError: cannot import name 'cli'`.

- [ ] **Step 3: Implement**

`src/peb/cli.py`:
```python
"""Command-line entry point: peb [--root DIR] ingest|validate|build."""
import argparse
import sys
from pathlib import Path

from peb.bank import validate_bank
from peb.build import BuildError, build
from peb.ingest import FAILED, YtDlpClient, ingest


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peb", description="Practice exam builder")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="download playlist metadata and captions into sources/")
    p_ingest.add_argument("url")
    p_ingest.add_argument("--force", action="store_true", help="re-fetch videos already ingested")
    p_ingest.add_argument("--delay", type=float, default=5.0, help="seconds between videos")
    p_ingest.add_argument("--cookies-from-browser", help="pass browser cookies to yt-dlp")
    p_ingest.set_defaults(handler=_ingest)

    p_validate = sub.add_parser("validate", help="validate bank files")
    p_validate.add_argument("paths", nargs="*", type=Path)
    p_validate.set_defaults(handler=_validate)

    p_build = sub.add_parser("build", help="build dist/dva-c02-practice.html")
    p_build.set_defaults(handler=_build)
    return parser


def _ingest(args) -> int:
    client = YtDlpClient(args.cookies_from_browser)
    results = ingest(client, args.url, args.root / "sources", force=args.force, delay=args.delay)
    for r in results:
        print(f"{r['index']:02d} {r['videoId']} {r['status']:<16} {r['detail']}")
    ok = sum(r["status"] == "ok" for r in results)
    print(f"{ok}/{len(results)} ok")
    return 1 if any(r["status"] in FAILED for r in results) else 0


def _validate(args) -> int:
    violations = validate_bank(args.root, args.paths or None)
    for v in violations:
        print(v)
    errors = [v for v in violations if not v.warning]
    print(f"{len(errors)} error(s), {len(violations) - len(errors)} warning(s)")
    return 1 if errors else 0


def _build(args) -> int:
    try:
        out = build(args.root)
    except BuildError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0
```

`src/peb/__main__.py`:
```python
from peb.cli import main

raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/peb/cli.py src/peb/__main__.py tests/test_cli.py
git commit -m "Add peb CLI for ingest, validate and build"
```

---

### Task 7: App core — randomness, quotas, sampling, selection, grading

**Files:**
- Create: `template/app-core.js`
- Test: `tests-js/sampling.test.js`

**Interfaces:**
- Produces: the global `PebCore`, also exported through `module.exports`, with:
  - `mulberry32(seed) -> () => number`
  - `shuffle(items, rng) -> array` (a new array)
  - `examQuotas(domains [{id, weight}], total) -> {[id]: n}`
  - `sampleExam(questions [{id, domain}], domains, total, rng) -> id[]`
  - `isCorrect(selected, correct) -> bool`
  - `toggleSelection(selected, key, selectN) -> array`
  - `isOptionLocked(selected, key, selectN) -> bool`
  - `canSubmit(selected, selectN) -> bool`

- [ ] **Step 1: Write the failing tests**

`tests-js/sampling.test.js`:
```js
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const DOMAINS = [{ id: 1, weight: 32 }, { id: 2, weight: 26 }, { id: 3, weight: 24 }, { id: 4, weight: 18 }];

function bank(perDomain) {
  const qs = [];
  perDomain.forEach((n, i) => { for (let k = 0; k < n; k++) qs.push({ id: `d${i + 1}-${k}`, domain: i + 1 }); });
  return qs;
}

test("mulberry32 is deterministic per seed and stays in [0, 1)", () => {
  const take = (rng) => Array.from({ length: 5 }, () => rng());
  const xs = take(C.mulberry32(42));
  assert.deepEqual(xs, take(C.mulberry32(42)));
  assert.notDeepEqual(xs, take(C.mulberry32(43)));
  assert.ok(xs.every((x) => x >= 0 && x < 1));
});

test("shuffle returns a permutation without mutating its input", () => {
  const items = [1, 2, 3, 4, 5, 6, 7, 8];
  const out = C.shuffle(items, C.mulberry32(1));
  assert.deepEqual(items, [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(out.slice().sort((a, b) => a - b), items);
  assert.notDeepEqual(out, items);
});

test("examQuotas apportions by largest remainder", () => {
  assert.deepEqual(C.examQuotas(DOMAINS, 65), { 1: 21, 2: 17, 3: 15, 4: 12 });
  assert.deepEqual(C.examQuotas(DOMAINS, 10), { 1: 3, 2: 3, 3: 2, 4: 2 });
});

test("sampleExam draws each domain's quota without duplicates", () => {
  const ids = C.sampleExam(bank([160, 130, 120, 90]), DOMAINS, 65, C.mulberry32(7));
  assert.equal(ids.length, 65);
  assert.equal(new Set(ids).size, 65);
  const count = (d) => ids.filter((id) => id.startsWith(`d${d}-`)).length;
  assert.deepEqual([1, 2, 3, 4].map(count), [21, 17, 15, 12]);
});

test("sampleExam interleaves domains rather than grouping them", () => {
  const ids = C.sampleExam(bank([160, 130, 120, 90]), DOMAINS, 65, C.mulberry32(7));
  assert.ok(!ids.slice(0, 21).every((id) => id.startsWith("d1-")));
});

test("sampleExam differs between seeds", () => {
  const qs = bank([160, 130, 120, 90]);
  assert.notDeepEqual(C.sampleExam(qs, DOMAINS, 65, C.mulberry32(1)), C.sampleExam(qs, DOMAINS, 65, C.mulberry32(2)));
});

test("isCorrect requires exactly the correct set", () => {
  assert.equal(C.isCorrect(["B"], ["B"]), true);
  assert.equal(C.isCorrect(["E", "B"], ["B", "E"]), true);
  assert.equal(C.isCorrect(["B"], ["B", "E"]), false);
  assert.equal(C.isCorrect([], ["B"]), false);
  assert.equal(C.isCorrect(["A", "B"], ["B"]), false);
});

test("toggleSelection replaces the pick for single-answer questions", () => {
  assert.deepEqual(C.toggleSelection(["A"], "C", 1), ["C"]);
});

test("toggleSelection caps choose-two at two picks and allows unpicking", () => {
  const two = C.toggleSelection(C.toggleSelection([], "A", 2), "C", 2);
  assert.deepEqual(two, ["A", "C"]);
  assert.deepEqual(C.toggleSelection(two, "D", 2), ["A", "C"]);
  assert.deepEqual(C.toggleSelection(two, "A", 2), ["C"]);
});

test("isOptionLocked locks only unpicked options once the cap is reached", () => {
  assert.equal(C.isOptionLocked(["A", "C"], "B", 2), true);
  assert.equal(C.isOptionLocked(["A", "C"], "A", 2), false);
  assert.equal(C.isOptionLocked(["A"], "B", 2), false);
  assert.equal(C.isOptionLocked(["A"], "B", 1), false);
});

test("canSubmit needs exactly selectN picks", () => {
  assert.equal(C.canSubmit([], 1), false);
  assert.equal(C.canSubmit(["A"], 1), true);
  assert.equal(C.canSubmit(["A"], 2), false);
  assert.equal(C.canSubmit(["A", "B"], 2), true);
});
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `node --test tests-js/`
Expected: FAIL with `Cannot find module '../template/app-core.js'`.

- [ ] **Step 3: Implement**

`template/app-core.js`:
```js
/* Pure study-app logic, shared by the browser app (global PebCore) and node tests (module.exports).
   Randomness and time are always passed in (rng, now) so behaviour is deterministic under test. */
(function (root) {
  "use strict";

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function shuffle(items, rng) {
    const out = items.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  function examQuotas(domains, total) {
    const weightSum = domains.reduce((sum, d) => sum + d.weight, 0);
    const exact = domains.map((d) => ({ id: d.id, value: (total * d.weight) / weightSum }));
    const quotas = {};
    exact.forEach((e) => { quotas[e.id] = Math.floor(e.value); });
    const leftover = total - exact.reduce((sum, e) => sum + quotas[e.id], 0);
    exact
      .slice()
      .sort((a, b) => (b.value - Math.floor(b.value)) - (a.value - Math.floor(a.value)) || a.id - b.id)
      .slice(0, leftover)
      .forEach((e) => { quotas[e.id] += 1; });
    return quotas;
  }

  function sampleExam(questions, domains, total, rng) {
    const quotas = examQuotas(domains, total);
    const picked = [];
    domains.forEach((d) => {
      const pool = questions.filter((q) => q.domain === d.id).map((q) => q.id);
      picked.push(...shuffle(pool, rng).slice(0, quotas[d.id]));
    });
    return shuffle(picked, rng);
  }

  function isCorrect(selected, correct) {
    return selected.length === correct.length && correct.every((k) => selected.includes(k));
  }

  function toggleSelection(selected, key, selectN) {
    if (selectN === 1) return [key];
    if (selected.includes(key)) return selected.filter((k) => k !== key);
    if (selected.length >= selectN) return selected.slice();
    return selected.concat([key]);
  }

  function isOptionLocked(selected, key, selectN) {
    return selectN > 1 && selected.length >= selectN && !selected.includes(key);
  }

  function canSubmit(selected, selectN) {
    return selected.length === selectN;
  }

  const api = {
    mulberry32, shuffle, examQuotas, sampleExam,
    isCorrect, toggleSelection, isOptionLocked, canSubmit,
  };
  root.PebCore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `node --test tests-js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add template/app-core.js tests-js/sampling.test.js
git commit -m "Add app core sampling, selection and grading logic"
```

---

### Task 8: App core — progress state, filters, passes, migration, import validation

**Files:**
- Modify: `template/app-core.js`. Add the functions above `const api`, and add them to `api`.
- Test: `tests-js/state.test.js`

**Interfaces:**
- Consumes: `shuffle` (Task 7).
- Produces, on `PebCore`:
  - `SCHEMA_VERSION = 1`
  - `createState(ids, bankVersion, rng)`, which returns `{schemaVersion, bankVersion, queue, passAnswered, questionStats, examHistory}`
  - `validateImport(obj) -> {ok: true} | {ok: false, error: string}`
  - `migrateState(state, ids, bankVersion, rng)`
  - `loadState(raw, ids, bankVersion, rng)`
  - `filterIds(state, "next" | "never" | "missed") -> id[]`
  - `sessionIds(state, filter, size: number | "all") -> id[]`
  - `recordAnswer(state, id, correct: bool, now: number, countsTowardPass: bool) -> state`
  - `newPass(state, rng) -> state`
- The shape of `questionStats[id]` is `{attempts, correct, lastResult: bool, lastAt: epochMs}`.
- Every function returns new objects and never mutates its input.

- [ ] **Step 1: Write the failing tests**

`tests-js/state.test.js`:
```js
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const IDS = ["a", "b", "c", "d"];
const fresh = () => C.createState(IDS, "v1", C.mulberry32(3));

test("createState shuffles every id into the queue with empty progress", () => {
  const s = fresh();
  assert.equal(s.schemaVersion, 1);
  assert.equal(s.bankVersion, "v1");
  assert.deepEqual(s.queue.slice().sort(), IDS);
  assert.deepEqual([s.passAnswered, s.questionStats, s.examHistory], [[], {}, []]);
});

test("recordAnswer accumulates stats and joins the pass only when asked", () => {
  let s = fresh();
  s = C.recordAnswer(s, "a", false, 1000, true);
  s = C.recordAnswer(s, "a", true, 2000, true);
  s = C.recordAnswer(s, "b", false, 3000, false);
  assert.deepEqual(s.questionStats.a, { attempts: 2, correct: 1, lastResult: true, lastAt: 2000 });
  assert.deepEqual(s.questionStats.b, { attempts: 1, correct: 0, lastResult: false, lastAt: 3000 });
  assert.deepEqual(s.passAnswered, ["a"]);
});

test("recordAnswer does not mutate the previous state", () => {
  const s0 = fresh();
  C.recordAnswer(s0, "a", true, 1, true);
  assert.deepEqual([s0.passAnswered, s0.questionStats], [[], {}]);
});

test("filters walk queue order", () => {
  let s = Object.assign(fresh(), { queue: ["d", "c", "b", "a"] });
  s = C.recordAnswer(s, "c", false, 1, true);
  s = C.recordAnswer(s, "a", true, 2, false);
  s = C.recordAnswer(s, "b", true, 3, true);
  s = C.recordAnswer(s, "b", false, 4, true);
  assert.deepEqual(C.filterIds(s, "next"), ["d", "a"]);
  assert.deepEqual(C.filterIds(s, "never"), ["d"]);
  assert.deepEqual(C.filterIds(s, "missed"), ["c", "b"]);
});

test("sessionIds limits to the session size unless 'all'", () => {
  const s = Object.assign(fresh(), { queue: ["d", "c", "b", "a"] });
  assert.deepEqual(C.sessionIds(s, "next", 2), ["d", "c"]);
  assert.deepEqual(C.sessionIds(s, "next", "all"), ["d", "c", "b", "a"]);
});

test("newPass reshuffles the queue and clears the pass but keeps stats", () => {
  let s = C.recordAnswer(fresh(), "a", true, 1, true);
  const next = C.newPass(s, C.mulberry32(9));
  assert.deepEqual(next.passAnswered, []);
  assert.deepEqual(next.queue.slice().sort(), IDS);
  assert.deepEqual(next.questionStats, s.questionStats);
});

test("migrateState keeps surviving order and stats, drops removed ids, appends new ids", () => {
  let s = Object.assign(C.createState(["a", "b", "c"], "v1", C.mulberry32(1)), { queue: ["c", "a", "b"] });
  s = C.recordAnswer(s, "b", true, 1, true);
  s = C.recordAnswer(s, "c", false, 2, true);
  const m = C.migrateState(s, ["a", "c", "x", "y"], "v2", C.mulberry32(1));
  assert.equal(m.bankVersion, "v2");
  assert.deepEqual(m.queue.slice(0, 2), ["c", "a"]);
  assert.deepEqual(m.queue.slice(2).sort(), ["x", "y"]);
  assert.deepEqual(Object.keys(m.questionStats), ["c"]);
  assert.deepEqual(m.passAnswered, ["c"]);
});

test("loadState starts fresh for missing, corrupted or partial stored data", () => {
  const unsupported = { schemaVersion: 2, bankVersion: "v1", queue: [], passAnswered: [], questionStats: {}, examHistory: [] };
  for (const raw of [null, undefined, "{", 42, [], {}, { schemaVersion: 1 }, unsupported]) {
    const s = C.loadState(raw, IDS, "v1", C.mulberry32(3));
    assert.deepEqual(s.queue.slice().sort(), IDS);
    assert.deepEqual(s.questionStats, {});
  }
});

test("loadState keeps valid stored data and migrates it to the current bank", () => {
  const stored = C.recordAnswer(Object.assign(fresh(), { queue: ["d", "c", "b", "a"] }), "a", true, 5, true);
  const same = C.loadState(JSON.parse(JSON.stringify(stored)), IDS, "v1", C.mulberry32(3));
  assert.deepEqual(same, stored);
  const moved = C.loadState(stored, ["a", "b"], "v2", C.mulberry32(3));
  assert.deepEqual([moved.bankVersion, moved.queue], ["v2", ["b", "a"]]);
});

test("validateImport accepts an exported state", () => {
  const exported = JSON.parse(JSON.stringify(C.recordAnswer(fresh(), "a", true, 1, true)));
  assert.deepEqual(C.validateImport(exported), { ok: true });
});
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `node --test tests-js/`
Expected: FAIL with `C.createState is not a function`.

- [ ] **Step 3: Implement**

Insert into `template/app-core.js`, directly above `const api = {`:
```js
  const SCHEMA_VERSION = 1;

  function createState(ids, bankVersion, rng) {
    return {
      schemaVersion: SCHEMA_VERSION, bankVersion, queue: shuffle(ids, rng),
      passAnswered: [], questionStats: {}, examHistory: [],
    };
  }

  const isObject = (x) => !!x && typeof x === "object" && !Array.isArray(x);
  const isStringArray = (x) => Array.isArray(x) && x.every((v) => typeof v === "string");
  const isStat = (s) => isObject(s) && Number.isFinite(s.attempts) && Number.isFinite(s.correct) &&
    typeof s.lastResult === "boolean" && Number.isFinite(s.lastAt);

  function validateImport(obj) {
    if (!isObject(obj)) return { ok: false, error: "This is not a progress file." };
    if (obj.schemaVersion !== SCHEMA_VERSION) return { ok: false, error: "Unsupported progress file version." };
    if (typeof obj.bankVersion !== "string") return { ok: false, error: "Progress file is missing its bank version." };
    if (!isStringArray(obj.queue) || !isStringArray(obj.passAnswered)) {
      return { ok: false, error: "Progress file has an invalid question queue." };
    }
    if (!isObject(obj.questionStats) || !Object.values(obj.questionStats).every(isStat)) {
      return { ok: false, error: "Progress file has invalid question statistics." };
    }
    if (!Array.isArray(obj.examHistory) || !obj.examHistory.every(isObject)) {
      return { ok: false, error: "Progress file has an invalid exam history." };
    }
    return { ok: true };
  }

  function migrateState(state, ids, bankVersion, rng) {
    const valid = new Set(ids);
    const kept = state.queue.filter((id) => valid.has(id));
    const known = new Set(kept);
    const added = shuffle(ids.filter((id) => !known.has(id)), rng);
    const questionStats = {};
    Object.keys(state.questionStats).forEach((id) => { if (valid.has(id)) questionStats[id] = state.questionStats[id]; });
    return {
      schemaVersion: SCHEMA_VERSION, bankVersion, queue: kept.concat(added),
      passAnswered: state.passAnswered.filter((id) => valid.has(id)),
      questionStats, examHistory: state.examHistory.slice(),
    };
  }

  function loadState(raw, ids, bankVersion, rng) {
    return validateImport(raw).ok ? migrateState(raw, ids, bankVersion, rng) : createState(ids, bankVersion, rng);
  }

  function filterIds(state, filter) {
    const pass = new Set(state.passAnswered);
    const stats = state.questionStats;
    const keep = {
      next: (id) => !pass.has(id),
      never: (id) => !stats[id],
      missed: (id) => !!stats[id] && stats[id].lastResult === false,
    }[filter];
    return state.queue.filter(keep);
  }

  function sessionIds(state, filter, size) {
    const ids = filterIds(state, filter);
    return size === "all" ? ids : ids.slice(0, size);
  }

  function recordAnswer(state, id, correct, now, countsTowardPass) {
    const prev = state.questionStats[id] || { attempts: 0, correct: 0 };
    const stat = { attempts: prev.attempts + 1, correct: prev.correct + (correct ? 1 : 0), lastResult: correct, lastAt: now };
    const joinPass = countsTowardPass && !state.passAnswered.includes(id);
    return Object.assign({}, state, {
      questionStats: Object.assign({}, state.questionStats, { [id]: stat }),
      passAnswered: joinPass ? state.passAnswered.concat([id]) : state.passAnswered,
    });
  }

  function newPass(state, rng) {
    return Object.assign({}, state, { queue: shuffle(state.queue, rng), passAnswered: [] });
  }
```

Replace the `api` object with:
```js
  const api = {
    mulberry32, shuffle, examQuotas, sampleExam,
    isCorrect, toggleSelection, isOptionLocked, canSubmit,
    SCHEMA_VERSION, createState, validateImport, migrateState, loadState,
    filterIds, sessionIds, recordAnswer, newPass,
  };
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `node --test tests-js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add template/app-core.js tests-js/state.test.js
git commit -m "Add progress state, practice filters, passes and migration to app core"
```

---

### Task 9: App core — exam grading, statistics, clock, import rejection

**Files:**
- Modify: `template/app-core.js`. Add the functions above `const api`, and add them to `api`.
- Test: `tests-js/stats.test.js`

**Interfaces:**
- Consumes: `isCorrect` (Task 7), and `recordAnswer`, `createState` and `validateImport` (Task 8).
- Produces, on `PebCore`:
  - `pct(n, d) -> integer`
  - `gradeExam(questions, answers {id: keys[]}) -> {correct, total, pct, byDomain {d: {correct, total}}, results {id: bool}}`
  - `recordExam(state, questions, grade, startedAt, now) -> state`
  - `summarize(state, questions) -> {overall, byDomain, byVideo}`, where each bucket is `{attempts, correct, seen, pct}`
  - `weakest(state, limit) -> id[]`, covering missed questions only
  - `remainingMs(deadline, now)`
  - `formatClock(ms) -> "m:ss"`
  - `videoUrl(q) -> string`

- [ ] **Step 1: Write the failing tests**

`tests-js/stats.test.js`:
```js
const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../template/app-core.js");

const QS = [
  { id: "a", domain: 1, video: 1, correct: ["B"] },
  { id: "b", domain: 1, video: 2, correct: ["A", "C"] },
  { id: "c", domain: 2, video: 2, correct: ["D"] },
];
const fresh = () => C.createState(["a", "b", "c"], "v1", C.mulberry32(1));

test("pct rounds and treats a zero denominator as 0", () => {
  assert.equal(C.pct(1, 3), 33);
  assert.equal(C.pct(2, 3), 67);
  assert.equal(C.pct(0, 0), 0);
});

test("gradeExam scores exact matches, counts unanswered and partial as wrong, and splits by domain", () => {
  const g = C.gradeExam(QS, { a: ["B"], b: ["A"] });
  assert.deepEqual([g.correct, g.total, g.pct], [1, 3, 33]);
  assert.deepEqual(g.byDomain, { 1: { correct: 1, total: 2 }, 2: { correct: 0, total: 1 } });
  assert.deepEqual(g.results, { a: true, b: false, c: false });
});

test("recordExam records every question as an attempt outside the pass and appends history", () => {
  const g = C.gradeExam(QS, { a: ["B"] });
  const s = C.recordExam(fresh(), QS, g, 10000, 70000);
  assert.deepEqual(Object.keys(s.questionStats).sort(), ["a", "b", "c"]);
  assert.deepEqual(s.questionStats.a, { attempts: 1, correct: 1, lastResult: true, lastAt: 70000 });
  assert.deepEqual(s.passAnswered, []);
  assert.deepEqual(s.examHistory, [{ at: 70000, scorePct: 33, correct: 1, total: 3, byDomain: g.byDomain, durationSec: 60 }]);
});

test("summarize reports accuracy overall, per domain and per video", () => {
  let s = fresh();
  s = C.recordAnswer(s, "a", true, 1, true);
  s = C.recordAnswer(s, "a", false, 2, true);
  s = C.recordAnswer(s, "c", true, 3, true);
  const sum = C.summarize(s, QS);
  assert.deepEqual(sum.overall, { attempts: 3, correct: 2, seen: 2, pct: 67 });
  assert.deepEqual(sum.byDomain[1], { attempts: 2, correct: 1, seen: 1, pct: 50 });
  assert.deepEqual(sum.byVideo[2], { attempts: 1, correct: 1, seen: 1, pct: 100 });
  assert.equal(sum.byVideo[3], undefined);
});

test("weakest ranks missed questions by accuracy, then more attempts, then most recent", () => {
  const questionStats = {
    a: { attempts: 2, correct: 1, lastResult: true, lastAt: 5 },
    b: { attempts: 4, correct: 2, lastResult: false, lastAt: 1 },
    c: { attempts: 1, correct: 0, lastResult: false, lastAt: 2 },
    d: { attempts: 1, correct: 0, lastResult: false, lastAt: 9 },
    e: { attempts: 3, correct: 3, lastResult: true, lastAt: 9 },
  };
  const s = Object.assign(fresh(), { questionStats });
  assert.deepEqual(C.weakest(s, 20), ["d", "c", "b", "a"]);
  assert.deepEqual(C.weakest(s, 2), ["d", "c"]);
});

test("remainingMs counts down to the deadline and floors at zero", () => {
  assert.equal(C.remainingMs(10000, 4000), 6000);
  assert.equal(C.remainingMs(10000, 12000), 0);
});

test("formatClock shows minutes:seconds, rounding partial seconds up", () => {
  assert.equal(C.formatClock(130 * 60000), "130:00");
  assert.equal(C.formatClock(61001), "1:02");
  assert.equal(C.formatClock(0), "0:00");
});

test("videoUrl deep-links to the question's chapter", () => {
  assert.equal(C.videoUrl({ videoId: "YJg7z6r6jsQ", timestampSec: 65 }), "https://www.youtube.com/watch?v=YJg7z6r6jsQ&t=65s");
});

test("validateImport rejects malformed files with a reason", () => {
  const good = fresh();
  const bad = [
    null, [], "text",
    Object.assign({}, good, { schemaVersion: 2 }),
    Object.assign({}, good, { bankVersion: 3 }),
    Object.assign({}, good, { queue: [1] }),
    Object.assign({}, good, { passAnswered: "a" }),
    Object.assign({}, good, { questionStats: { a: { attempts: "2", correct: 1, lastResult: true, lastAt: 1 } } }),
    Object.assign({}, good, { questionStats: { a: { attempts: 2, correct: 1, lastResult: null, lastAt: 1 } } }),
    Object.assign({}, good, { examHistory: {} }),
  ];
  bad.forEach((obj) => {
    const r = C.validateImport(obj);
    assert.equal(r.ok, false);
    assert.equal(typeof r.error, "string");
  });
});
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `node --test tests-js/`
Expected: FAIL with `C.pct is not a function`.

- [ ] **Step 3: Implement**

Insert into `template/app-core.js`, directly above `const api = {`:
```js
  function pct(n, d) {
    return d ? Math.round((100 * n) / d) : 0;
  }

  function gradeExam(questions, answers) {
    const byDomain = {};
    const results = {};
    let correct = 0;
    questions.forEach((q) => {
      const ok = isCorrect(answers[q.id] || [], q.correct);
      results[q.id] = ok;
      const bucket = byDomain[q.domain] || (byDomain[q.domain] = { correct: 0, total: 0 });
      bucket.total += 1;
      if (ok) { bucket.correct += 1; correct += 1; }
    });
    return { correct, total: questions.length, pct: pct(correct, questions.length), byDomain, results };
  }

  function recordExam(state, questions, grade, startedAt, now) {
    let next = state;
    questions.forEach((q) => { next = recordAnswer(next, q.id, grade.results[q.id], now, false); });
    const entry = {
      at: now, scorePct: grade.pct, correct: grade.correct, total: grade.total,
      byDomain: grade.byDomain, durationSec: Math.round((now - startedAt) / 1000),
    };
    return Object.assign({}, next, { examHistory: next.examHistory.concat([entry]) });
  }

  function summarize(state, questions) {
    const empty = () => ({ attempts: 0, correct: 0, seen: 0, pct: 0 });
    const overall = empty();
    const byDomain = {};
    const byVideo = {};
    questions.forEach((q) => {
      const s = state.questionStats[q.id];
      if (!s) return;
      const buckets = [overall, byDomain[q.domain] || (byDomain[q.domain] = empty()), byVideo[q.video] || (byVideo[q.video] = empty())];
      buckets.forEach((b) => { b.attempts += s.attempts; b.correct += s.correct; b.seen += 1; });
    });
    [overall].concat(Object.values(byDomain), Object.values(byVideo)).forEach((b) => { b.pct = pct(b.correct, b.attempts); });
    return { overall, byDomain, byVideo };
  }

  function weakest(state, limit) {
    const accuracy = (s) => s.correct / s.attempts;
    return Object.keys(state.questionStats)
      .map((id) => ({ id, s: state.questionStats[id] }))
      .filter((x) => x.s.attempts > 0 && x.s.correct < x.s.attempts)
      .sort((a, b) => accuracy(a.s) - accuracy(b.s) || b.s.attempts - a.s.attempts || b.s.lastAt - a.s.lastAt)
      .slice(0, limit)
      .map((x) => x.id);
  }

  function remainingMs(deadline, now) {
    return Math.max(0, deadline - now);
  }

  function formatClock(ms) {
    const total = Math.ceil(ms / 1000);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function videoUrl(q) {
    return `https://www.youtube.com/watch?v=${q.videoId}&t=${q.timestampSec}s`;
  }
```

Replace the `api` object with:
```js
  const api = {
    mulberry32, shuffle, examQuotas, sampleExam,
    isCorrect, toggleSelection, isOptionLocked, canSubmit,
    SCHEMA_VERSION, createState, validateImport, migrateState, loadState,
    filterIds, sessionIds, recordAnswer, newPass,
    pct, gradeExam, recordExam, summarize, weakest, remainingMs, formatClock, videoUrl,
  };
```

`weakest` lists only questions with at least one miss. A question answered correctly every time isn't "weak", so it stays off the list even when fewer than 20 questions have been missed.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `node --test tests-js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add template/app-core.js tests-js/stats.test.js
git commit -m "Add exam grading, statistics and timer helpers to app core"
```

---

### Task 10: Study app UI, dist smoke test, demo build

**Files:**
- Create: `template/app.html`, `tests/test_dist_smoke.py`, `tests/make_demo.py`

**Interfaces:**
- Consumes: every `PebCore` function (Tasks 7–9), and the global `BANK` with the keys `bankVersion`, `exam`, `domains`, `videos` and `questions` (Task 5).
- The template must contain `<script>/*__CORE__*/</script>` and `<script>/*__BANK__*/</script>`, in that order, as the first two `<script>` tags with no attributes. The smoke test depends on this.

- [ ] **Step 1: Write the failing smoke test**

`tests/test_dist_smoke.py`:
```python
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from factory import make_root, rewrite, video_id
from peb.build import build

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
TRICKY = "Use </script><!-- & <b>tags</b>?"

SMOKE_JS = r"""
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const probe = ";JSON.stringify({n: BANK.questions.length, stem: BANK.questions[0].stem, title: document.title," +
  " quotas: PebCore.examQuotas(BANK.domains, BANK.exam.questions)})";
const sandbox = { document: { title: (html.match(/<title>(.*?)<\/title>/) || [])[1] } };
process.stdout.write(vm.runInNewContext(blocks[0] + "\n" + blocks[1] + probe, sandbox));
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_built_app_embeds_loadable_core_and_bank(tmp_path):
    root = make_root(tmp_path)
    rewrite(root / "bank" / f"01-{video_id(1)}.json", lambda b: b["questions"][0].update(stem=TRICKY))
    shutil.copytree(REPO / "template", root / "template")
    out = build(root)
    script = tmp_path / "smoke.js"
    script.write_text(SMOKE_JS, encoding="utf-8")
    result = subprocess.run([NODE, str(script), str(out)], capture_output=True, text=True, encoding="utf-8", check=True)
    data = json.loads(result.stdout)
    assert data == {"n": 80, "stem": TRICKY, "title": "DVA-C02 Practice (unofficial)",
                    "quotas": {"1": 21, "2": 17, "3": 15, "4": 12}}
```

Run: `.venv/Scripts/python -m pytest tests/test_dist_smoke.py -q`
Expected: FAIL with `FileNotFoundError` for `template/app.html`.

- [ ] **Step 2: Write `template/app.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DVA-C02 Practice (unofficial)</title>
<style>
  :root{
    --ink:#16191f; --muted:#5f6b7a; --bg:#f2f3f3; --card:#ffffff; --border:#d5dbdb;
    --squid:#232f3e; --squid-dark:#161e2d; --orange:#ff9900; --orange-hover:#ec7211; --on-orange:#16191f;
    --green:#1d8102; --green-bg:#f2fcf3; --red:#d13212; --red-bg:#fdf3f1;
    --amber:#8a5a00; --amber-bg:#fff7e6; --info:#0972d3; --info-bg:#f1faff; --chip:#ffffff; --track:#e9ebed;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --ink:#e9ebed; --muted:#9ba7b6; --bg:#0f141a; --card:#192534; --border:#414d5c;
      --squid:#0f1b2a; --squid-dark:#0a121c;
      --green:#62d26f; --green-bg:#11261a; --red:#ff7a5c; --red-bg:#2e1511;
      --amber:#ffc56b; --amber-bg:#2d2210; --info:#5fb3ff; --info-bg:#0e2338; --chip:#192534; --track:#2a3746;
    }
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5;font-size:15px}
  a{color:var(--info)}
  .topbar{background:var(--squid);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 20px;border-bottom:3px solid var(--orange);flex-wrap:wrap}
  .topbar h1{margin:0;font-size:17px;font-weight:700}
  .topbar .unofficial{font-weight:400;opacity:.75;font-size:13px}
  .topbar .sub{font-size:12px;opacity:.8}
  .top-right{display:flex;align-items:center;gap:14px}
  .toplink{background:none;border:none;color:#fff;font:inherit;cursor:pointer;opacity:.9}
  .toplink:hover{color:var(--orange)}
  .timer{font-variant-numeric:tabular-nums;font-size:20px;font-weight:700;background:var(--squid-dark);border:1px solid #414d5c;padding:4px 12px;border-radius:6px}
  .timer.low{background:#d13212;border-color:#d13212}
  .app{max-width:1100px;margin:0 auto;padding:20px 16px 80px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:20px 24px;margin-bottom:16px;box-shadow:0 1px 1px rgba(0,28,36,.1)}
  h2{margin:0 0 10px;font-size:20px} h3{font-size:15px;margin:16px 0 8px} h4{margin:14px 0 4px;font-size:14px}
  .muted{color:var(--muted)} .small{font-size:13px}
  .btn{display:inline-flex;align-items:center;justify-content:center;background:var(--orange);color:var(--on-orange);border:2px solid var(--orange);padding:8px 20px;border-radius:20px;font-family:inherit;font-size:14px;font-weight:700;line-height:1.4;cursor:pointer}
  .btn:hover{background:var(--orange-hover);border-color:var(--orange-hover)}
  .btn.secondary{background:transparent;color:var(--ink);border-color:var(--ink)}
  .btn.secondary:hover{background:var(--track)}
  .btn.danger{background:transparent;color:var(--red);border-color:var(--red)}
  .btn:disabled{opacity:.45;cursor:not-allowed}
  .btn.block{width:100%;margin-top:10px}
  .btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
  .linkbtn{background:none;border:none;color:var(--info);cursor:pointer;font:inherit;text-decoration:underline;padding:0;text-align:left}
  .banner{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber);border-radius:8px;padding:10px 14px;margin-bottom:16px}
  .progress{height:10px;background:var(--track);border-radius:6px;overflow:hidden;margin:6px 0 16px}
  .progress-fill{height:100%;background:var(--orange)}
  .progress-label{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;font-size:14px}
  .table-wrap{overflow-x:auto}
  .table{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}
  .table th,.table td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border)}
  .table th{color:var(--muted);font-size:12px;text-transform:uppercase;font-weight:600}
  .chips{display:flex;gap:8px;flex-wrap:wrap}
  .chip{padding:6px 14px;border-radius:16px;border:1px solid var(--border);background:var(--chip);color:var(--ink);font-size:13px;cursor:pointer;font-family:inherit}
  .chip.active{background:var(--ink);color:var(--card);border-color:var(--ink)}
  .q-header{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
  .q-meta{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}
  .q-count{font-size:13px;color:var(--muted)}
  .q-title{font-size:16px;margin:8px 0 0}
  .q-text{font-size:16px;margin:10px 0 14px;white-space:pre-line}
  .select-hint{display:inline-block;background:var(--amber-bg);color:var(--amber);font-size:12px;font-weight:700;padding:3px 10px;border-radius:12px;margin-bottom:12px}
  .option{display:flex;gap:10px;align-items:flex-start;padding:11px 14px;border:1.5px solid var(--border);border-radius:8px;margin-bottom:8px;cursor:pointer}
  .option:hover{border-color:var(--orange)}
  .option.selected{border-color:var(--orange);background:var(--amber-bg)}
  .option.locked{opacity:.55;cursor:not-allowed}
  .option.correct{border-color:var(--green);background:var(--green-bg)}
  .option.incorrect{border-color:var(--red);background:var(--red-bg)}
  .option input{margin-top:4px;accent-color:var(--orange);width:16px;height:16px;flex-shrink:0}
  .opt-key{font-weight:700}
  .footer-nav{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:18px}
  .verdict{margin-top:16px;padding:10px 14px;border-radius:8px;font-weight:700}
  .verdict.right{background:var(--green-bg);color:var(--green);border:1px solid var(--green)}
  .verdict.wrong{background:var(--red-bg);color:var(--red);border:1px solid var(--red)}
  .explain{margin-top:10px;padding:4px 16px 12px;border-left:3px solid var(--orange);background:var(--info-bg);border-radius:6px;font-size:14px}
  .explain p{margin:4px 0}
  ul.plain{list-style:none;padding:0;margin:4px 0}
  .why{padding:6px 0;border-bottom:1px dashed var(--border)}
  .why:last-child{border-bottom:none}
  .tag{font-size:11px;font-weight:700;padding:1px 8px;border-radius:10px;text-transform:uppercase;margin-left:4px}
  .tag.right{background:var(--green-bg);color:var(--green)} .tag.wrong{background:var(--red-bg);color:var(--red)} .tag.pick{background:var(--track);color:var(--ink)}
  .exam-layout{display:grid;grid-template-columns:230px 1fr;gap:16px;align-items:start}
  .nav-panel{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;position:sticky;top:12px}
  .nav-panel h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;color:var(--muted)}
  .nav-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:5px}
  .nav-btn{aspect-ratio:1;border-radius:4px;border:1px solid var(--border);background:var(--chip);color:var(--ink);font-size:11px;cursor:pointer;padding:0;position:relative}
  .nav-btn.answered{background:var(--ink);color:var(--card);border-color:var(--ink)}
  .nav-btn.current{outline:2px solid var(--orange);outline-offset:1px;font-weight:700}
  .nav-btn.flagged::after{content:"";position:absolute;top:2px;right:2px;width:6px;height:6px;border-radius:50%;background:var(--orange)}
  .legend{margin-top:10px;font-size:11px;color:var(--muted);display:grid;gap:3px}
  .dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:middle;border:1px solid var(--border)}
  .dot.answered{background:var(--ink)} .dot.flag{background:var(--orange);border-radius:50%;border-color:var(--orange)}
  .score-hero{text-align:center}
  .score-big{font-size:46px;font-weight:800}
  .pass-pill{display:inline-block;margin-top:10px;padding:5px 16px;border-radius:16px;font-weight:700}
  .pass-pill.pass{background:var(--green-bg);color:var(--green)} .pass-pill.fail{background:var(--red-bg);color:var(--red)}
  .bar{display:inline-block;vertical-align:middle;width:90px;height:8px;background:var(--track);border-radius:4px;overflow:hidden;margin-right:6px}
  .bar>span{display:block;height:100%;background:var(--orange)}
  .review-item{border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:12px}
  .opt-line{font-size:14px;margin:2px 0}
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .stat{border:1px solid var(--border);border-radius:8px;padding:12px}
  .stat-num{font-size:26px;font-weight:800}
  .hidden{display:none !important}
  @media (max-width:760px){.exam-layout{grid-template-columns:1fr}.nav-panel{position:static}.card{padding:16px}}
</style>
</head>
<body>
<header class="topbar">
  <div>
    <h1>DVA-C02 Practice <span class="unofficial">(unofficial)</span></h1>
    <div class="sub">AWS Certified Developer – Associate · study app</div>
  </div>
  <div class="top-right">
    <button class="toplink" data-go="home">Home</button>
    <button class="toplink" data-go="stats">Statistics</button>
    <div id="timerBox" class="timer hidden">130:00</div>
  </div>
</header>
<main class="app">
  <div id="storageBanner" class="banner hidden">Progress can't be saved in this browser (storage is unavailable). Use Export progress before closing.</div>

  <section id="homeScreen">
    <div class="card">
      <h2>Welcome</h2>
      <p class="muted">Unofficial study material built from the “Full Course: 500 Real Exam Questions” YouTube playlist. Not affiliated with or endorsed by AWS.</p>
      <div class="progress-label"><span id="passProgressText"></span><span id="lifetimeText" class="muted"></span></div>
      <div class="progress"><div class="progress-fill" id="passProgressFill"></div></div>
      <div class="table-wrap"><table class="table" id="bankTable"></table></div>
      <div class="btn-row">
        <button class="btn" data-go="practiceSetup">Practice</button>
        <button class="btn" data-go="examStart">Timed exam</button>
        <button class="btn secondary" data-go="stats">Statistics</button>
      </div>
    </div>
    <div class="card">
      <h3>Your progress data</h3>
      <p class="small muted">Progress is stored in this browser. Keep this file in a fixed location (moving or renaming it can lose progress in some browsers) and export regularly.</p>
      <div class="btn-row">
        <button class="btn secondary" id="exportBtn">Export progress</button>
        <label class="btn secondary">Import progress<input type="file" id="importInput" accept="application/json,.json" hidden></label>
        <button class="btn danger" id="resetBtn">Reset progress</button>
      </div>
      <p id="dataMsg" class="small"></p>
    </div>
  </section>

  <section id="practiceSetupScreen" class="hidden">
    <div class="card">
      <h2>Practice</h2>
      <h3>Which questions</h3>
      <div class="chips">
        <button class="chip" data-filter="next">Next in pass</button>
        <button class="chip" data-filter="never">Never answered</button>
        <button class="chip" data-filter="missed">Previously missed</button>
      </div>
      <h3>Session size</h3>
      <div class="chips">
        <button class="chip" data-size="10">10</button>
        <button class="chip" data-size="20">20</button>
        <button class="chip" data-size="50">50</button>
        <button class="chip" data-size="all">All</button>
      </div>
      <p id="filterInfo" class="muted"></p>
      <div class="btn-row">
        <button class="btn" id="startPracticeBtn">Start</button>
        <button class="btn secondary hidden" id="newPassBtn">Start a new pass</button>
      </div>
    </div>
  </section>

  <section id="practiceScreen" class="hidden">
    <div class="card">
      <div class="q-header"><span class="q-meta" id="pMeta"></span><span class="q-count" id="pCount"></span></div>
      <h2 class="q-title" id="pTitle"></h2>
      <div class="q-text" id="pStem"></div>
      <div id="pHint" class="select-hint hidden"></div>
      <div id="pOptions"></div>
      <div id="pFeedback"></div>
      <div class="footer-nav">
        <button class="btn secondary" id="pQuitBtn">End session</button>
        <div>
          <button class="btn" id="pSubmitBtn">Submit</button>
          <button class="btn hidden" id="pNextBtn">Next →</button>
        </div>
      </div>
    </div>
  </section>

  <section id="practiceSummaryScreen" class="hidden">
    <div class="card">
      <h2>Session complete</h2>
      <div id="summaryBody"></div>
      <div class="btn-row">
        <button class="btn" data-go="practiceSetup">Another session</button>
        <button class="btn secondary" data-go="home">Home</button>
      </div>
    </div>
  </section>

  <section id="examStartScreen" class="hidden">
    <div class="card">
      <h2>Timed exam</h2>
      <p id="examInfo"></p>
      <div class="table-wrap"><table class="table" id="examQuotaTable"></table></div>
      <ul>
        <li>Questions are drawn at random in the DVA-C02 exam guide's domain proportions.</li>
        <li>Answers and explanations appear only after you submit, just like exam day.</li>
        <li>Flag questions to revisit, and jump anywhere with the navigator.</li>
        <li>The timer auto-submits at 0:00. Reloading or closing the page abandons the exam.</li>
        <li>The passing line here is 72%, an approximation: the real exam uses a scaled score of 720/1000.</li>
      </ul>
      <div class="btn-row"><button class="btn" id="beginBtn">Begin exam</button></div>
    </div>
  </section>

  <section id="examScreen" class="hidden">
    <div class="exam-layout">
      <aside class="nav-panel">
        <h3>Questions</h3>
        <div class="nav-grid" id="navGrid"></div>
        <div class="legend">
          <div><span class="dot answered"></span>Answered</div>
          <div><span class="dot"></span>Not answered</div>
          <div><span class="dot flag"></span>Flagged</div>
        </div>
        <button class="btn secondary block" id="flagBtn">Flag for review</button>
        <button class="btn block" id="submitExamBtn">Submit exam</button>
      </aside>
      <div class="card">
        <div class="q-header"><span class="q-meta" id="eMeta"></span><span class="q-count" id="eCount"></span></div>
        <div class="q-text" id="eStem"></div>
        <div id="eHint" class="select-hint hidden"></div>
        <div id="eOptions"></div>
        <div class="footer-nav">
          <button class="btn secondary" id="ePrevBtn">← Previous</button>
          <button class="btn" id="eNextBtn">Next →</button>
        </div>
      </div>
    </div>
  </section>

  <section id="resultsScreen" class="hidden">
    <div class="card score-hero">
      <div class="q-meta">Your result</div>
      <div class="score-big" id="scoreBig"></div>
      <div class="muted" id="scoreSub"></div>
      <span class="pass-pill" id="passPill"></span>
      <p class="small muted">Passing line 72%, an approximation: the real exam uses a scaled score of 720/1000.</p>
      <div class="table-wrap"><table class="table" id="domainResults"></table></div>
      <div class="btn-row" style="justify-content:center">
        <button class="btn" data-go="examStart">New exam</button>
        <button class="btn secondary" data-go="home">Home</button>
      </div>
    </div>
    <div class="card">
      <h2>Review</h2>
      <div class="chips">
        <button class="chip" data-review="all">All</button>
        <button class="chip" data-review="incorrect">Incorrect</button>
        <button class="chip" data-review="flagged">Flagged</button>
      </div>
      <div id="reviewList"></div>
    </div>
  </section>

  <section id="statsScreen" class="hidden">
    <div class="card"><h2>Statistics</h2><div class="stat-grid" id="statsOverall"></div></div>
    <div class="card"><h3>By domain</h3><div class="table-wrap"><table class="table" id="statsDomains"></table></div></div>
    <div class="card"><h3>Weakest questions</h3><div id="statsWeakest"></div></div>
    <div class="card"><h3>Exam history</h3><div class="table-wrap"><table class="table" id="statsExams"></table></div></div>
    <div class="card"><h3>By video</h3><div class="table-wrap"><table class="table" id="statsVideos"></table></div></div>
  </section>
</main>

<script>/*__CORE__*/</script>
<script>/*__BANK__*/</script>
<script>
(function () {
  "use strict";
  const C = PebCore;
  const STORAGE_KEY = "peb:dva-c02";
  const $ = (id) => document.getElementById(id);
  const QMAP = {};
  BANK.questions.forEach((q) => { QMAP[q.id] = q; });
  const IDS = BANK.questions.map((q) => q.id);
  const DOMAIN_NAME = {};
  BANK.domains.forEach((d) => { DOMAIN_NAME[d.id] = d.name; });
  const override = Number(new URLSearchParams(location.search).get("examMinutes"));
  const EXAM_MINUTES = override > 0 ? override : BANK.exam.minutes;
  const SCREENS = ["home", "practiceSetup", "practice", "practiceSummary", "examStart", "exam", "results", "stats"];
  const FILTER_TEXT = { next: "questions left in this pass", never: "questions you have never answered", missed: "questions you missed last time" };

  let storageOk = true;
  let state = C.loadState(readStored(), IDS, BANK.bankVersion, Math.random);
  let setup = { filter: "next", size: 20 };
  let practice = null;
  let exam = null;
  let lastExam = null;
  save();

  function readStored() {
    let raw = null;
    try { raw = localStorage.getItem(STORAGE_KEY); } catch (e) { storageOk = false; return null; }
    try { return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { storageOk = false; }
    $("storageBanner").classList.toggle("hidden", storageOk);
  }

  function esc(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function bar(p) { return `<span class="bar"><span style="width:${p}%"></span></span>`; }
  function questionMeta(q) { return `Domain ${q.domain} · ${DOMAIN_NAME[q.domain]} · Task ${q.task}`; }
  function videoLabel(v) { return `Part ${v.index} (Q${(v.index - 1) * 20 + 1}–${v.index * 20})`; }

  function show(name) {
    SCREENS.forEach((s) => $(s + "Screen").classList.toggle("hidden", s !== name));
    const renderers = { home: renderHome, practiceSetup: renderPracticeSetup, examStart: renderExamStart, stats: renderStats };
    if (renderers[name]) renderers[name]();
    window.scrollTo(0, 0);
  }

  function markChips(attr, value) {
    document.querySelectorAll(`[data-${attr}]`).forEach((c) => c.classList.toggle("active", c.dataset[attr] === value));
  }

  function setHint(el, selectN) {
    el.textContent = `Choose ${selectN}`;
    el.classList.toggle("hidden", selectN < 2);
  }

  function quotaTableHtml() {
    const counts = {};
    BANK.questions.forEach((q) => { counts[q.domain] = (counts[q.domain] || 0) + 1; });
    const quotas = C.examQuotas(BANK.domains, BANK.exam.questions);
    return "<tr><th>Domain</th><th>Weight</th><th>In bank</th><th>Per exam</th></tr>" +
      BANK.domains.map((d) => `<tr><td>${d.id}. ${esc(d.name)}</td><td>${d.weight}%</td><td>${counts[d.id] || 0}</td><td>${quotas[d.id]}</td></tr>`).join("") +
      `<tr><td><b>Total</b></td><td></td><td><b>${IDS.length}</b></td><td><b>${BANK.exam.questions}</b></td></tr>`;
  }

  // ---------- Home ----------
  function renderHome() {
    const answered = state.passAnswered.length;
    const sum = C.summarize(state, BANK.questions);
    $("passProgressText").textContent = `${answered} / ${IDS.length} answered this pass`;
    $("lifetimeText").textContent = sum.overall.attempts ? `Lifetime accuracy ${sum.overall.pct}%` : "No answers yet";
    $("passProgressFill").style.width = `${IDS.length ? (100 * answered) / IDS.length : 0}%`;
    $("bankTable").innerHTML = quotaTableHtml();
  }

  function dataMsg(text, isError) {
    $("dataMsg").textContent = text;
    $("dataMsg").style.color = isError ? "var(--red)" : "var(--green)";
  }

  function exportProgress() {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `dva-c02-progress-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    dataMsg("Progress exported.");
  }

  function importProgress(file) {
    const reader = new FileReader();
    reader.onload = () => {
      let obj;
      try { obj = JSON.parse(reader.result); } catch (e) { dataMsg("That file isn't valid JSON.", true); return; }
      const check = C.validateImport(obj);
      if (!check.ok) { dataMsg(check.error, true); return; }
      if (!confirm("Replace your current progress with the imported file?")) return;
      state = C.loadState(obj, IDS, BANK.bankVersion, Math.random);
      save();
      renderHome();
      dataMsg("Progress imported.");
    };
    reader.readAsText(file);
  }

  function resetProgress() {
    if (!confirm("Reset all progress and statistics? This can't be undone.")) return;
    state = C.createState(IDS, BANK.bankVersion, Math.random);
    save();
    renderHome();
    dataMsg("Progress reset.");
  }

  // ---------- Practice ----------
  function renderPracticeSetup() {
    markChips("filter", setup.filter);
    markChips("size", String(setup.size));
    const available = C.filterIds(state, setup.filter).length;
    const exhausted = setup.filter === "next" && available === 0;
    $("filterInfo").textContent = available
      ? `${available} ${FILTER_TEXT[setup.filter]}.`
      : exhausted ? "You've answered every question in this pass." : `No ${FILTER_TEXT[setup.filter]}.`;
    $("startPracticeBtn").disabled = available === 0;
    $("newPassBtn").classList.toggle("hidden", !exhausted);
  }

  function startPractice(ids) {
    practice = { ids, i: 0, selected: [], submitted: false, results: [] };
    show("practice");
    renderPracticeQuestion();
  }

  function renderPracticeQuestion() {
    const q = QMAP[practice.ids[practice.i]];
    $("pMeta").textContent = questionMeta(q);
    $("pCount").textContent = practice.ids.length === 1 ? "Single question" : `Question ${practice.i + 1} of ${practice.ids.length} this session`;
    $("pTitle").textContent = practice.submitted ? `Q${q.n} · ${q.chapterTitle}` : `Q${q.n}`;
    $("pStem").textContent = q.stem;
    setHint($("pHint"), q.selectN);
    renderOptions($("pOptions"), q, practice.selected, practice.submitted, (sel) => { practice.selected = sel; renderPracticeQuestion(); });
    $("pFeedback").innerHTML = practice.submitted ? explanationHtml(q, practice.selected) : "";
    $("pSubmitBtn").classList.toggle("hidden", practice.submitted);
    $("pSubmitBtn").disabled = !C.canSubmit(practice.selected, q.selectN);
    $("pNextBtn").classList.toggle("hidden", !practice.submitted);
    $("pNextBtn").textContent = practice.i === practice.ids.length - 1 ? "Finish" : "Next →";
  }

  function submitPractice() {
    if (!practice || practice.submitted) return;
    const q = QMAP[practice.ids[practice.i]];
    const ok = C.isCorrect(practice.selected, q.correct);
    state = C.recordAnswer(state, q.id, ok, Date.now(), true);
    save();
    practice.results.push({ id: q.id, ok });
    practice.submitted = true;
    renderPracticeQuestion();
  }

  function nextPractice() {
    if (practice.i === practice.ids.length - 1) { finishPractice(); return; }
    practice.i += 1;
    practice.selected = [];
    practice.submitted = false;
    renderPracticeQuestion();
    window.scrollTo(0, 0);
  }

  function finishPractice() {
    const results = practice.results;
    practice = null;
    if (!results.length) { show("practiceSetup"); return; }
    const right = results.filter((r) => r.ok).length;
    const missed = results.filter((r) => !r.ok).map((r) => QMAP[r.id]);
    $("summaryBody").innerHTML =
      `<div class="score-big">${right} / ${results.length}</div><p class="muted">${C.pct(right, results.length)}% correct this session</p>` +
      (missed.length
        ? "<h3>Missed</h3><ul class='plain'>" + missed.map((q) => `<li><button class="linkbtn" data-single="${esc(q.id)}">Q${q.n} · ${esc(q.chapterTitle)}</button></li>`).join("") + "</ul>"
        : "<p>No misses. Nice work.</p>");
    show("practiceSummary");
  }

  // ---------- Shared question rendering ----------
  function renderOptions(container, q, selected, revealed, onChange) {
    container.innerHTML = "";
    q.options.forEach((o) => {
      const picked = selected.includes(o.k);
      const locked = !revealed && C.isOptionLocked(selected, o.k, q.selectN);
      const row = document.createElement("label");
      row.className = "option" + (picked ? " selected" : "") + (locked ? " locked" : "");
      if (revealed && q.correct.includes(o.k)) row.classList.add("correct");
      else if (revealed && picked) row.classList.add("incorrect");
      const input = document.createElement("input");
      input.type = q.selectN > 1 ? "checkbox" : "radio";
      input.name = "opt-" + q.id;
      input.checked = picked;
      input.disabled = revealed || locked;
      input.addEventListener("change", () => onChange(C.toggleSelection(selected, o.k, q.selectN)));
      const text = document.createElement("span");
      text.innerHTML = `<span class="opt-key">${esc(o.k)}.</span> ${esc(o.t)}`;
      row.append(input, text);
      container.append(row);
    });
  }

  function explanationHtml(q, selected) {
    const ok = C.isCorrect(selected, q.correct);
    const s = state.questionStats[q.id];
    const rows = q.options.map((o) => {
      const right = q.correct.includes(o.k);
      const tags = (right ? '<span class="tag right">Correct</span>' : '<span class="tag wrong">Incorrect</span>') +
        (selected.includes(o.k) ? ' <span class="tag pick">Your pick</span>' : "");
      return `<li class="why"><div><b>${esc(o.k)}.</b> ${tags}</div><div>${esc(o.why)}</div></li>`;
    }).join("");
    const statsText = s ? ` · Answered ${s.attempts}× · correct ${s.correct}× (${C.pct(s.correct, s.attempts)}%)` : "";
    return `<div class="verdict ${ok ? "right" : "wrong"}">${ok ? "Correct" : "Incorrect"}. Answer: ${esc(q.correct.join(", "))}</div>
      <div class="explain">
        <h4>Topic</h4><p>${esc(q.topic)}</p>
        <h4>Answer by answer</h4><ul class="plain">${rows}</ul>
        <h4>Why the correct answer is right</h4><p>${esc(q.correctWhy)}</p>
        <p class="small"><a href="${esc(C.videoUrl(q))}" target="_blank" rel="noopener">Watch the explanation on YouTube ↗</a>${statsText}</p>
      </div>`;
  }

  // ---------- Exam ----------
  function renderExamStart() {
    $("examInfo").textContent = `${BANK.exam.questions} questions · ${EXAM_MINUTES} minutes` + (EXAM_MINUTES !== BANK.exam.minutes ? " (test override)" : "");
    $("examQuotaTable").innerHTML = quotaTableHtml();
  }

  function beginExam() {
    const now = Date.now();
    exam = {
      ids: C.sampleExam(BANK.questions, BANK.domains, BANK.exam.questions, Math.random),
      i: 0, answers: {}, flagged: {}, startedAt: now, deadline: now + EXAM_MINUTES * 60000, timerId: null,
    };
    buildNavGrid();
    show("exam");
    renderExamQuestion();
    $("timerBox").classList.remove("hidden");
    exam.timerId = setInterval(tick, 500);
    tick();
  }

  function tick() {
    if (!exam) return;
    const left = C.remainingMs(exam.deadline, Date.now());
    $("timerBox").textContent = C.formatClock(left);
    $("timerBox").classList.toggle("low", left <= 5 * 60000);
    if (left === 0) submitExam();
  }

  function buildNavGrid() {
    const grid = $("navGrid");
    grid.innerHTML = "";
    exam.ids.forEach((id, i) => {
      const b = document.createElement("button");
      b.className = "nav-btn";
      b.textContent = String(i + 1);
      b.addEventListener("click", () => { exam.i = i; renderExamQuestion(); });
      grid.append(b);
    });
  }

  function renderExamQuestion() {
    const q = QMAP[exam.ids[exam.i]];
    $("eMeta").textContent = questionMeta(q);
    $("eCount").textContent = `Question ${exam.i + 1} of ${exam.ids.length}`;
    $("eStem").textContent = q.stem;
    setHint($("eHint"), q.selectN);
    renderOptions($("eOptions"), q, exam.answers[q.id] || [], false, (sel) => { exam.answers[q.id] = sel; renderExamQuestion(); });
    $("flagBtn").textContent = exam.flagged[q.id] ? "Unflag" : "Flag for review";
    $("ePrevBtn").disabled = exam.i === 0;
    $("eNextBtn").disabled = exam.i === exam.ids.length - 1;
    Array.from($("navGrid").children).forEach((b, i) => {
      const id = exam.ids[i];
      b.classList.toggle("answered", (exam.answers[id] || []).length > 0);
      b.classList.toggle("flagged", !!exam.flagged[id]);
      b.classList.toggle("current", i === exam.i);
    });
  }

  function confirmSubmitExam() {
    const unanswered = exam.ids.filter((id) => !(exam.answers[id] || []).length).length;
    if (confirm(unanswered ? `Submit with ${unanswered} unanswered question(s)?` : "Submit the exam now?")) submitExam();
  }

  function submitExam() {
    clearInterval(exam.timerId);
    const questions = exam.ids.map((id) => QMAP[id]);
    const now = Date.now();
    const grade = C.gradeExam(questions, exam.answers);
    state = C.recordExam(state, questions, grade, exam.startedAt, now);
    save();
    lastExam = { questions, answers: exam.answers, flagged: exam.flagged, grade };
    exam = null;
    $("timerBox").classList.add("hidden");
    renderResults("all");
    show("results");
  }

  function abandonExamIfConfirmed() {
    if (!exam) return true;
    if (!confirm("Abandon this exam? It won't be recorded.")) return false;
    clearInterval(exam.timerId);
    exam = null;
    $("timerBox").classList.add("hidden");
    return true;
  }

  function renderResults(filter) {
    const { grade, questions, answers, flagged } = lastExam;
    $("scoreBig").textContent = `${grade.pct}%`;
    $("scoreSub").textContent = `${grade.correct} of ${grade.total} correct`;
    const pass = grade.pct >= BANK.exam.passPct;
    $("passPill").className = "pass-pill " + (pass ? "pass" : "fail");
    $("passPill").textContent = pass ? "At or above the passing line" : "Below the passing line";
    $("domainResults").innerHTML = "<tr><th>Domain</th><th>Score</th><th>%</th></tr>" + BANK.domains.map((d) => {
      const s = grade.byDomain[d.id] || { correct: 0, total: 0 };
      const p = C.pct(s.correct, s.total);
      return `<tr><td>${d.id}. ${esc(d.name)}</td><td>${s.correct}/${s.total}</td><td>${bar(p)}${p}%</td></tr>`;
    }).join("");
    markChips("review", filter);
    const shown = questions.map((q, i) => ({ q, i })).filter(({ q }) =>
      filter === "all" || (filter === "incorrect" && !grade.results[q.id]) || (filter === "flagged" && flagged[q.id]));
    $("reviewList").innerHTML = shown.length
      ? shown.map(({ q, i }) => reviewItemHtml(q, i, answers[q.id] || [])).join("")
      : "<p class='muted'>Nothing to show.</p>";
  }

  function reviewItemHtml(q, i, selected) {
    const options = q.options.map((o) => `<div class="opt-line"><b>${esc(o.k)}.</b> ${esc(o.t)}</div>`).join("");
    return `<div class="review-item">
      <div class="q-header"><span class="q-meta">#${i + 1} · Q${q.n} · ${esc(q.chapterTitle)}</span><span class="q-meta">${esc(questionMeta(q))}</span></div>
      <div class="q-text">${esc(q.stem)}</div>${options}${explanationHtml(q, selected)}</div>`;
  }

  // ---------- Statistics ----------
  function accRow(label, b, title) {
    const bucket = b || { attempts: 0, correct: 0, seen: 0, pct: 0 };
    const acc = bucket.attempts ? `${bar(bucket.pct)}${bucket.pct}%` : "–";
    return `<tr><td${title ? ` title="${esc(title)}"` : ""}>${esc(label)}</td><td>${bucket.seen}</td><td>${bucket.correct}/${bucket.attempts}</td><td>${acc}</td></tr>`;
  }

  function renderStats() {
    const sum = C.summarize(state, BANK.questions);
    const tiles = [
      [sum.overall.seen, `questions attempted of ${IDS.length}`],
      [sum.overall.attempts ? `${sum.overall.pct}%` : "–", "lifetime accuracy"],
      [sum.overall.attempts, "answers recorded"],
      [state.examHistory.length, "exams taken"],
    ];
    $("statsOverall").innerHTML = tiles.map(([n, label]) => `<div class="stat"><div class="stat-num">${n}</div><div class="small muted">${label}</div></div>`).join("");
    const head = "<tr><th></th><th>Seen</th><th>Correct / attempts</th><th>Accuracy</th></tr>";
    $("statsDomains").innerHTML = head + BANK.domains.map((d) => accRow(`${d.id}. ${d.name}`, sum.byDomain[d.id])).join("");
    $("statsVideos").innerHTML = head + BANK.videos.map((v) => accRow(videoLabel(v), sum.byVideo[v.index], v.title)).join("");
    const weak = C.weakest(state, 20);
    $("statsWeakest").innerHTML = weak.length
      ? "<ul class='plain'>" + weak.map((id) => {
          const q = QMAP[id], s = state.questionStats[id];
          return `<li class="why"><button class="linkbtn" data-single="${esc(id)}">Q${q.n} · ${esc(q.chapterTitle)}</button> <span class="small muted">${s.correct}/${s.attempts} correct</span></li>`;
        }).join("") + "</ul>"
      : "<p class='muted'>No missed questions yet.</p>";
    $("statsExams").innerHTML = state.examHistory.length
      ? "<tr><th>Date</th><th>Score</th>" + BANK.domains.map((d) => `<th>D${d.id}</th>`).join("") + "<th>Time</th></tr>" +
        state.examHistory.slice().reverse().map((e) =>
          `<tr><td>${new Date(e.at).toLocaleString()}</td><td>${e.scorePct}%</td>` +
          BANK.domains.map((d) => { const s = e.byDomain[d.id]; return `<td>${s ? C.pct(s.correct, s.total) + "%" : "–"}</td>`; }).join("") +
          `<td>${Math.round(e.durationSec / 60)} min</td></tr>`).join("")
      : "<tr><td class='muted'>No exams yet.</td></tr>";
  }

  // ---------- Wiring ----------
  document.addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]");
    if (go) { if (abandonExamIfConfirmed()) { practice = null; show(go.dataset.go); } return; }
    const single = e.target.closest("[data-single]");
    if (single) { startPractice([single.dataset.single]); return; }
    const filter = e.target.closest("[data-filter]");
    if (filter) { setup.filter = filter.dataset.filter; renderPracticeSetup(); return; }
    const size = e.target.closest("[data-size]");
    if (size) { setup.size = size.dataset.size === "all" ? "all" : Number(size.dataset.size); renderPracticeSetup(); return; }
    const review = e.target.closest("[data-review]");
    if (review && lastExam) renderResults(review.dataset.review);
  });
  $("startPracticeBtn").addEventListener("click", () => startPractice(C.sessionIds(state, setup.filter, setup.size)));
  $("newPassBtn").addEventListener("click", () => { state = C.newPass(state, Math.random); save(); renderPracticeSetup(); });
  $("pSubmitBtn").addEventListener("click", submitPractice);
  $("pNextBtn").addEventListener("click", nextPractice);
  $("pQuitBtn").addEventListener("click", finishPractice);
  $("beginBtn").addEventListener("click", beginExam);
  $("flagBtn").addEventListener("click", () => { const id = exam.ids[exam.i]; exam.flagged[id] = !exam.flagged[id]; renderExamQuestion(); });
  $("ePrevBtn").addEventListener("click", () => { exam.i -= 1; renderExamQuestion(); });
  $("eNextBtn").addEventListener("click", () => { exam.i += 1; renderExamQuestion(); });
  $("submitExamBtn").addEventListener("click", confirmSubmitExam);
  $("exportBtn").addEventListener("click", exportProgress);
  $("importInput").addEventListener("change", (e) => { if (e.target.files[0]) importProgress(e.target.files[0]); e.target.value = ""; });
  $("resetBtn").addEventListener("click", resetProgress);
  window.addEventListener("beforeunload", (e) => { if (exam) { e.preventDefault(); e.returnValue = ""; } });

  show("home");
})();
</script>
</body>
</html>
```

- [ ] **Step 3: Run the full test suites**

Run: `.venv/Scripts/python -m pytest -q && node --test tests-js/`
Expected: all pass, including `test_built_app_embeds_loadable_core_and_bank`.

- [ ] **Step 4: Add the demo builder**

`tests/make_demo.py`:
```python
"""Build the study app from a synthetic 80-question bank for manual checks.

Usage: .venv/Scripts/python tests/make_demo.py <empty-dir>
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "src")]

from factory import make_root, rewrite, video_id  # noqa: E402
from peb.build import build  # noqa: E402


def choose_two(bank):
    q = bank["questions"][1]
    q["options"].append({"k": "E", "t": "Option E", "why": "Why E"})
    q.update(selectN=2, correct=["B", "E"])


def main(target: str) -> None:
    root = make_root(Path(target))
    rewrite(root / "bank" / f"01-{video_id(1)}.json", choose_two)
    shutil.copytree(HERE.parent / "template", root / "template", dirs_exist_ok=True)
    print(build(root))


if __name__ == "__main__":
    main(sys.argv[1])
```

Run it, with `<scratchpad>` set to the session scratchpad directory:
```bash
.venv/Scripts/python tests/make_demo.py "<scratchpad>/demo"
```
Expected: prints `.../demo/dist/dva-c02-practice.html`.

- [ ] **Step 5: Check the app manually in a browser**

Serve the demo with `python -m http.server 8765 --directory "<scratchpad>/demo/dist"`, run in the background. Then open `http://localhost:8765/dva-c02-practice.html` using the claude-in-chrome tools. Check each of the following, and avoid buttons that open `confirm()` dialogs (Reset, Import, Submit exam, Home during an exam):

1. **Home.** It shows "0 / 80 answered this pass" and the domain table (24/20/20/16 in bank, 21/17/15/12 per exam), in the orange and squid palette.
2. **Practice session.** Choose Practice, then *Next in pass*, size 10, then Start.
   - The header reads "Question 1 of 10 this session".
   - Submit stays disabled until an option is picked.
   - After Submit, the title gains the chapter title, and the verdict, Topic, answer-by-answer, why-correct and YouTube link all appear.
3. **Choose-two question.** Find Q2 (video 1, choose two) through *Never answered* sessions if needed. After two picks, the other options are disabled.
4. **Filters and summary.** Finish a session and check that the summary lists misses. Back on Home, the progress bar has advanced. *Previously missed* then shows the missed count.
5. **Timed exam.** Open `?examMinutes=1` and Begin exam.
   - The timer counts down, the navigator marks answered and flagged questions, and the exam auto-submits at 0:00.
   - Results show a per-domain table, and the review chips filter correctly.
6. **Statistics.** It shows tiles, the domain and video tables, weakest questions (clicking one opens the single-question view) and exam history.
7. **Phone width.** Resize to 390px wide: no horizontal page scroll, and the exam navigator stacks above the question.

Fix any defect, re-run Step 3, and repeat the affected checks.

- [ ] **Step 6: Commit**

```bash
git add template/app.html tests/test_dist_smoke.py tests/make_demo.py
git commit -m "Add AWS-styled study app UI with practice, exam and statistics"
```

---

### Task 11: Extraction procedure and README

**Files:**
- Create: `docs/extraction.md`, `README.md`

No code, so no test cycle. The deliverable is the document that the extraction subagents in Tasks 13–14 follow verbatim.

- [ ] **Step 1: Write `docs/extraction.md`**

````markdown
# Extracting questions from one video

You turn one ingested video into `bank/<nn>-<videoId>.json` (20 questions) plus
`bank/<nn>-<videoId>.notes.md`. You are transcribing **real exam questions** that
the narrator reads aloud. Faithfulness beats polish: never invent content.

## Inputs

- `sources/<nn>-<videoId>/metadata.json`. Holds `index`, `videoId`, `title`, and
  `questionChapters` (`q`, `startSec`, `endSec`, `title`).
- `sources/<nn>-<videoId>/transcript.txt`. Lines look like `[h:mm:ss] text`.
  Before each question chapter there is a header line:
  `=== Q07 [0:10:39–0:13:51] Lambda concurrency throttling ===`.

The narrator often says "Question seven, …" a second or two **before** the
chapter header. So the stem's first words may sit just above the header, at the
end of the previous section.

## How each question is narrated

1. "Question N." followed by the stem, then "A. … B. … C. … D. …". Choose-two
   questions say so in the stem (e.g. "Choose two" / "Select TWO") and usually
   have options A–E.
2. The topic discussion ("Okay, this question is about…").
3. Each incorrect option: "Option C is incorrect…".
4. The correct answer(s) and why ("This leads us to option D, which is the
   correct answer…").

## Output: bank file

```json
{
  "video": 1,
  "videoId": "YJg7z6r6jsQ",
  "title": "<metadata.json title>",
  "expectedCount": 20,
  "countNote": null,
  "questions": [
    {
      "id": "YJg7z6r6jsQ-q01",
      "video": 1,
      "videoId": "YJg7z6r6jsQ",
      "n": 1,
      "chapterTitle": "Storing a database password",
      "timestampSec": 70,
      "anchor": "A developer is building an order processing service on AWS Lambda",
      "domain": 2,
      "task": "2.3",
      "selectN": 1,
      "stem": "A developer is building an order processing service on AWS Lambda that connects to an Amazon RDS database. The database password must be encrypted and rotated automatically. …",
      "options": [
        { "k": "A", "t": "Hard-code the password in the function code …", "why": "Incorrect. The password would be exposed in source control and can't rotate; …" },
        { "k": "B", "t": "…", "why": "…" },
        { "k": "C", "t": "…", "why": "…" },
        { "k": "D", "t": "Store the password in AWS Secrets Manager with automatic rotation …", "why": "Correct. Secrets Manager encrypts the secret and rotates it natively …" }
      ],
      "correct": ["D"],
      "topic": "This question is about keeping database credentials out of code …",
      "correctWhy": "Secrets Manager stores the password encrypted with KMS and rotates it on a schedule. …"
    }
  ]
}
```

Field rules:

| Field | Rule |
|---|---|
| `id` | `<videoId>-q<NN>`, where `NN` is the chapter number (01–20) |
| `n` | `(video − 1) × 20 + NN` |
| `chapterTitle`, `timestampSec` | copied exactly from `questionChapters[NN-1]` (`title`, `startSec`) |
| `anchor` | 6–12 **consecutive words copied verbatim from transcript.txt** where the stem begins (the words after "Question N"). Copy exactly as the captions show them, even if they're misspelled. Punctuation and case don't matter. |
| `stem` | The question text, near-verbatim. Fix obvious caption errors (e.g. "AWSKMS" → "AWS KMS", "B 64" → "Base64", "anti-attern" → "anti-pattern", "DVAC02" → "DVA-C02"). Use proper AWS service capitalization. Drop "Question N." |
| `options` | One entry per option read aloud, keys `A`, `B`, … in order. `t` is the option text, near-verbatim. |
| `options[].why` | For an incorrect option: the narrator's reasoning for why it's wrong, condensed to 1–3 sentences in their words. For a correct option: one short sentence on why it's right. If the narrator never addresses a distractor, use exactly `Not covered in the video.` |
| `correct` | The key(s) the narrator names as correct. `selectN` equals the number of correct keys (1 or 2). |
| `topic` | The narrator's topic discussion, condensed to 2–5 sentences. Remove filler; keep every technical point. |
| `correctWhy` | The narrator's explanation of the correct answer, 2–5 sentences. |
| `domain`, `task` | Your best-effort DVA-C02 tag (guide below). Explain it in the notes. |

## Hard rules

- **One chapter = one question.** Never merge, split, skip or pad questions to
  reach 20. If a chapter doesn't contain exactly one question, stop, leave the
  file incomplete, and report it. Don't "fix" it.
- **Never add facts** the narrator didn't say. Explanations condense; they never
  embellish.
- **Letters.** Cross-check each option letter against the narrator's later
  references, e.g. "Option C is incorrect … Base64" must match option C's text.
  If the letters conflict (a caption mishearing, such as "B" vs "D"), trust the
  content match and record it in the notes as uncertain.
- The correct answer is what the **narrator** says, even if you disagree. Put any
  disagreement in the notes.

## Output: notes file

`bank/<nn>-<videoId>.notes.md`:

```markdown
# Video <nn> — <title>

## Uncertain items
- <id>: <what is uncertain and what you chose> (or "None")

## Domain tagging
- q01 — 2.3: Secrets Manager rotation and retrieval of sensitive data
- q02 — …
```

## DVA-C02 domain tagging guide

| Task | Tag when the question is mainly about… |
|---|---|
| 1.1 | Application code using AWS services and SDKs: API Gateway integrations, SQS/SNS/EventBridge/Kinesis messaging patterns, Step Functions, retries/backoff, idempotency, fan-out |
| 1.2 | Lambda itself: memory/timeout, concurrency, layers, env vars, destinations, event source mappings, VPC access, handler design |
| 1.3 | Data stores: DynamoDB keys/indexes/queries/capacity/streams/TTL/DAX, ElastiCache and caching strategies, S3 as a data store, RDS access from code |
| 2.1 | Authentication/authorization: IAM roles and policies, Cognito user/identity pools, STS/assume role, API Gateway authorizers, resource policies |
| 2.2 | Encryption: KMS keys and envelope encryption, encryption at rest and in transit, ACM, S3/DynamoDB encryption settings |
| 2.3 | Sensitive data in code: Secrets Manager, Parameter Store, credential rotation, keeping secrets out of code/logs |
| 3.1 | Preparing artifacts: SAM/CloudFormation templates, packaging, container images/ECR, Lambda deployment packages, AppConfig |
| 3.2 | Testing in dev: SAM local, mocks, API Gateway stages/stage variables for testing |
| 3.3 | Automated deployment testing: Lambda aliases/versions with traffic shifting, CodeDeploy canary/linear, pre/post traffic hooks |
| 3.4 | CI/CD and deployment: CodePipeline, CodeBuild, CodeDeploy, Elastic Beanstalk deployment policies, CDK/SAM deploy, rollbacks |
| 4.1 | Root cause analysis: reading logs/metrics/traces, CloudWatch Logs Insights, X-Ray service maps, interpreting errors (throttling, 4xx/5xx) |
| 4.2 | Instrumentation: structured logging, custom metrics/EMF, X-Ray SDK annotations/subsegments, alarms |
| 4.3 | Optimization: performance tuning, caching for speed, Lambda memory/cold starts, DynamoDB/S3 performance, cost-efficient choices |

When two tasks fit, choose the one the question's *decision* hinges on. For
example, "least effort to rotate secrets" is 2.3, not 1.1.

## Procedure

1. Read `metadata.json` and all of `transcript.txt`.
2. For NN = 01…20, write each question from its chapter section (plus the lead-in
   lines just above its header).
3. Write the bank file with `expectedCount: 20` and `countNote: null`, as UTF-8
   JSON (2-space indent).
4. Write the notes file.
5. Run `.venv/Scripts/python -m peb validate bank/<nn>-<videoId>.json`, and fix
   genuine mistakes: an anchor copied wrong, a wrong chapter title, a missing
   `why`. **Never** change content just to satisfy the question-count rule.
6. Report back: the validation output, plus every uncertain item from the notes.
````

- [ ] **Step 2: Write `README.md`**

````markdown
# Practice Exam Builder

Turns a YouTube playlist of narrated practice questions into a single offline study app.
Iteration 1 targets the DVA-C02 (AWS Certified Developer – Associate) "500 Real Exam
Questions" playlist.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Node 22+ must be on PATH. yt-dlp uses it as its YouTube JS runtime, and it runs the JS tests.

## Pipeline

```bash
# 1. Ingest captions + chapters into sources/ (re-runnable; skips finished videos)
.venv/Scripts/python -m peb ingest "https://www.youtube.com/playlist?list=PLB574eEmT4ofjfiABMEx5c19Q_lCbaADV"

# 2. Extract questions into bank/: done by Claude Code following docs/extraction.md

# 3. Validate and build
.venv/Scripts/python -m peb validate
.venv/Scripts/python -m peb build        # -> dist/dva-c02-practice.html
```

If YouTube rate-limits caption downloads (HTTP 429), wait and re-run ingest,
optionally with `--delay 15` or `--cookies-from-browser chrome`.

## Using the app

Open `dist/dva-c02-practice.html` in a browser. There are three areas:

- **Practice** (untimed): works through all questions in random order without repeats. You can filter to never-answered or previously missed questions and pick a session size.
- **Timed exam**: 65 questions in 130 minutes, weighted 21/17/15/12 by DVA-C02 domain.
- **Statistics**: accuracy by domain and by video, your weakest questions, and exam history.

Progress lives in browser storage, so keep the file at a fixed path and use
**Export progress** as a backup.

## Tests

```bash
.venv/Scripts/python -m pytest -q
node --test tests-js/
```
````

- [ ] **Step 3: Commit**

```bash
git add docs/extraction.md README.md
git commit -m "Document extraction procedure and usage"
```

---

### Task 12: Ingest the real playlist

**Files:**
- Create (generated): `sources/playlist.json`, `sources/<nn>-<videoId>/{metadata.json, captions.vtt, transcript.txt}` for all 25 videos.

- [ ] **Step 1: Run ingest**

Run (it takes several minutes; use a 600000 ms timeout):
```bash
.venv/Scripts/python -m peb ingest "https://www.youtube.com/playlist?list=PLB574eEmT4ofjfiABMEx5c19Q_lCbaADV" --delay 5
```
Expected: 25 rows, all `ok`, then `25/25 ok`.

If some rows show `error` with HTTP 429: wait 5 minutes, then re-run the same command. Finished videos are skipped, so up to 3 re-runs are fine. If 429s persist, stop and report. The controller will ask the user about `--cookies-from-browser`.

A `chapter-mismatch` or `no-captions` row is a hard stop. Report it; don't work around it.

- [ ] **Step 2: Spot-check one transcript**

Run: `grep -c "^=== Q" sources/01-*/transcript.txt`
Expected: `20`.

Run: `sed -n '1,5p;/=== Q01/,+3p' sources/01-*/transcript.txt`
Expected: `[0:00:00] …` caption lines, then the `=== Q01 [0:01:05–0:05:39] Managing application secrets ===` header.

- [ ] **Step 3: Commit**

```bash
git add sources
git commit -m "Ingest DVA-C02 playlist captions and chapters"
```

---

### Task 13: Pilot extraction of video 01 — HUMAN GATE

**Files:**
- Create: `bank/01-YJg7z6r6jsQ.json`, `bank/01-YJg7z6r6jsQ.notes.md`

- [ ] **Step 1: Extract video 01**

Follow `docs/extraction.md` exactly for `sources/01-YJg7z6r6jsQ/`.

- [ ] **Step 2: Validate the file**

Run: `.venv/Scripts/python -m peb validate bank/01-YJg7z6r6jsQ.json`
Expected: `0 error(s), 0 warning(s)`.

- [ ] **Step 3: Commit**

```bash
git add bank/01-YJg7z6r6jsQ.json bank/01-YJg7z6r6jsQ.notes.md
git commit -m "Extract pilot video 01 questions"
```

- [ ] **Step 4: STOP for user review**

The controller shows the user:
- the path to the bank file and the notes
- a readable rendering of 3 questions (stem, options, answer, explanations)
- the answer-letter list for all 20 questions
- every uncertain item

The user checks at least 3 questions end to end against the video, plus the answer letters for all 20.

**Don't start Task 14 until the user approves.** If the user requests changes to the extraction rules, update `docs/extraction.md`, redo video 01, and ask again.

---

### Task 14: Extract the remaining 24 videos

**Files:**
- Create: `bank/<nn>-<videoId>.json` and `.notes.md` for videos 02–25.

- [ ] **Step 1: Dispatch one extraction subagent per video, in parallel**

Each subagent gets:
- its source folder
- `docs/extraction.md`
- the approved pilot `bank/01-*.json` as a style reference

It writes only its own two files. It doesn't commit. Its report holds its validate output and its uncertain items.

- [ ] **Step 2: Handle reports**

For each video that fails validation, send its violations back to that video's subagent to fix. A chapter that doesn't hold exactly one question gets escalated to the user, not fixed.

- [ ] **Step 3: Validate the whole bank**

Run: `.venv/Scripts/python -m peb validate`
Expected: `0 error(s), 0 warning(s)`. The domain quota rule is included.

If a domain falls short of its quota, report the per-domain counts to the user. Don't retag questions to make the numbers fit.

- [ ] **Step 4: Commit**

```bash
git add bank
git commit -m "Extract questions for videos 02-25"
```

- [ ] **Step 5: Show the consolidated uncertain items to the user**

Gather every "Uncertain items" entry from the 25 notes files into one list, and give it to the user.

---

### Task 15: Build the real app and verify

- [ ] **Step 1: Build**

Run: `.venv/Scripts/python -m peb build`
Expected: `wrote …/dist/dva-c02-practice.html`.

- [ ] **Step 2: Run the full suites**

Run: `.venv/Scripts/python -m pytest -q && node --test tests-js/`
Expected: all pass.

- [ ] **Step 3: Browser check on real data**

Repeat the Task 10 Step 5 checks against `dist/dva-c02-practice.html` served over http. Also check that:
- Home reads "0 / 500".
- A "Watch the explanation" link opens the right video at the right chapter.
- A choose-two question from the real bank behaves correctly.

- [ ] **Step 4: Report**

Tell the user:
- the path to the built file
- the per-domain question counts
- the test results
- anything skipped
````
