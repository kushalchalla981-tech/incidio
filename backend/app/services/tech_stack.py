import json
import re
from pathlib import Path

MANIFEST_PATTERNS = [
    ("package.json", "npm", "nodejs"),
    ("yarn.lock", "npm", "nodejs"),
    ("pnpm-lock.yaml", "npm", "nodejs"),
    ("requirements.txt", "pip", "python"),
    ("pyproject.toml", "pip", "python"),
    ("Pipfile", "pip", "python"),
    ("poetry.lock", "pip", "python"),
    ("go.mod", "go", "go"),
    ("go.sum", "go", "go"),
    ("Cargo.toml", "cargo", "rust"),
    ("composer.json", "composer", "php"),
    ("Gemfile", "bundler", "ruby"),
    ("Gems.lock", "bundler", "ruby"),
    ("build.gradle", "gradle", "java"),
    ("pom.xml", "maven", "java"),
    ("*.csproj", "nuget", "dotnet"),
]

FRAMEWORK_HINTS = [
    (re.compile(r'"next"\s*:|^next(?:==|>=|~=|$)', re.M), "Next.js"),
    (re.compile(r'"react"\s*:|^react(?:==|>=|~=|$)', re.M), "React"),
    (re.compile(r'"vue"\s*:|^vue(?:==|>=|~=|$)', re.M), "Vue"),
    (re.compile(r'"angular"\s*:'), "Angular"),
    (re.compile(r'"express"\s*:|^express(?:==|>=|~=|$)', re.M), "Express"),
    (re.compile(r'"fastify"\s*:|^fastify(?:==|>=|~=|$)', re.M), "Fastify"),
    (re.compile(r'"django"\s*:|^django(?:==|>=|~=|$)', re.M), "Django"),
    (re.compile(r'"flask"\s*:|^flask(?:==|>=|~=|$)', re.M), "Flask"),
    (re.compile(r'"fastapi"\s*:|^fastapi(?:==|>=|~=|$)', re.M), "FastAPI"),
    (re.compile(r'"gin-gonic/gin"'), "Gin"),
    (re.compile(r'"laravel/framework"'), "Laravel"),
    (re.compile(r'"symfony/symfony"'), "Symfony"),
    (re.compile(r'"spring-boot"'), "Spring Boot"),
    (re.compile(r'"rails"'), "Ruby on Rails"),
]

LANGUAGE_MARKERS = {
    "nodejs": "JavaScript/TypeScript",
    "python": "Python",
    "go": "Go",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "java": "Java",
    "dotnet": ".NET",
}


def _read_small(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:60000]
    except (OSError, PermissionError):
        return ""


def detect_stack(repo_path: Path) -> dict:
    managers: list[dict] = []
    languages: set[str] = set()
    seen_files: list[str] = []
    sample_texts: list[str] = []

    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_path).as_posix()
        if any(part in (".git", "node_modules", "vendor", ".venv", "dist", "build", "__pycache__")
               for part in rel.split("/")):
            continue
        name = p.name
        for pattern, manager, language in MANIFEST_PATTERNS:
            matched = pattern.endswith("*") and name.endswith(pattern[1:]) or name == pattern
            if matched and manager not in {m["manager"] for m in managers}:
                managers.append({"manager": manager, "file": rel})
                languages.add(language)
                sample_texts.append(_read_small(p))
                seen_files.append(rel)
                break
        if len(sample_texts) >= 8:
            break

    if not managers and (repo_path / "Dockerfile").exists():
        languages.add("unknown")

    framework = None
    for text in sample_texts:
        for pattern, label in FRAMEWORK_HINTS:
            if pattern.search(text):
                framework = label
                break
        if framework:
            break

    language = None
    for lang in ("python", "nodejs", "go", "rust", "php", "ruby", "java", "dotnet"):
        if lang in languages:
            language = LANGUAGE_MARKERS[lang]
            break

    return {
        "language": language,
        "framework": framework,
        "package_managers": managers,
        "detected_files": seen_files,
        "detectors": [m["manager"] for m in managers],
    }