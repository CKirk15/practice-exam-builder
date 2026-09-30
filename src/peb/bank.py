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
