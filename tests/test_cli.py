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
