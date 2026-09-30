from peb.dva_c02 import DOMAINS, EXAM, exam_quotas


def test_exam_quotas_match_guide_for_65():
    assert exam_quotas(65) == {1: 21, 2: 17, 3: 15, 4: 12}


def test_quotas_default_to_exam_length():
    assert sum(exam_quotas().values()) == EXAM["questions"] == 65


def test_quotas_use_largest_remainder_for_small_totals():
    assert exam_quotas(10) == {1: 3, 2: 3, 3: 2, 4: 2}


def test_weights_sum_to_100_and_tasks_are_numbered_by_domain():
    assert sum(d["weight"] for d in DOMAINS) == 100
    assert [len(d["tasks"]) for d in DOMAINS] == [3, 3, 4, 3]
    for d in DOMAINS:
        assert all(t.startswith(f"{d['id']}.") for t in d["tasks"])
