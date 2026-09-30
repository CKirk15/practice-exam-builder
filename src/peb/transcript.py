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


def _joined(lines: list[Line]) -> tuple[str, list[tuple[int, int]]]:
    joined, offsets = "", []
    for line in lines:
        piece = normalize(line.text)
        if not piece:
            continue
        if joined:
            joined += " "
        offsets.append((len(joined), line.start))
        joined += piece
    return joined, offsets


def _second_at(offsets: list[tuple[int, int]], pos: int) -> int:
    start = offsets[0][1]
    for offset, second in offsets:
        if offset > pos:
            break
        start = second
    return start


def find_anchor_start(lines: list[Line], anchor: str) -> int | None:
    """Start second of the line where the first whole-word match of `anchor` begins."""
    target = normalize(anchor)
    if not target:
        return None
    joined, offsets = _joined(lines)
    pos = f" {joined} ".find(f" {target} ")
    return None if pos < 0 else _second_at(offsets, pos)


def spoken_question_chapters(lines: list[Line], first_n: int, count: int, duration_sec: int) -> list[dict]:
    """Question sections from the narrator saying "Question N", for videos without chapters."""
    joined, offsets = _joined(lines)
    padded = f" {joined} "
    starts, pos = [], 0
    for n in range(first_n, first_n + count):
        found = padded.find(f" question {n} ", pos)
        if found < 0:
            break
        starts.append(_second_at(offsets, found))
        pos = found + 1
    ends = starts[1:] + [duration_sec]
    return [{"q": i, "startSec": s, "endSec": e, "title": f"Question {first_n + i - 1}"}
            for i, (s, e) in enumerate(zip(starts, ends), start=1)]


def anchor_window(chapter: dict) -> tuple[int, int]:
    """[lo, hi) seconds where a chapter's stem may begin (the narrator starts early)."""
    return max(0, chapter["startSec"] - ANCHOR_LEAD_SEC), chapter["endSec"] - ANCHOR_LEAD_SEC
