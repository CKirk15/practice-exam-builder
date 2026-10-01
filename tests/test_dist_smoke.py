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
new vm.Script(blocks[2]);
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
