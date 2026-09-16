import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import unquote, urlparse

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.services.zip_ingest import extract_zip, validate_zip_bytes
from app.services.tech_stack import detect_stack
from app.services.deps import analyze_dependencies
from app.services.url_checker import validate_live_url, run_url_checks

SCAN_TMP = Path(settings.SCAN_TMP_DIR).resolve()
ALLOWED_HOSTS = set(settings.SCAN_ALLOWED_HOSTS)


class ScanAbortError(Exception):
    pass


def validate_repo_url(url: str) -> str:
    stripped = url.strip()
    if not stripped or len(stripped) > 2048:
        raise ValueError("repo URL is empty or too long")
    if stripped.startswith("-"):
        raise ValueError("repo URL must not start with '-'")
    parsed = urlparse(stripped)
    if parsed.scheme != "https":
        raise ValueError("repo URL must use https")
    if parsed.username or parsed.password:
        raise ValueError("repo URL must not contain credentials")
    host = (parsed.hostname or "").lower()
    if host != host.rstrip("."):
        raise ValueError("repo URL host must not end with '.'")
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"repo URL host not allowed: {host}")
    if ".." in unquote(parsed.path):
        raise ValueError("repo URL path must not contain '..'")
    return stripped


def _run_git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.kill()
        proc.wait(timeout=10)
        raise TimeoutError(f"git clone timed out after {timeout}s")
    return subprocess.CompletedProcess(args, proc.returncode)


def clone_repo(url: str, scan_id: str) -> Path:
    dest = SCAN_TMP / scan_id
    os.makedirs(SCAN_TMP, exist_ok=True)
    cmd = ["git", "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never",
           "clone", "--depth", "1", "--single-branch", "--no-tags",
           "--no-recurse-submodules", "--", url, str(dest)]
    try:
        result = _run_git(cmd, timeout=60)
    except FileNotFoundError:
        raise ScanAbortError("git executable not found on PATH; install git to scan repos")
    if result.returncode != 0 or not (dest / ".git").exists():
        raise ScanAbortError(f"git clone failed (exit {result.returncode})")
    return dest


def _rmtree_retry(path: Path):
    for attempt in range(3):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt < 2:
                time.sleep(0.5)
    print(f"WARNING: could not remove scan temp dir {path}")


SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}
SKIP_EXT = {".min.js", ".lock", ".map", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"}
SKIP_NAMES = {"package-lock.json", "yarn.lock"}
INCLUDE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".php", ".rb", ".go", ".java", ".cs", ".json", ".yml", ".yaml", ".sql"}
SPECIAL_NAMES = {"Dockerfile", "next.config.js", "next.config.ts", "config.js", "config.ts"}


def iter_source_files(repo_path: Path):
    total_bytes = 0
    count = 0
    for p in repo_path.rglob("*"):
        rel = p.relative_to(repo_path)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if not p.is_file():
            continue
        name = p.name
        ext = p.suffix
        if ext in SKIP_EXT or name in SKIP_NAMES:
            continue
        included = (
            name in SPECIAL_NAMES
            or name == ".env"
            or name.startswith(".env.")
            or ext in INCLUDE_EXT
        )
        if not included:
            continue
        try:
            with open(p, "rb") as f:
                head = f.read(8000)
            if b"\x00" in head:
                continue
            total_bytes += p.stat().st_size
            if total_bytes > settings.MAX_REPO_SIZE_MB * 1024 * 1024:
                raise ScanAbortError("repo exceeds MAX_REPO_SIZE_MB")
            count += 1
            if count > settings.MAX_SCAN_FILES:
                raise ScanAbortError("repo exceeds MAX_SCAN_FILES")
        except (FileNotFoundError, PermissionError, OSError):
            continue
        yield rel, p


@dataclass
class RULE:
    rule_id: str
    name: str
    category: str
    severity: str
    extensions: Optional[set[str]]
    pattern: Optional[re.Pattern] = None
    patterns: list[re.Pattern] = field(default_factory=list)
    description: str = ""
    remediation: str = ""
    handler: Optional[str] = None
    confidence: str = "potential"
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    impact: str = ""
    attack_scenario: str = ""
    verification: str = ""


RULES: list[RULE] = [
    RULE("SECRET_AWS_KEY", "AWS Access Key", "secrets", "critical",
         None, re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}\b"),
         description="AWS access key exposed in source",
         remediation="Rotate the key immediately and remove it from the repo", handler="_skip_placeholder",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_OPENAI_KEY", "OpenAI API Key", "secrets", "critical",
         None, None,
         patterns=[re.compile(r"\bsk-(?:proj|svcacct|admin)-(?:[A-Za-z0-9_-]{74}|[A-Za-z0-9_-]{58})T3BlbkFJ(?:[A-Za-z0-9_-]{74}|[A-Za-z0-9_-]{58})\b"),
                   re.compile(r"\bsk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}\b")],
         description="OpenAI API key exposed in source",
         remediation="Revoke the key and use a secret manager",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_GITHUB_TOKEN", "GitHub Token", "secrets", "critical",
         None, None,
         patterns=[re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"),
                   re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")],
         description="GitHub token exposed in source",
         remediation="Revoke the token and remove it from the repo",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_PRIVATE_KEY", "Private Key", "secrets", "critical",
         None, re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
         description="Private key material committed to the repo",
         remediation="Remove the key and rotate it",
         confidence="confirmed", cwe="CWE-312", owasp="A02:2021"),
    RULE("SECRET_GENERIC_API_KEY", "Generic API Key", "secrets", "high",
         None, re.compile(r"(?:api[_-]?key|apikey|secret|token)\s*[=:]\s*[\"']([^\"'\s]{16,})[\"']"),
         description="Possible hardcoded API key",
         remediation="Move the secret to environment variables", handler="_entropy_gate",
         confidence="strong", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_DB_URL", "Database URL with Credentials", "secrets", "high",
         None, re.compile(r"(?:postgres(?:ql)?|mysql|mongo(?:db)?\+srv|redis|amqp)://[^\s:@/]+:[^\s:@/]+@"),
         description="Database connection string with embedded credentials",
         remediation="Use a secret manager and never commit credentials",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_ENV_COMMITTED", "Committed .env File", "secrets", "critical",
         None, None,
         description="Environment file committed to the repo",
         remediation="Remove the file and rotate any secrets it contained", handler="_env_filename",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("SECRET_ENV_NEXT_PUBLIC", "NEXT_PUBLIC Secret", "secrets", "high",
         None, re.compile(r"NEXT_PUBLIC_[A-Z0-9_]*?(?:KEY|SECRET|TOKEN)\s*="),
         description="Secret exposed via NEXT_PUBLIC environment variable",
         remediation="NEXT_PUBLIC vars are shipped to the browser; move secrets server-side",
         confidence="strong", cwe="CWE-200", owasp="A01:2021"),
    RULE("SECRET_STRIPE", "Stripe Live Key", "secrets", "critical",
         None, re.compile(r"\bsk_live_[0-9a-zA-Z]{24}\b"),
         description="Stripe live secret key exposed",
         remediation="Rotate the key immediately",
         confidence="confirmed", cwe="CWE-798", owasp="A07:2021"),
    RULE("DANGER_EVAL", "Dangerous Code Execution", "code", "high",
         None, re.compile(r"\beval\(|exec\(|shell_exec\(|os\.system\(|subprocess\.call\(|subprocess\.Popen\("),
         description="Arbitrary code execution sink",
         remediation="Avoid eval/exec of untrusted input; use safe parsers", handler="_literal_or_variable",
         confidence="potential", cwe="CWE-95", owasp="A03:2021"),
    RULE("DANGER_CHILD_PROCESS", "Child Process Execution", "code", "high",
         None, re.compile(r"child_process\.(?:exec|execSync|spawn|spawnSync)\("),
         description="Node child process execution",
         remediation="Validate and sanitize command inputs", handler="_literal_or_variable",
         confidence="potential", cwe="CWE-78", owasp="A03:2021"),
    RULE("DANGER_XSS_INNERHTML", "Unsafe HTML Injection", "code", "high",
         None, re.compile(r"innerHTML\s*=|outerHTML\s*=|dangerouslySetInnerHTML|v-html="),
         description="Potential XSS via raw HTML injection",
         remediation="Escape user input or use framework-safe rendering",
         confidence="strong", cwe="CWE-79", owasp="A03:2021"),
    RULE("DANGER_SQL_CONCAT", "SQL Injection via Concatenation", "code", "high",
         None, re.compile(r"(SELECT|INSERT|UPDATE|DELETE|WHERE)"),
         description="SQL built by string concatenation may be injectable",
         remediation="Use parameterized queries", handler="_sql_concat",
         confidence="potential", cwe="CWE-89", owasp="A03:2021"),
    RULE("DANGER_UNSAFE_YAML", "Unsafe YAML/Pickle Load", "code", "medium",
         None, re.compile(r"yaml\.load\(|yaml\.unsafe_load\(|pickle\.loads\("),
         description="Unsafe deserialization of untrusted data",
         remediation="Use yaml.safe_load or JSON",
         confidence="strong", cwe="CWE-502", owasp="A08:2021"),
    RULE("DANGER_TEMPLATE_ESCAPE_OFF", "Template Autoescape Disabled", "code", "medium",
         None, re.compile(r"autoescape\s*=\s*False|mark_safe\(|raw="),
         description="Template escaping disabled — XSS risk",
         remediation="Keep autoescape enabled",
         confidence="strong", cwe="CWE-79", owasp="A03:2021"),
    RULE("CONFIG_CORS_CREDENTIALS", "CORS Wildcard with Credentials", "config", "high",
         None, re.compile(r"allow_origins\s*=\s*\[?[\"']\*[\"']\]?"),
         description="CORS allows all origins, possibly with credentials",
         remediation="Restrict allow_origins to trusted domains", handler="_cors_correlation",
         confidence="strong", cwe="CWE-942", owasp="A01:2021"),
    RULE("CONFIG_DEBUG_TRUE", "Debug Mode Enabled", "config", "medium",
         None, re.compile(r"debug\s*=\s*True|APP_DEBUG\s*=\s*true|NODE_ENV\s*=\s*[\"']development[\"']"),
         description="Debug mode enabled in production-facing code",
         remediation="Disable debug mode in production", handler="_skip_test_paths",
         confidence="potential", cwe="CWE-489", owasp="A05:2021"),
    RULE("CONFIG_HARDCODED_SECRET_KEY", "Hardcoded Secret Key", "config", "high",
         None, re.compile(r"(?:SECRET_KEY|JWT_SECRET|signing_key|SESSION_SECRET)\s*[=:]\s*[\"']([^\"']+)[\"']"),
         description="Hardcoded secret key material",
         remediation="Generate a random key and store it in a secret manager", handler="_secret_blocklist",
         confidence="strong", cwe="CWE-798", owasp="A07:2021"),
    RULE("CONFIG_DEFAULT_CREDS", "Default Credentials", "config", "high",
         None, None,
         patterns=[re.compile(r"(?:username|user|login)\s*[=:]\s*[\"']admin[\"']"),
                   re.compile(r"password\s*[=:]\s*[\"'](?:admin|password|123456)[\"']")],
         description="Default or weak credentials",
         remediation="Require strong unique credentials", handler="_creds_correlation",
         confidence="strong", cwe="CWE-798", owasp="A07:2021"),
    RULE("CONFIG_SUPABASE_NO_RLS", "Supabase Without Row Level Security", "config", "high",
         None, None,
         description="Supabase client present but no RLS policies found",
         remediation="Enable RLS and define policies for all tables", handler="_supabase_correlation",
         confidence="potential", cwe="CWE-284", owasp="A01:2021"),
]

EXTENSIONS_CONF = {".py", ".js", ".ts", ".tsx", ".jsx", ".yml", ".yaml", ".json"}
EXTENSIONS_SQL = {".py", ".sql", ".js", ".ts"}
for _r in RULES:
    if _r.category == "secrets":
        _r.extensions = None
    elif _r.rule_id == "DANGER_SQL_CONCAT":
        _r.extensions = EXTENSIONS_SQL
    elif _r.category == "config":
        _r.extensions = EXTENSIONS_CONF
    else:
        _r.extensions = None

BLOCKLIST = {"supersecretkey", "supersecretjwt", "secret", "changeme", "password", "your-secret-key", "change-me", "replace_me"}


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    n = len(s)
    entropy = 0.0
    for c in counts.values():
        p = c / n
        entropy -= p * math.log2(p)
    return entropy


def _mask_secret(s: str) -> str:
    prefixes = ("sk-", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "AKIA", "sk_live_")
    if s.startswith(prefixes):
        return s[:4] + "****"
    return s[:3] + "****"


def _truncate_evidence(s: str, limit: int = 200) -> str:
    if len(s) > limit:
        return s[:limit]
    return s


def _skip_placeholder(evidence: str) -> bool:
    return "XXXXXXXX" in evidence


def _entropy_gate(evidence: str, group: str) -> bool:
    return _shannon_entropy(group) >= 3.5


def _env_filename(rel: Path) -> bool:
    name = rel.name
    return name in (".env", ".env.local", ".env.production")


def _eval_arg(line: str) -> str:
    rest = line.split("(", 1)[-1]
    if ")" in rest:
        rest = rest.split(")", 1)[0]
    return rest.strip().strip('"').strip("'")


def _literal_or_variable(arg: str) -> str:
    if re.fullmatch(r"[a-z_]\w*", arg):
        return "high"
    return "medium"


def _sql_concat(lines: list[str], idx: int) -> Optional[str]:
    lo = max(0, idx - 1)
    hi = min(len(lines), idx + 2)
    for i in range(lo, hi):
        if re.search(r"\+|f\"| % ", lines[i]):
            return "high"
    return None


def _cors_correlation(text: str) -> str:
    if re.search(r"allow_credentials\s*=\s*True", text):
        return "high"
    return "medium"


def _skip_test_paths(rel: Path) -> bool:
    parts = [p.lower() for p in rel.parts]
    return any(p.startswith((".github", "test", "spec")) for p in parts)


def _secret_blocklist(value: str) -> str:
    if value.lower() in BLOCKLIST:
        return "high"
    return "medium"


def _creds_correlation(lines: list[str]) -> str:
    positions = []
    for i, line in enumerate(lines):
        if re.search(r"(?:username|user|login)\s*[=:]\s*[\"']admin[\"']", line):
            positions.append(i)
        if re.search(r"password\s*[=:]\s*[\"'](?:admin|password|123456)[\"']", line):
            positions.append(i)
    positions.sort()
    for i in range(len(positions) - 1):
        if positions[i + 1] - positions[i] <= 3:
            return "high"
    return "medium"


def _supabase_correlation(texts: dict[str, str]) -> Optional[tuple[str, str]]:
    has_sql_rls = False
    for rel, text in texts.items():
        if rel.endswith(".sql") and ("rowLevelSecurity" in text or "create policy" in text):
            has_sql_rls = True
            break
    if has_sql_rls:
        return None
    for rel, text in texts.items():
        if rel.endswith((".js", ".ts", ".tsx", ".jsx")) and "createClient" in text:
            if "supabase.co" in text or "SUPABASE_" in text:
                return rel, text
    return None


def _rule_applies_to_file(rule: RULE, rel: Path) -> bool:
    name = rel.name
    if rule.rule_id == "SECRET_ENV_NEXT_PUBLIC":
        return name.startswith(".env") or name in ("next.config.js", "next.config.ts")
    if rule.rule_id == "SECRET_ENV_COMMITTED":
        return _env_filename(rel)
    if rule.rule_id == "CONFIG_SUPABASE_NO_RLS":
        return False
    if rule.extensions is not None:
        return rel.suffix in rule.extensions or name.startswith(".env") or name in ("next.config.js", "next.config.ts")
    return True


def scan_repo(repo_path: Path, scanned: Optional[list[str]] = None) -> tuple[list[dict], list[tuple[str, int]], dict[str, str], int]:
    findings: list[dict] = []
    texts: dict[str, str] = {}
    file_hits: dict[str, int] = {}

    for rel, abs_path in iter_source_files(repo_path):
        try:
            raw = abs_path.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, PermissionError, OSError):
            continue
        texts[rel.as_posix()] = raw[:settings.MAX_LLM_FILE_CHARS]
        if scanned is not None:
            scanned.append(rel.as_posix())
        lines = raw.splitlines()

        if _env_filename(rel):
            findings.append({
                "rule_id": "SECRET_ENV_COMMITTED",
                "severity": "critical",
                "category": "secrets",
                "file": rel.as_posix(),
                "line": None,
                "evidence": "committed .env file",
                "description": "Environment file committed to the repo",
                "remediation": "Remove the file and rotate any secrets it contained",
                "confidence": "confirmed",
                "cwe": "CWE-798",
                "owasp": "A07:2021",
                "source": "rules",
            })
            file_hits[rel.as_posix()] = file_hits.get(rel.as_posix(), 0) + 1

        for idx, line in enumerate(lines):
            line_no = idx + 1
            for rule in RULES:
                if not _rule_applies_to_file(rule, rel):
                    continue
                patterns = rule.patterns if rule.patterns else ([rule.pattern] if rule.pattern else [])
                if not patterns:
                    continue
                for pat in patterns:
                    m = pat.search(line)
                    if not m:
                        continue
                    severity = None
                    if rule.handler == "_skip_placeholder":
                        if _skip_placeholder(m.group(0)):
                            continue
                        severity = rule.severity
                    elif rule.handler == "_entropy_gate":
                        if not _entropy_gate(m.group(0), m.group(1)):
                            continue
                        severity = rule.severity
                    elif rule.handler == "_literal_or_variable":
                        severity = _literal_or_variable(_eval_arg(line))
                    elif rule.handler == "_sql_concat":
                        severity = _sql_concat(lines, idx)
                        if severity is None:
                            continue
                    elif rule.handler == "_skip_test_paths":
                        if _skip_test_paths(rel):
                            continue
                        severity = rule.severity
                    elif rule.handler == "_secret_blocklist":
                        severity = _secret_blocklist(m.group(1))
                    else:
                        severity = rule.severity
                    findings.append({
                        "rule_id": rule.rule_id,
                        "severity": severity,
                        "category": rule.category,
                        "file": rel.as_posix(),
                        "line": line_no,
                        "evidence": _truncate_evidence(_mask_secret(m.group(0))),
                        "description": rule.description,
                        "remediation": rule.remediation,
                        "confidence": rule.confidence,
                        "cwe": rule.cwe,
                        "owasp": rule.owasp,
                        "impact": rule.impact,
                        "attack_scenario": rule.attack_scenario,
                        "verification": rule.verification,
                        "source": "rules",
                    })
                    file_hits[rel.as_posix()] = file_hits.get(rel.as_posix(), 0) + 1
                    break

        text = "\n".join(lines)
        for rule in RULES:
            if not _rule_applies_to_file(rule, rel):
                continue
            if rule.handler == "_cors_correlation":
                m = rule.pattern.search(text)
                if m:
                    findings.append({
                        "rule_id": rule.rule_id,
                        "severity": _cors_correlation(text),
                        "category": rule.category,
                        "file": rel.as_posix(),
                        "line": None,
                        "evidence": _truncate_evidence(m.group(0)),
                        "description": rule.description,
                        "remediation": rule.remediation,
                        "confidence": rule.confidence,
                        "cwe": rule.cwe,
                        "owasp": rule.owasp,
                        "source": "rules",
                    })
                    file_hits[rel.as_posix()] = file_hits.get(rel.as_posix(), 0) + 1
            elif rule.handler == "_creds_correlation":
                m1 = rule.patterns[0].search(text)
                m2 = rule.patterns[1].search(text)
                if m1 or m2:
                    findings.append({
                        "rule_id": rule.rule_id,
                        "severity": _creds_correlation(lines),
                        "category": rule.category,
                        "file": rel.as_posix(),
                        "line": None,
                        "evidence": _truncate_evidence((m1.group(0) if m1 else "") + " / " + (m2.group(0) if m2 else "")),
                        "description": rule.description,
                        "remediation": rule.remediation,
                        "confidence": rule.confidence,
                        "cwe": rule.cwe,
                        "owasp": rule.owasp,
                        "source": "rules",
                    })
                    file_hits[rel.as_posix()] = file_hits.get(rel.as_posix(), 0) + 1

    sup = _supabase_correlation(texts)
    if sup is not None:
        rel, _text = sup
        findings.append({
            "rule_id": "CONFIG_SUPABASE_NO_RLS",
            "severity": "high",
            "category": "config",
            "file": rel,
            "line": None,
            "evidence": "createClient without RLS policies in repo",
            "description": "Supabase client present but no RLS policies found",
            "remediation": "Enable RLS and define policies for all tables",
            "confidence": "potential",
            "cwe": "CWE-284",
            "owasp": "A01:2021",
            "source": "rules",
        })
        file_hits[rel] = file_hits.get(rel, 0) + 1

    files_with_hits = sorted(file_hits.items(), key=lambda kv: (-kv[1], kv[0]))
    total_bytes = sum(p.stat().st_size for p in repo_path.rglob("*") if p.is_file())
    return findings, files_with_hits, texts, total_bytes


SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 7, "low": 3, "informational": 1}

KNOWN_CATEGORIES = ("secrets", "config", "code")
SECRET_CATEGORY_HINTS = ("secret", "key", "token", "credential")
CONFIG_CATEGORY_HINTS = ("cors", "debug", "config", "header", "secret-key")


def _letter_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 50:
        return "C"
    if score >= 25:
        return "D"
    return "F"


def _category_of(finding: dict) -> str:
    category = str(finding.get("category") or "").strip().lower()
    if category in KNOWN_CATEGORIES:
        return category
    if any(hint in category for hint in SECRET_CATEGORY_HINTS):
        return "secrets"
    if any(hint in category for hint in CONFIG_CATEGORY_HINTS):
        return "config"
    return "code"


def score_report(findings: list[dict]) -> dict:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    sub_scores = {"secrets_score": 100, "config_score": 100, "code_score": 100}
    total_weight = 0
    for finding in findings:
        severity = finding.get("severity")
        weight = SEVERITY_WEIGHTS.get(severity)
        if weight is None:
            continue
        counts[severity] = counts.get(severity, 0) + 1
        total_weight += weight
        category = _category_of(finding)
        key = f"{category}_score"
        sub_scores[key] = max(0, sub_scores[key] - weight)
    score = max(0.0, 100.0 - total_weight)
    return {
        "score": score,
        "grade": _letter_grade(score),
        "sub_scores": sub_scores,
        "counts": counts,
    }


def build_summary(scan_run, findings: list[dict]) -> str:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    files: set[str] = set()
    for finding in findings:
        severity = finding.get("severity")
        if severity in SEVERITY_WEIGHTS:
            counts[severity] = counts.get(severity, 0) + 1
        file_value = finding.get("file")
        if file_value is not None:
            files.add(str(file_value))
    return (
        f"{len(findings)} findings ({counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low) across {len(files)} files"
    )


from openai import OpenAIError  # noqa: E402

from app.database import Database  # noqa: E402

LLM_MAX_FINDINGS = 20

LLM_SYSTEM_PROMPT = (
    "You are a senior application security auditor reviewing source code for "
    "security vulnerabilities. Focus on the OWASP Top 10 (injection, broken "
    "authentication, sensitive data exposure, XML external entities, broken "
    "access control, security misconfiguration, cross-site scripting, insecure "
    "deserialization, vulnerable components, insufficient logging), hardcoded "
    "secrets and credentials, and supply-chain risks. Precision over recall: "
    "only report issues you are highly confident are real vulnerabilities, and "
    "only if you can point to specific evidence in the code. Do not invent or "
    "guess issues. For every finding provide the file path, the line number if "
    "known, a severity from the allowed set, a category, a concise description, "
    "a short evidence snippet, and a remediation suggestion. If no issues are "
    "found, return an empty findings list."
)

_llm_client: Optional[OpenAI] = None
_scan_semaphore = asyncio.Semaphore(settings.SCAN_MAX_CONCURRENT)


def _get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60.0)
    return _llm_client


class LLMFinding(BaseModel):
    file: str
    line: Optional[int] = None
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    category: str = "code"
    description: str = ""
    evidence: Optional[str] = None
    remediation: Optional[str] = None


class LLMReview(BaseModel):
    findings: list[LLMFinding] = Field(default_factory=list)


def select_llm_files(
    file_hits: list[tuple[str, int]], texts: dict[str, str]
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, int, int]] = []
    for path, hits in file_hits:
        if path in texts:
            candidates.append((path, hits, len(texts[path])))
    candidates.sort(key=lambda c: (-c[1], c[2]))
    selected: list[tuple[str, str]] = []
    total_chars = 0
    for path, hits, size in candidates:
        if len(selected) >= settings.MAX_LLM_FILES:
            break
        snippet = f"# {path}\n{texts[path][:settings.MAX_LLM_FILE_CHARS]}"
        needed = len(snippet) + 2
        if total_chars + needed > settings.MAX_LLM_INPUT_CHARS:
            break
        total_chars += needed
        selected.append((path, snippet))
    return selected


def llm_review(files: list[tuple[str, str]]) -> tuple[list[dict], str]:
    if not files:
        return [], "rules_only"
    if not settings.OPENAI_API_KEY:
        return [], "rules_only"
    parts: list[str] = []
    total = 0
    for path, text in files:
        if text.startswith("# "):
            snippet = text
        else:
            snippet = f"# {path}\n{text[:settings.MAX_LLM_FILE_CHARS]}"
        if total + len(snippet) > settings.MAX_LLM_INPUT_CHARS:
            break
        parts.append(snippet)
        total += len(snippet) + 2
    if not parts:
        return [], "rules_only"
    try:
        client = _get_llm_client()
        resp = client.beta.chat.completions.parse(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Review the following source files for security "
                        "vulnerabilities. Return a JSON object with a "
                        '"findings" array matching the required schema.\n\n'
                        + "\n\n".join(parts)
                    ),
                },
            ],
            response_format=LLMReview,
            max_tokens=4096,
        )
    except OpenAIError:
        return [], "rules_only"
    except Exception:
        return [], "rules_only"
    try:
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            return [], "rules_only"
        review = getattr(msg, "parsed", None)
        if review is None:
            return [], "rules_only"
        findings = [f.model_dump() for f in review.findings[:LLM_MAX_FINDINGS]]
        return findings, "ok"
    except Exception:
        return [], "rules_only"


def _dedup_key(finding: dict) -> tuple[str, Optional[int], str]:
    file_value = str(finding.get("file") or "").replace("\\", "/")
    while file_value.startswith("./"):
        file_value = file_value[2:]
    line = finding.get("line")
    try:
        line = int(line) if line is not None else None
    except (TypeError, ValueError):
        line = None
    return (file_value, line, _category_of(finding))


def merge_findings(rule_findings: list[dict], llm_findings: list[dict]) -> list[dict]:
    seen: set[tuple[str, Optional[int], str]] = set()
    merged: list[dict] = []
    for finding in rule_findings:
        key = _dedup_key(finding)
        if key not in seen:
            seen.add(key)
        merged.append(finding)
    for finding in llm_findings:
        key = _dedup_key(finding)
        if key not in seen:
            seen.add(key)
            merged.append(finding)
    return merged


def _finding_id(repo_url: str, rule_id: Optional[str], file: str, line: Optional[int], project_id: Optional[str] = None) -> str:
    scope = project_id or repo_url
    raw = f"{scope}|{rule_id or 'llm'}|{file or ''}|{line if line is not None else ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _normalize_severity(severity: Optional[str]) -> str:
    if severity in ("critical", "high", "medium", "low", "informational"):
        return severity
    return "medium"


async def promote_finding_to_incident(
    db: Database, scan_run: dict, finding: dict
) -> Optional[dict]:
    finding_id = _finding_id(
        scan_run["repo_url"], finding.get("rule_id"), finding.get("file") or "", finding.get("line"),
        scan_run.get("project_id"),
    )
    if await db.finding_has_incident(finding_id):
        return None
    severity = _normalize_severity(finding.get("severity"))
    description = finding.get("description") or finding.get("title") or ""
    title = f"{description or 'Security finding'} in {finding.get('file') or 'unknown file'}"
    incident = await db.insert("incidents", {
        "id": f"inc-{finding_id}",
        "title": title[:200],
        "description": description[:2000] or None,
        "severity": severity,
        "status": "open",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "affected_services": [scan_run.get("name") or scan_run["repo_url"]],
        "root_cause": finding.get("evidence"),
        "metadata": {
            "finding_id": finding_id,
            "scan_id": scan_run["id"],
            "repo_url": scan_run["repo_url"],
            "rule_id": finding.get("rule_id"),
            "file": finding.get("file"),
            "line": finding.get("line"),
        },
    })
    await db.mark_finding_promoted(finding_id)
    return incident


async def _finalize_scan(
    db: Database,
    scan_run: dict,
    findings: list[dict],
    file_hits: list[tuple[str, int]],
    texts: dict[str, str],
    llm_mode: bool = True,
) -> None:
    scan_id = scan_run["id"]
    repo_url = scan_run["repo_url"]
    project_id = scan_run.get("project_id")
    fresh = await db.get_scan_run(scan_id)
    if fresh is not None:
        scan_run = fresh
        repo_url = scan_run["repo_url"]
        project_id = scan_run.get("project_id")
    llm_status = "skipped"
    llm_findings: list[dict] = []
    if texts and llm_mode:
        selected = select_llm_files(file_hits, texts)
        if selected:
            llm_findings, llm_status = await asyncio.to_thread(llm_review, selected)
    merged = merge_findings(findings, llm_findings)
    report = score_report(merged)
    records = []
    for finding in merged:
        records.append({
            "id": _finding_id(repo_url, finding.get("rule_id"), finding.get("file") or "", finding.get("line"), project_id),
            "scan_id": scan_id,
            "severity": _normalize_severity(finding.get("severity")),
            "category": _category_of(finding),
            "rule_id": finding.get("rule_id"),
            "file": finding.get("file") or "",
            "line": finding.get("line"),
            "evidence": finding.get("evidence"),
            "description": finding.get("description") or finding.get("title") or "",
            "remediation": finding.get("remediation"),
            "confidence": finding.get("confidence") or "potential",
            "cwe": finding.get("cwe"),
            "owasp": finding.get("owasp"),
            "title": finding.get("title"),
            "impact": finding.get("impact"),
            "attack_scenario": finding.get("attack_scenario"),
            "verification": finding.get("verification"),
            "suggested_fix": finding.get("suggested_fix"),
            "source": finding.get("source") or ("llm" if finding.get("rule_id") is None else "rules"),
        })
    if records:
        ids = [r["id"] for r in records]
        rows = await db.pool.fetch("SELECT id FROM scan_findings WHERE id = ANY($1::text[])", ids)
        existing_ids = {row["id"] for row in rows}
        fresh = [r for r in records if r["id"] not in existing_ids]
        if fresh:
            try:
                await db.insert_batch("scan_findings", fresh)
            except Exception:
                for record in fresh:
                    try:
                        await db.insert("scan_findings", record)
                    except Exception:
                        pass
        for record in records:
            if record["id"] in existing_ids:
                try:
                    await db.update_by_id("scan_findings", record["id"], {
                        "severity": record["severity"],
                        "evidence": record["evidence"],
                        "description": record["description"],
                        "title": record["title"],
                        "confidence": record["confidence"],
                        "status": "open",
                    })
                except Exception:
                    pass
    for finding in merged:
        if finding.get("severity") in ("critical", "high"):
            await promote_finding_to_incident(db, scan_run, finding)
    metadata = dict(scan_run.get("metadata") or {})
    metadata.update({
        "scanned_files": sorted(texts.keys()),
        "sub_scores": report["sub_scores"],
        "counts": report["counts"],
        "rule_findings": findings,
        "llm_findings": llm_findings,
        "llm_status": llm_status,
    })
    summary = build_summary(scan_run, merged)
    await db.update_scan_status(
        scan_id,
        "completed",
        score=report["score"],
        grade=report["grade"],
        summary=summary,
        total_files=len(texts),
        metadata=metadata,
    )
    if project_id:
        await db.update_project_last_scan(project_id, scan_id)


async def _mark_scan_failed(db, scan_id: str, message: str, scanned_files: Optional[list[str]] = None) -> None:
    if scanned_files:
        await db.update_scan_status(
            scan_id,
            "failed",
            error=message,
            total_files=len(scanned_files),
            metadata={"scanned_files": sorted(set(scanned_files)), "partial_scanned_files": True},
        )
    else:
        await db.update_scan_status(scan_id, "failed", error=message)


async def run_scan(scan_id: str, repo_url: str) -> dict:
    db = await get_db()
    async with _scan_semaphore:
        try:
            url = validate_repo_url(repo_url)
        except ValueError as exc:
            await db.update_scan_status(scan_id, "failed", error=str(exc))
            return await db.get_scan_run(scan_id)
        scan = await db.get_scan_run(scan_id)
        try:
            await db.update_scan_status(scan_id, "running")
            scanned_files: list[str] = []
            repo_dir = await asyncio.to_thread(clone_repo, url, scan_id)
            try:
                findings, file_hits, texts, total_bytes = await asyncio.to_thread(scan_repo, repo_dir, scanned_files)
            finally:
                _rmtree_retry(repo_dir)
            await _finalize_scan(db, scan, findings, file_hits, texts)
        except ScanAbortError as exc:
            await _mark_scan_failed(db, scan_id, str(exc), scanned_files)
        except Exception as exc:
            await _mark_scan_failed(db, scan_id, f"scan failed: {exc}", scanned_files)
        return await db.get_scan_run(scan_id)


async def sweep_orphaned_scans() -> int:
    db = await get_db()
    rows = await db.pool.fetch("SELECT id FROM scan_runs WHERE status IN ('queued', 'running')")
    count = 0
    for row in rows:
        await db.update_scan_status(row["id"], "failed", error="server restarted mid-scan")
        count += 1
    return count


def _stage_meta(existing: dict, stage: str, status: str) -> dict:
    meta = dict(existing or {})
    stages = dict(meta.get("stages") or {})
    stages[stage] = {"status": status, "at": datetime.now(timezone.utc).isoformat()}
    meta["stages"] = stages
    return meta


async def _update_stage(db, scan_id: str, stage: str, status: str, extra: Optional[dict] = None) -> None:
    scan = await db.get_scan_run(scan_id)
    if not scan:
        return
    meta = _stage_meta(scan.get("metadata") or {}, stage, status)
    if extra:
        meta.update(extra)
    await db.update_scan_status(scan_id, scan["status"], metadata=meta)


async def run_security_scan(
    scan_id: str,
    source_type: str,
    source_ref: str,
    options: Optional[dict] = None,
) -> dict:
    db = await get_db()
    options = options or {}
    llm_mode = bool(options.get("llm_review", True))
    async with _scan_semaphore:
        try:
            if source_type == "repo":
                url = validate_repo_url(source_ref)
            elif source_type == "url":
                url = validate_live_url(source_ref)
            else:
                url = source_ref
        except ValueError as exc:
            await db.update_scan_status(scan_id, "failed", error=str(exc))
            return await db.get_scan_run(scan_id)
        scan = await db.get_scan_run(scan_id)
        try:
            await db.update_scan_status(scan_id, "running")
            findings: list[dict] = []
            texts: dict[str, str] = {}
            file_hits: list[tuple[str, int]] = []
            scanned_files: list[str] = []
            stack: dict = {}
            dependencies: list[dict] = []
            repo_dir: Optional[Path] = None
            zip_path: Optional[Path] = None

            if source_type in ("repo", "zip"):
                if source_type == "repo":
                    await _update_stage(db, scan_id, "acquire", "running")
                    repo_dir = await asyncio.to_thread(clone_repo, url, scan_id)
                else:
                    await _update_stage(db, scan_id, "acquire", "running")
                    zip_path = SCAN_TMP / f"{scan_id}.zip"
                    if not zip_path.exists():
                        raise ScanAbortError("uploaded zip file is missing")
                    repo_dir = SCAN_TMP / scan_id
                    await asyncio.to_thread(extract_zip, zip_path, repo_dir)
                try:
                    await _update_stage(db, scan_id, "detect", "running")
                    stack = await asyncio.to_thread(detect_stack, repo_dir)
                    await _update_stage(db, scan_id, "static", "running")
                    findings, file_hits, texts, _total_bytes = await asyncio.to_thread(scan_repo, repo_dir, scanned_files)
                    await _update_stage(db, scan_id, "dependencies", "running")
                    dependencies, dep_findings = await asyncio.to_thread(analyze_dependencies, repo_dir)
                    findings.extend(dep_findings)
                finally:
                    _rmtree_retry(repo_dir)
                    if zip_path is not None and zip_path.exists():
                        try:
                            zip_path.unlink()
                        except OSError:
                            pass
            elif source_type == "url":
                await _update_stage(db, scan_id, "dynamic", "running")
                findings = await asyncio.to_thread(run_url_checks, url)
            else:
                raise ScanAbortError(f"unsupported source type: {source_type}")

            await _update_stage(
                db, scan_id, "scoring", "running",
                extra={"tech_stack": stack, "dependencies": dependencies},
            )
            await _finalize_scan(db, scan, findings, file_hits, texts, llm_mode=llm_mode)
        except ScanAbortError as exc:
            await _mark_scan_failed(db, scan_id, str(exc), scanned_files)
        except Exception as exc:
            await _mark_scan_failed(db, scan_id, f"scan failed: {exc}", scanned_files)
        return await db.get_scan_run(scan_id)

