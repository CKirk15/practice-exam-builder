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
