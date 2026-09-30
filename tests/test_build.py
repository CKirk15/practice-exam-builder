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
