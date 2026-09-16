import json
import re
from pathlib import Path

from app.config import settings

SKIP_PARTS = {".git", "node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}

ADVISORIES = [
    # npm / node
    {"package": "next", "manager": "npm", "op": "<", "version": "14.2.25",
     "cve": "CVE-2025-29927", "cwe": "CWE-306", "owasp": "A01:2021", "severity": "critical",
     "description": "Next.js middleware authorization bypass allows attackers to disable middleware checks and access protected pages.",
     "remediation": "Upgrade next to >=14.2.25, >=15.2.3, or latest."},
    {"package": "next", "manager": "npm", "op": "<", "version": "15.2.3", "min": "15.0.0",
     "cve": "CVE-2025-29927", "cwe": "CWE-306", "owasp": "A01:2021", "severity": "critical",
     "description": "Next.js middleware authorization bypass (15.x line).",
     "remediation": "Upgrade next to >=15.2.3."},
    {"package": "vite", "manager": "npm", "op": "<", "version": "5.4.12",
     "cve": "CVE-2025-30208", "cwe": "CWE-22", "owasp": "A05:2021", "severity": "high",
     "description": "Vite dev server fs.deny bypass allows reading files outside the workspace root during development.",
     "remediation": "Upgrade vite to >=5.4.12 (or >=6.0.9 / >=7.0.4 for newer majors)."},
    {"package": "axios", "manager": "npm", "op": "<", "version": "1.7.4",
     "cve": "CVE-2024-39338", "cwe": "CWE-918", "owasp": "A10:2021", "severity": "high",
     "description": "Axios SSRF via unexpected URLs in browser builds when the URL contains a credentials or protocol override.",
     "remediation": "Upgrade axios to >=1.7.4."},
    {"package": "axios", "manager": "npm", "op": "<", "version": "0.28.1",
     "cve": "CVE-2024-39338", "cwe": "CWE-918", "owasp": "A10:2021", "severity": "high",
     "description": "Axios SSRF via unexpected URLs (0.x line).",
     "remediation": "Upgrade axios to >=0.28.1 or 1.x."},
    {"package": "ua-parser-js", "manager": "npm", "op": "<", "version": "0.7.33",
     "cve": "CVE-2022-25927", "cwe": "CWE-1333", "owasp": "A05:2021", "severity": "high",
     "description": "ReDoS in ua-parser-js user-agent parsing can cause denial of service.",
     "remediation": "Upgrade ua-parser-js to >=0.7.33."},
    {"package": "minimist", "manager": "npm", "op": "<", "version": "1.2.6",
     "cve": "CVE-2021-44906", "cwe": "CWE-1321", "owasp": "A04:2021", "severity": "medium",
     "description": "Prototype pollution in minimist argument parsing.",
     "remediation": "Upgrade minimist to >=1.2.6."},
    {"package": "lodash", "manager": "npm", "op": "<", "version": "4.17.21",
     "cve": "CVE-2021-23337", "cwe": "CWE-1321", "owasp": "A04:2021", "severity": "high",
     "description": "Prototype pollution in lodash template functions with crafted keys.",
     "remediation": "Upgrade lodash to >=4.17.21."},
    {"package": "event-stream", "manager": "npm", "op": "==", "version": "3.3.6",
     "cve": "CVE-2018-12640", "cwe": "CWE-506", "owasp": "A06:2021", "severity": "high",
     "description": "event-stream 3.3.6 shipped with a malicious dependency (flatmap-stream) that targeted bitcoin wallets.",
     "remediation": "Remove event-stream or replace with a maintained alternative."},
    {"package": "jsonwebtoken", "manager": "npm", "op": "<", "version": "9.0.0",
     "cve": "CVE-2022-23529", "cwe": "CWE-347", "owasp": "A07:2021", "severity": "high",
     "description": "Key confusion in jsonwebtoken allows forging tokens by using an asymmetric key as an HMAC secret.",
     "remediation": "Upgrade jsonwebtoken to >=9.0.0."},
    {"package": "express", "manager": "npm", "op": "<", "version": "4.19.2",
     "cve": "CVE-2024-29041", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "medium",
     "description": "Express route-handling DoS via malformed URL-encoded paths.",
     "remediation": "Upgrade express to >=4.19.2."},
    {"package": "ws", "manager": "npm", "op": "<", "version": "8.17.1",
     "cve": "CVE-2024-37890", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "high",
     "description": "ws vulnerability allows a DoS by sending many specially-crafted frames (8.x line).",
     "remediation": "Upgrade ws to >=8.17.1."},
    {"package": "ws", "manager": "npm", "op": "<", "version": "7.5.10",
     "cve": "CVE-2024-37890", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "high",
     "description": "ws vulnerability allows a DoS by sending many specially-crafted frames (7.x line).",
     "remediation": "Upgrade ws to >=7.5.10."},
    {"package": "tough-cookie", "manager": "npm", "op": "<", "version": "4.1.3",
     "cve": "CVE-2023-26136", "cwe": "CWE-1321", "owasp": "A04:2021", "severity": "medium",
     "description": "Prototype pollution in tough-cookie when parsing cookies.",
     "remediation": "Upgrade tough-cookie to >=4.1.3."},
    {"package": "protobufjs", "manager": "npm", "op": "<", "version": "7.2.5",
     "cve": "CVE-2023-36665", "cwe": "CWE-1321", "owasp": "A04:2021", "severity": "high",
     "description": "Prototype pollution in protobufjs parse() with crafted input (7.x line).",
     "remediation": "Upgrade protobufjs to >=7.2.5."},
    {"package": "protobufjs", "manager": "npm", "op": "<", "version": "6.11.4",
     "cve": "CVE-2023-36665", "cwe": "CWE-1321", "owasp": "A04:2021", "severity": "high",
     "description": "Prototype pollution in protobufjs parse() with crafted input (6.x line).",
     "remediation": "Upgrade protobufjs to >=6.11.4."},
    {"package": "simple-git", "manager": "npm", "op": "<", "version": "3.16.0",
     "cve": "CVE-2022-25912", "cwe": "CWE-78", "owasp": "A03:2021", "severity": "critical",
     "description": "simple-git command injection via malicious git URLs.",
     "remediation": "Upgrade simple-git to >=3.16.0."},
    # python / pip
    {"package": "setuptools", "manager": "pip", "op": "<", "version": "70.0.0",
     "cve": "CVE-2024-6345", "cwe": "CWE-77", "owasp": "A03:2021", "severity": "high",
     "description": "setuptools downloads a crafted sdist that can execute arbitrary code during installation.",
     "remediation": "Upgrade setuptools to >=70.0.0."},
    {"package": "requests", "manager": "pip", "op": "<", "version": "2.32.0",
     "cve": "CVE-2024-35195", "cwe": "CWE-522", "owasp": "A02:2021", "severity": "high",
     "description": "requests may leak proxy credentials when reusing a session across domains.",
     "remediation": "Upgrade requests to >=2.32.0."},
    {"package": "urllib3", "manager": "pip", "op": "<", "version": "2.2.2",
     "cve": "CVE-2024-37891", "cwe": "CWE-522", "owasp": "A02:2021", "severity": "medium",
     "description": "urllib3 proxy-authorization header leak on redirect (2.x line).",
     "remediation": "Upgrade urllib3 to >=2.2.2."},
    {"package": "urllib3", "manager": "pip", "op": "<", "version": "1.26.19",
     "cve": "CVE-2024-37891", "cwe": "CWE-522", "owasp": "A02:2021", "severity": "medium",
     "description": "urllib3 proxy-authorization header leak on redirect (1.x line).",
     "remediation": "Upgrade urllib3 to >=1.26.19."},
    {"package": "jinja2", "manager": "pip", "op": "<", "version": "3.1.4",
     "cve": "CVE-2024-22195", "cwe": "CWE-79", "owasp": "A03:2021", "severity": "medium",
     "description": "Jinja2 HTML attribute XSS via the 'attr' filter with crafted keys.",
     "remediation": "Upgrade jinja2 to >=3.1.4."},
    {"package": "werkzeug", "manager": "pip", "op": "<", "version": "3.0.3",
     "cve": "CVE-2024-34069", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "medium",
     "description": "Werkzeug DoS from very large multipart/form-data requests (3.x line).",
     "remediation": "Upgrade werkzeug to >=3.0.3."},
    {"package": "werkzeug", "manager": "pip", "op": "<", "version": "2.3.8",
     "cve": "CVE-2024-34069", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "medium",
     "description": "Werkzeug DoS from very large multipart/form-data requests (2.x line).",
     "remediation": "Upgrade werkzeug to >=2.3.8."},
    {"package": "cryptography", "manager": "pip", "op": "<", "version": "42.0.2",
     "cve": "CVE-2024-26130", "cwe": "CWE-347", "owasp": "A07:2021", "severity": "medium",
     "description": "cryptography allows NULL bytes to be used in certificate generation, weakening signature verification.",
     "remediation": "Upgrade cryptography to >=42.0.2."},
    {"package": "starlette", "manager": "pip", "op": "<", "version": "0.36.3",
     "cve": "CVE-2024-24762", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "medium",
     "description": "Starlette DoS from a large multipart/form-data request when python-multipart is installed.",
     "remediation": "Upgrade starlette to >=0.36.3."},
    {"package": "pillow", "manager": "pip", "op": "<", "version": "10.3.0",
     "cve": "CVE-2024-28219", "cwe": "CWE-787", "owasp": "A03:2021", "severity": "high",
     "description": "Pillow buffer overflow in image conversion with crafted images.",
     "remediation": "Upgrade pillow to >=10.3.0."},
    {"package": "transformers", "manager": "pip", "op": "<", "version": "4.36.0",
     "cve": "CVE-2023-7016", "cwe": "CWE-502", "owasp": "A08:2021", "severity": "critical",
     "description": "transformers unpickles untrusted data in the local code execution path, allowing arbitrary code execution.",
     "remediation": "Upgrade transformers to >=4.36.0."},
    {"package": "aiohttp", "manager": "pip", "op": "<", "version": "3.9.2",
     "cve": "CVE-2024-23334", "cwe": "CWE-22", "owasp": "A05:2021", "severity": "high",
     "description": "aiohttp static file handler path traversal when follow_symlinks is enabled.",
     "remediation": "Upgrade aiohttp to >=3.9.2."},
    # go
    {"package": "golang.org/x/net", "manager": "go", "op": "<", "version": "0.17.0",
     "cve": "CVE-2023-44487", "cwe": "CWE-400", "owasp": "A05:2021", "severity": "high",
     "description": "HTTP/2 Rapid Reset stream multiplexing DoS.",
     "remediation": "Upgrade golang.org/x/net to >=0.17.0."},
    {"package": "golang.org/x/crypto", "manager": "go", "op": "<", "version": "0.17.0",
     "cve": "CVE-2023-48795", "cwe": "CWE-354", "owasp": "A07:2021", "severity": "medium",
     "description": "Terrapin: SSH protocol prefix truncation weakness affecting channel integrity.",
     "remediation": "Upgrade golang.org/x/crypto to >=0.17.0."},
]


def _parse_version(v: str):
    m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v.strip())
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())


def _cmp(a, b):
    a = a + (0,) * (4 - len(a))
    b = b + (0,) * (4 - len(b))
    return (a > b) - (a < b)


def _matches(advisory: dict, version) -> bool:
    if version is None:
        return False
    target = _parse_version(advisory["version"])
    if target is None:
        return False
    if advisory.get("min"):
        lower = _parse_version(advisory["min"])
        if lower is not None and _cmp(version, lower) < 0:
            return False
    op = advisory["op"]
    if op == "<":
        return _cmp(version, target) < 0
    if op == "<=":
        return _cmp(version, target) <= 0
    if op == "==":
        return _cmp(version, target) == 0
    return False


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _extract_lower_bound(raw: str):
    raw = raw.strip().strip('"').strip("'")
    if not raw or raw in ("*", "latest"):
        return None
    m = re.search(r"(?:^|[\^~=><,\s])(\d+(?:\.\d+)*)", raw)
    if m:
        return _parse_version(m.group(1))
    return None


def _parse_package_json(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for name, raw in (data.get(section) or {}).items():
            version = _extract_lower_bound(raw)
            if version is not None:
                out.append({"package": _normalize_name(name), "version": version,
                            "raw": raw, "manager": "npm", "file": path})
    return out


def _parse_requirements(path: Path) -> list[dict]:
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-r", "-e", "--")):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(?:==|>=|<=|~=)\s*([\d.*]+)", line)
        if not m:
            continue
        version = _extract_lower_bound(m.group(2))
        if version is not None:
            out.append({"package": _normalize_name(m.group(1)), "version": version,
                        "raw": m.group(2), "manager": "pip", "file": path})
    return out


def _parse_pyproject(path: Path) -> list[dict]:
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for m in re.finditer(r"^\s*([A-Za-z0-9_.\-]+)\s*=\s*['\"]([^'\"]+)['\"]", text, re.M):
        name, raw = m.group(1), m.group(2)
        if name.lower() in ("name", "version", "description", "authors", "readme", "license", "requires-python", "python"):
            continue
        version = _extract_lower_bound(raw)
        if version is not None:
            out.append({"package": _normalize_name(name), "version": version,
                        "raw": raw, "manager": "pip", "file": path})
    for m in re.finditer(r"^\s*(?:dependencies|dev-dependencies|optional-dependencies|all-dependencies)\s*=\s*\[([^\]]*)\]", text, re.M):
        for item in m.group(1).split(","):
            item = item.strip().strip('"').strip("'")
            if not item:
                continue
            package = item.split(">=")[0].split("==")[0].split("~=")[0].split("<")[0].split(">")[0].strip()
            version = _extract_lower_bound(item)
            if version is not None and package:
                out.append({"package": _normalize_name(package), "version": version,
                            "raw": item, "manager": "pip", "file": path})
    return out


def _parse_go_mod(path: Path) -> list[dict]:
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for m in re.finditer(r"^\s*([\w./\-]+)\s+v(\d+\.\d+(?:\.\d+)?)", text, re.M):
        version = _parse_version(m.group(2))
        if version is not None:
            out.append({"package": m.group(1), "version": version,
                        "raw": m.group(2), "manager": "go", "file": path})
    return out


def _parse_manifest(path: Path) -> list[dict]:
    name = path.name
    if name == "package.json":
        return _parse_package_json(path)
    if name == "requirements.txt":
        return _parse_requirements(path)
    if name == "pyproject.toml":
        return _parse_pyproject(path)
    if name == "go.mod":
        return _parse_go_mod(path)
    return []


def _collect_dependencies(repo_path: Path) -> list[dict]:
    deps: list[dict] = []
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_path)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        if p.name not in ("package.json", "requirements.txt", "pyproject.toml", "go.mod"):
            continue
        deps.extend(_parse_manifest(p))
    return deps


def analyze_dependencies(repo_path) -> tuple[list[dict], list[dict]]:
    repo_path = Path(repo_path)
    dependencies = _collect_dependencies(repo_path)
    for dep in dependencies:
        dep["file"] = dep["file"].as_posix()
    findings: list[dict] = []
    for dep in dependencies:
        for advisory in ADVISORIES:
            if advisory["manager"] != dep["manager"]:
                continue
            if advisory["package"] != dep["package"]:
                continue
            if not _matches(advisory, dep["version"]):
                continue
            findings.append({
                "rule_id": "DEP_VULNERABLE_PACKAGE",
                "severity": advisory["severity"],
                "category": "dependencies",
                "file": dep["file"],
                "line": None,
                "evidence": f"{dep['package']} {dep['raw']} — {advisory['cve']}",
                "title": f"{dep['package']} {advisory['cve']}",
                "description": advisory["description"],
                "remediation": advisory["remediation"],
                "confidence": "confirmed",
                "cwe": advisory["cwe"],
                "owasp": advisory["owasp"],
                "impact": f"An attacker can exploit {advisory['cve']} in {dep['package']} "
                         f"({dep['raw']} installed via {dep['file']}).",
                "attack_scenario": "An attacker targets the known vulnerability remotely or via crafted input, "
                                   "depending on how the package is used.",
                "verification": f"Check installed version of {dep['package']} and compare against the advisory.",
                "source": "dependency",
            })
            break
    return dependencies, findings