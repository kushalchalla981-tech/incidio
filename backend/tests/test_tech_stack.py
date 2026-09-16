from pathlib import Path

from app.services.tech_stack import detect_stack


def _project(files: dict[str, str], tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


def test_detects_nextjs(tmp_path):
    root = _project({
        "package.json": '{"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}',
        "next.config.js": "module.exports = {}",
    }, tmp_path)
    stack = detect_stack(root)
    assert stack["language"] == "JavaScript/TypeScript"
    assert stack["framework"] == "Next.js"
    assert "npm" in stack["detectors"]


def test_detects_fastapi(tmp_path):
    root = _project({
        "requirements.txt": "fastapi==0.109.0\nuvicorn==0.27.0\n",
        "app/main.py": "from fastapi import FastAPI\n",
    }, tmp_path)
    stack = detect_stack(root)
    assert stack["language"] == "Python"
    assert stack["framework"] == "FastAPI"
    assert "pip" in stack["detectors"]


def test_detects_go(tmp_path):
    root = _project({
        "go.mod": "module example.com/app\n\ngo 1.21\n",
        "main.go": "package main\n",
    }, tmp_path)
    stack = detect_stack(root)
    assert stack["language"] == "Go"
    assert "go" in stack["detectors"]


def test_unknown_project(tmp_path):
    root = _project({"README.md": "nothing here\n"}, tmp_path)
    stack = detect_stack(root)
    assert stack["language"] is None
    assert stack["framework"] is None
    assert stack["detectors"] == []


def test_skips_vendor_dirs(tmp_path):
    root = _project({
        "node_modules/pkg/package.json": '{"dependencies": {"next": "^14.0.0"}}',
        "app/package.json": '{"dependencies": {"express": "^4.18.0"}}',
    }, tmp_path)
    stack = detect_stack(root)
    assert "npm" in stack["detectors"]