import pytest

from app.services.scanner import _category_of, _letter_grade, score_report


def finding(severity, category="secrets", **extra):
    base = {
        "severity": severity,
        "category": category,
        "rule_id": "R",
        "file": "app.py",
        "line": 1,
        "description": "finding",
    }
    base.update(extra)
    return base


def test_empty_findings_score_100_a():
    report = score_report([])
    assert report["score"] == 100.0
    assert report["grade"] == "A"
    assert report["counts"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assert report["sub_scores"] == {"secrets_score": 100, "config_score": 100, "code_score": 100}


def test_single_critical_score_75_b():
    report = score_report([finding("critical")])
    assert report["score"] == 75.0
    assert report["grade"] == "B"
    assert report["counts"] == {"critical": 1, "high": 0, "medium": 0, "low": 0}


def test_one_of_each_severity_score_50_c():
    findings = [
        finding("critical"),
        finding("high"),
        finding("medium"),
        finding("low"),
    ]
    report = score_report(findings)
    assert report["score"] == 50.0
    assert report["grade"] == "C"
    assert report["counts"] == {"critical": 1, "high": 1, "medium": 1, "low": 1}


def test_four_critical_findings_score_0_f():
    findings = [finding("critical") for _ in range(4)]
    report = score_report(findings)
    assert report["score"] == 0.0
    assert report["grade"] == "F"


def test_three_critical_findings_score_25_d():
    findings = [finding("critical") for _ in range(3)]
    report = score_report(findings)
    assert report["score"] == 25.0
    assert report["grade"] == "D"


def test_low_plus_medium_score_90_a():
    report = score_report([finding("low"), finding("medium")])
    assert report["score"] == 90.0
    assert report["grade"] == "A"


@pytest.mark.parametrize(
    ("score", "grade"),
    [
        (90, "A"),
        (89, "B"),
        (75, "B"),
        (74, "C"),
        (50, "C"),
        (49, "D"),
        (25, "D"),
        (24, "F"),
    ],
)
def test_grade_boundaries(score, grade):
    assert _letter_grade(score) == grade


def test_sub_scores_per_category():
    report = score_report(
        [
            finding("critical", category="secrets"),
            finding("high", category="code"),
            finding("medium", category="config"),
        ]
    )
    assert report["score"] == 53.0
    assert report["sub_scores"] == {
        "secrets_score": 75,
        "config_score": 93,
        "code_score": 85,
    }


def test_sub_scores_floor_at_zero():
    report = score_report([finding("critical", category="secrets") for _ in range(5)])
    assert report["sub_scores"]["secrets_score"] == 0
    assert report["sub_scores"]["config_score"] == 100
    assert report["sub_scores"]["code_score"] == 100


def test_unknown_severity_is_ignored():
    report = score_report([finding("blah")])
    assert report["score"] == 100.0
    assert report["grade"] == "A"


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("secrets", "secrets"),
        ("config", "config"),
        ("code", "code"),
        ("api_key", "secrets"),
        ("api token", "secrets"),
        ("credential_store", "secrets"),
        ("secret-key", "secrets"),
        ("cors", "config"),
        ("debug", "config"),
        ("ssl_config", "config"),
        ("header_settings", "config"),
        ("authentication", "code"),
        ("injection", "code"),
        ("", "code"),
        ("unknown", "code"),
    ],
)
def test_category_of_mapping(category, expected):
    assert _category_of({"category": category}) == expected


def test_category_of_falls_back_to_code_for_missing_category():
    assert _category_of({}) == "code"
