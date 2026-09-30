import pytest

from peb.timecode import format_hms, parse_hms


@pytest.mark.parametrize("sec,text", [(0, "0:00:00"), (59, "0:00:59"), (639, "0:10:39"), (4449, "1:14:09")])
def test_format_hms(sec, text):
    assert format_hms(sec) == text


def test_format_truncates_fractions():
    assert format_hms(3.99) == "0:00:03"


@pytest.mark.parametrize("text,sec", [("10:39", 639), ("1:14:09", 4449), ("00:00:03.270", 3.27)])
def test_parse_hms(text, sec):
    assert parse_hms(text) == pytest.approx(sec)


@pytest.mark.parametrize("bad", ["", "12", "1:2:3:4", "a:bc"])
def test_parse_rejects_bad_timecodes(bad):
    with pytest.raises(ValueError):
        parse_hms(bad)
