from pathlib import Path

from app.services.deps import (
    ADVISORIES,
    _cmp,
    _matches,
    _parse_go_mod,
    _parse_package_json,
    _parse_pyproject,
    _parse_requirements,
    analyze_dependencies,
)


def test_cmp():
    assert _cmp((1, 2, 3), (1, 2, 3)) == 0
    assert _cmp((1, 2, 3), (1, 2, 4)) < 0
    assert _cmp((1, 2, 3), (1, 3, 0)) < 0
    assert _cmp((2, 0, 0), (1, 99, 99)) > 0
    assert _cmp((1, 2), (1, 2, 0)) == 0
    assert _cmp((1, 2, 3), (1, 2)) > 0


def test_matches_basic_ops():
    adv = {"version": "1.0.0", "op": "<"}
    assert _matches(adv, (0, 9, 9))
    assert not _matches(adv, (1, 0, 0))
    adv_le = {"version": "1.0.0", "op": "<="}
    assert _matches(adv_le, (1, 0, 0))
    adv_eq = {"version": "1.0.0", "op": "=="}
    assert _matches(adv_eq, (1, 0, 0))
    assert not _matches(adv_eq, (1, 0, 1))


def test_matches_min_lower_bound():
    adv = {"version": "15.2.3", "op": "<", "min": "15.0.0"}
    assert _matches(adv, (15, 0, 0))
    assert _matches(adv, (15, 1, 4))
    assert _matches(adv, (15, 2, 2))
    assert not _matches(adv, (15, 2, 3))
    assert not _matches(adv, (15, 3, 0))
    assert not _matches(adv, (14, 9, 9))
    assert not _matches(adv, None)


def test_matches_none_version():
    assert not _matches({"version": "1.0.0", "op": "<"}, None)


def test_parse_requirements(tmp_path):
    path = tmp_path / "requirements.txt"
    path.write_text("fastapi==0.109.0\n\nuvicorn>=0.27,<0.30\nFlask~=2.3.0\n# comment\nbad-line-no-version\n")
    deps = _parse_requirements(path)
    by_name = {d["package"]: d for d in deps}
    assert by_name["fastapi"]["version"] == (0, 109, 0)
    assert by_name["uvicorn"]["version"] == (0, 27, 0)
    assert by_name["flask"]["version"] == (2, 3, 0)
    assert len(deps) == 3


def test_parse_package_json(tmp_path):
    path = tmp_path / "package.json"
    path.write_text('{"dependencies": {"next": "15.1.0", "express": "^4.18.0"}, '
                    '"devDependencies": {"eslint": "~8.0.0"}, "name": "demo"}')
    deps = _parse_package_json(path)
    by_name = {d["package"]: d for d in deps}
    assert by_name["next"]["version"] == (15, 1, 0)
    assert by_name["express"]["version"] == (4, 18, 0)
    assert by_name["eslint"]["version"] == (8, 0, 0)
    assert "demo" not in by_name


def test_parse_pyproject(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "demo-app"\nversion = "1.0.0"\n'
                    'dependencies = ["requests>=2.31,<3"]\n\n'
                    '[tool.poetry.dependencies]\nfastapi = "^0.100.0"\n')
    deps = _parse_pyproject(path)
    by_name = {d["package"]: d for d in deps}
    assert by_name["requests"]["version"] == (2, 31, 0)
    assert by_name["fastapi"]["version"] == (0, 100, 0)
    assert "demo-app" not in by_name
    assert "1.0.0" not in [d["package"] for d in deps]


def test_parse_go_mod(tmp_path):
    path = tmp_path / "go.mod"
    path.write_text("module example.com/app\n\ngo 1.21\n\nrequire (\n\tgolang.org/x/net v0.30.0\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n")
    deps = _parse_go_mod(path)
    by_name = {d["package"]: d for d in deps}
    assert by_name["golang.org/x/net"]["version"] == (0, 30, 0)
    assert by_name["github.com/gin-gonic/gin"]["version"] == (1, 9, 1)


def test_analyze_dependencies_finds_vulnerable(tmp_path):
    root = tmp_path / "repo"
    (root / "package.json").parent.mkdir(parents=True)
    (root / "package.json").write_text('{"dependencies": {"next": "15.1.0"}}')
    deps, findings = analyze_dependencies(str(root))
    assert any(d["package"] == "next" for d in deps)
    assert findings
    assert all(f["source"] == "dependency" for f in findings)
    assert any(f["severity"] in ("critical", "high", "medium", "low") for f in findings)


def test_analyze_dependencies_clean(tmp_path):
    root = tmp_path / "repo"
    (root / "requirements.txt").parent.mkdir(parents=True)
    (root / "requirements.txt").write_text("requests==2.32.0\n")
    deps, findings = analyze_dependencies(str(root))
    assert deps
    assert findings == []


def test_analyze_dependencies_empty(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    deps, findings = analyze_dependencies(str(root))
    assert deps == []
    assert findings == []


def test_curated_advisories_reference_real_packages():
    assert len(ADVISORIES) >= 20
    for adv in ADVISORIES:
        assert adv["package"]
        assert adv["version"]
        assert adv["op"] in ("<", "<=", "==")
        assert adv["severity"] in ("critical", "high", "medium", "low")
        assert adv["cwe"]
        assert adv["owasp"]