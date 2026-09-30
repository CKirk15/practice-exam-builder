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
