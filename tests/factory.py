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
