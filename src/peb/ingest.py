"""Ingest a YouTube playlist into sources/ (manifest, metadata, captions, transcript)."""
import json
import subprocess
import sys
import time
from pathlib import Path

from peb.dva_c02 import QUESTIONS_PER_VIDEO
from peb.transcript import clean_vtt, question_chapters, render_transcript, spoken_question_chapters

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
            meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            qchapters_count = len(meta.get("questionChapters", []))
            if qchapters_count != QUESTIONS_PER_VIDEO:
                results.append(_result(item, "chapter-mismatch", _chapter_mismatch_detail(qchapters_count)))
            else:
                results.append(_result(item, "ok", "skipped (already ingested)"))
        else:
            if fetched_any:
                sleep(delay)
            fetched_any = True
            results.append(_ingest_video(client, item, folder))
    return results


def _chapter_mismatch_detail(qchapters_count: int) -> str:
    return f"{qchapters_count} question chapters (expected {QUESTIONS_PER_VIDEO})"


def _ingest_video(client, item: dict, folder: Path) -> dict:
    try:
        info = client.video_info(item["videoId"])
        duration = info["durationSec"] or item["durationSec"]
        qchapters, source = question_chapters(info["chapters"]), "chapters"
        folder.mkdir(parents=True, exist_ok=True)
        track = pick_caption_track(info)
        lines = None
        if track is not None:
            vtt = client.download_captions(item["videoId"], track[0], track[1], folder)
            (folder / "captions.vtt").write_text(vtt, encoding="utf-8")
            lines = clean_vtt(vtt)
            if not qchapters:
                first_n = (item["index"] - 1) * QUESTIONS_PER_VIDEO + 1
                qchapters = spoken_question_chapters(lines, first_n, QUESTIONS_PER_VIDEO, duration)
                source = "spoken"
        metadata = {**item, "durationSec": duration, "chapters": info["chapters"],
                    "questionSource": source, "questionChapters": qchapters}
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        if lines is None:
            return _result(item, "no-captions", "no English captions available")
        (folder / "transcript.txt").write_text(render_transcript(lines, qchapters), encoding="utf-8")
    except Exception as exc:  # boundary: report per video and keep going
        return _result(item, "error", str(exc) or type(exc).__name__)
    if len(qchapters) != QUESTIONS_PER_VIDEO:
        return _result(item, "chapter-mismatch", _chapter_mismatch_detail(len(qchapters)))
    return _result(item, "ok", f"{track[0]}{' (auto)' if track[1] else ''}")


def _result(item: dict, status: str, detail: str) -> dict:
    return {"index": item["index"], "videoId": item["videoId"], "status": status, "detail": detail}
