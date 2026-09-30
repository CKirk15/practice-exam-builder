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
