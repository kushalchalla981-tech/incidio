import socket
import ssl
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config import settings

TIMEOUT = settings.URL_CHECK_TIMEOUT

SECURITY_HEADER_CHECKS = [
    ("content-security-policy", "CSP", "medium",
     "No Content-Security-Policy header found. The application cannot constrain the sources of scripts and other content.",
     "Add a Content-Security-Policy header (e.g. default-src 'self').",
     "CWE-1021", "A05:2021"),
    ("strict-transport-security", "HSTS", "medium",
     "No Strict-Transport-Security header. Browsers may load the site over plain HTTP after an HTTPS visit.",
     "Add Strict-Transport-Security: max-age=31536000; includeSubDomains.",
     "CWE-319", "A02:2021"),
    ("x-content-type-options", "X-Content-Type-Options", "low",
     "No X-Content-Type-Options header, so MIME-sniffing is possible.",
     "Add X-Content-Type-Options: nosniff.",
     "CWE-16", "A05:2021"),
    ("x-frame-options", "X-Frame-Options", "low",
     "No X-Frame-Options header and no CSP frame-ancestors directive; the page may be embeddable in an iframe (clickjacking).",
     "Add X-Frame-Options: DENY (or SAMEORIGIN) or a CSP frame-ancestors directive.",
     "CWE-1021", "A05:2021"),
    ("referrer-policy", "Referrer-Policy", "informational",
     "No Referrer-Policy header; the page may leak the full URL in the Referer header.",
     "Add Referrer-Policy: strict-origin-when-cross-origin.",
     "CWE-200", "A01:2021"),
]

EXPOSED_PATHS = [
    ("/.env", "env-config", "critical",
     "The .env file is publicly accessible. It typically contains secrets such as API keys and database credentials.",
     "Remove the file from the web root and store secrets in a secret manager.",
     "CWE-200", "A05:2021"),
    ("/.git/config", "git-config", "critical",
     "The .git/config file is publicly accessible, exposing repository metadata and possibly remote URLs with credentials.",
     "Block .git paths in the web server configuration.",
     "CWE-200", "A05:2021"),
    ("/.git/HEAD", "git-head", "high",
     "A .git directory is exposed, allowing attackers to reconstruct the full repository history.",
     "Block .git paths in the web server configuration.",
     "CWE-200", "A05:2021"),
    ("/actuator/env", "actuator-env", "high",
     "Spring Boot Actuator env endpoint is exposed, potentially leaking configuration and secrets.",
     "Restrict or disable actuator endpoints in production.",
     "CWE-200", "A05:2021"),
    ("/actuator", "actuator", "medium",
     "Spring Boot Actuator endpoints are exposed without protection.",
     "Restrict or disable actuator endpoints in production.",
     "CWE-200", "A05:2021"),
    ("/admin", "admin-console", "medium",
     "An administration path responds without authentication or with a generic response; verify it is protected.",
     "Ensure admin endpoints enforce authentication and authorization.",
     "CWE-306", "A01:2021"),
    ("/health", "health-endpoint", "informational",
     "A health endpoint is publicly reachable. Low risk by itself, but may reveal internal service names.",
     "Consider restricting health endpoints to internal networks.",
     "CWE-200", "A01:2021"),
    ("/robots.txt", "robots", "informational",
     "robots.txt exists and may reveal private or disallowed paths.",
     "Review robots.txt and remove paths that reveal internal structure.",
     "CWE-200", "A01:2021"),
]


def _resolve_host(host: str):
    try:
        return socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return []


def _is_private_ip(ip: str) -> bool:
    try:
        from ipaddress import ip_address
        addr = ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved
    except ValueError:
        return True


def validate_live_url(url: str) -> str:
    stripped = url.strip()
    if not stripped or len(stripped) > 2048:
        raise ValueError("URL is empty or too long")
    if stripped.startswith("-"):
        raise ValueError("URL must not start with '-'")
    parsed = urlparse(stripped)
    if parsed.scheme != "https":
        raise ValueError("URL must use https")
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL must include a host")
    if ".." in parsed.path:
        raise ValueError("URL path must not contain '..'")
    if not settings.URL_ALLOW_PRIVATE_IP:
        for entry in _resolve_host(host):
            ip = entry[4][0]
            if _is_private_ip(ip):
                raise ValueError(f"URL host resolves to a non-public address: {ip}")
    return stripped


def _check_cookies(headers: httpx.Headers, base: str) -> list[dict]:
    findings = []
    cookies = headers.get_list("set-cookie")
    for cookie in cookies:
        name = cookie.split("=", 1)[0].strip()
        low = cookie.lower()
        flags = {"secure": "Secure" in cookie, "httponly": "httponly" in low, "samesite": "samesite" in low}
        if not flags["secure"]:
            findings.append({
                "rule_id": "URL_COOKIE_NO_SECURE", "severity": "high", "category": "config",
                "file": base, "line": None,
                "evidence": f"cookie '{name}' without the Secure flag",
                "title": f"Cookie '{name}' missing Secure flag",
                "description": f"Cookie '{name}' is set without the Secure attribute and could be sent over plain HTTP.",
                "remediation": "Add the Secure attribute (and consider SameSite + HttpOnly).",
                "confidence": "confirmed", "cwe": "CWE-614", "owasp": "A05:2021",
                "impact": "Session tokens transmitted over HTTP can be intercepted by network attackers.",
                "attack_scenario": "An attacker on the same network forces or observes plain HTTP traffic to steal the cookie.",
                "verification": "Inspect Set-Cookie headers in the browser devtools or with curl -v.",
                "source": "url_check",
            })
        if not flags["httponly"]:
            findings.append({
                "rule_id": "URL_COOKIE_NO_HTTPONLY", "severity": "medium", "category": "config",
                "file": base, "line": None,
                "evidence": f"cookie '{name}' without the HttpOnly flag",
                "title": f"Cookie '{name}' missing HttpOnly flag",
                "description": f"Cookie '{name}' lacks HttpOnly, so client-side JavaScript can read it.",
                "remediation": "Add the HttpOnly attribute to session cookies.",
                "confidence": "confirmed", "cwe": "CWE-1004", "owasp": "A05:2021",
                "impact": "If XSS exists anywhere, attackers can steal the cookie directly.",
                "attack_scenario": "An attacker finds an XSS sink and exfiltrates the cookie via document.cookie.",
                "verification": "Inspect Set-Cookie headers; check for HttpOnly.",
                "source": "url_check",
            })
    return findings


def _check_endpoint(base: str, path: str, client: httpx.Client) -> Optional[dict]:
    url = base.rstrip("/") + path
    try:
        resp = client.get(url)
    except (httpx.TimeoutException, httpx.RequestError):
        return None
    rule = EXPOSED_PATHS_MAP.get(path)
    if rule is None:
        return None
    key, severity, desc, remed, cwe, owasp = rule
    rule_id = f"URL_PATH_{key.replace('-', '_').upper()}"
    if resp.status_code == 404:
        return None
    if resp.status_code in (401, 403):
        return {
            "rule_id": rule_id,
            "severity": "informational", "category": "url",
            "file": path, "line": None,
            "evidence": f"{path} -> HTTP {resp.status_code} (protected)",
            "title": f"{path} exists but is protected",
            "description": f"{path} responds with HTTP {resp.status_code}; the endpoint exists but appears protected.",
            "remediation": "Confirm access control and audit logs cover this endpoint.",
            "confidence": "strong", "cwe": cwe, "owasp": owasp,
            "impact": "None if protection is enforced correctly.",
            "attack_scenario": "An attacker probes the path and is rejected; monitor for further probing.",
            "verification": "Verify the 401/403 is enforced by the application, not a CDN.",
            "source": "url_check",
        }
    body = resp.text[:400]
    confirmed = False
    if path == "/.env" and "=" in body and "\n" in body:
        confirmed = True
    elif path == "/.git/config" and "[core]" in body:
        confirmed = True
    elif path == "/.git/HEAD" and "ref:" in body:
        confirmed = True
    if severity in ("informational", "low"):
        severity_out = severity
    elif confirmed:
        severity_out = severity
    else:
        severity_out = "high" if severity == "critical" else "medium"
    return {
        "rule_id": rule_id,
        "severity": severity_out,
        "category": "url",
        "file": path, "line": None,
        "evidence": f"{path} -> HTTP {resp.status_code} (content matches: {confirmed})",
        "title": f"{path} is publicly accessible",
        "description": desc,
        "remediation": remed,
        "confidence": "confirmed" if confirmed else "potential",
        "cwe": cwe, "owasp": owasp,
        "impact": f"Public access to {path} can disclose sensitive information.",
        "attack_scenario": "An attacker simply requests the path over HTTPS and reads the response.",
        "verification": f"Run: curl -s -o /dev/null -w '%{{http_code}}' {base}{path}",
        "source": "url_check",
    }


EXPOSED_PATHS_MAP = {item[0]: item[1:] for item in EXPOSED_PATHS}


def run_url_checks(url: str) -> list[dict]:
    findings: list[dict] = []
    base = url.rstrip("/")
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True, verify=True,
                          headers={"User-Agent": "VibeCodedSecurityChecker/1.0 (non-destructive)"}) as client:
            resp = client.get(base)
            if resp.status_code >= 400:
                return [{
                    "rule_id": "URL_UNREACHABLE", "severity": "medium", "category": "url",
                    "file": base, "line": None,
                    "evidence": f"GET {base} -> HTTP {resp.status_code}",
                    "title": "Live URL unreachable",
                    "description": f"The live URL returned HTTP {resp.status_code}; checks could not run.",
                    "remediation": "Verify the URL is correct and the site is up.",
                    "confidence": "confirmed", "cwe": "CWE-16", "owasp": "A05:2021",
                    "impact": "No security assessment possible for an unreachable site.",
                    "attack_scenario": "—", "verification": "Retry the request manually.",
                    "source": "url_check",
                }]
            final_url = str(resp.url)
            headers = resp.headers
            for header, label, severity, desc, remed, cwe, owasp in SECURITY_HEADER_CHECKS:
                if header not in headers:
                    findings.append({
                        "rule_id": f"URL_HEADER_{label.upper()}", "severity": severity,
                        "category": "url", "file": base, "line": None,
                        "evidence": f"missing {header} on {final_url}",
                        "title": f"Missing security header: {label}",
                        "description": desc, "remediation": remed,
                        "confidence": "confirmed", "cwe": cwe, "owasp": owasp,
                        "impact": "Weakens browser-side security protections.",
                        "attack_scenario": "Attackers exploit the absence of the header to mount clickjacking, MIME-sniffing, mixed-content or data-theft attacks.",
                        "verification": f"Run: curl -sI {base} | grep -i {header}",
                        "source": "url_check",
                    })
            server = headers.get("server")
            if server:
                findings.append({
                    "rule_id": "URL_INFO_SERVER_HEADER", "severity": "informational",
                    "category": "url", "file": base, "line": None,
                    "evidence": f"Server: {server[:120]}",
                    "title": "Server header reveals implementation details",
                    "description": "The Server header exposes the web server software and version.",
                    "remediation": "Hide or strip the Server header (and X-Powered-By).",
                    "confidence": "confirmed", "cwe": "CWE-200", "owasp": "A05:2021",
                    "impact": "Helps attackers pick targeted exploits.",
                    "attack_scenario": "An attacker fingerprints the stack to choose known CVEs.",
                    "verification": f"Run: curl -sI {base} | grep -i server",
                    "source": "url_check",
                })
            findings.extend(_check_cookies(headers, base))
    except (httpx.TimeoutException, httpx.RequestError, ssl.SSLError) as exc:
        return [{
            "rule_id": "URL_REQUEST_FAILED", "severity": "medium", "category": "url",
            "file": base, "line": None,
            "evidence": f"GET {base} failed: {type(exc).__name__}",
            "title": "Live URL check failed",
            "description": f"Request to the live URL failed ({type(exc).__name__}); HTTPS/TLS could not be verified.",
            "remediation": "Ensure the site serves a valid TLS certificate and responds over HTTPS.",
            "confidence": "confirmed", "cwe": "CWE-295", "owasp": "A05:2021",
            "impact": "Could indicate TLS problems (e.g., self-signed or expired certificates).",
            "attack_scenario": "—", "verification": "Open the URL in a browser and check the padlock.",
            "source": "url_check",
        }]

    try:
        no_redirect = httpx.Client(timeout=TIMEOUT, follow_redirects=False, verify=False)
        plain = no_redirect.get(base.replace("https://", "http://", 1))
        no_redirect.close()
        if plain.status_code == 200:
            findings.append({
                "rule_id": "URL_NO_HTTPS_REDIRECT", "severity": "medium", "category": "url",
                "file": base, "line": None,
                "evidence": f"http:// served HTTP {plain.status_code} without redirecting to https",
                "title": "Site serves content over plain HTTP",
                "description": "The site does not redirect HTTP traffic to HTTPS; users can be downgraded to plain HTTP.",
                "remediation": "Redirect all HTTP requests to HTTPS (301) and enable HSTS.",
                "confidence": "confirmed", "cwe": "CWE-319", "owasp": "A02:2021",
                "impact": "Traffic — including credentials — can be intercepted in transit.",
                "attack_scenario": "An attacker performs a man-in-the-middle or SSL-strip attack on an unsecured network.",
                "verification": "Run: curl -sI http://{host} and inspect the status/location.",
                "source": "url_check",
            })
    except (httpx.TimeoutException, httpx.RequestError):
        pass

    with httpx.Client(timeout=TIMEOUT, follow_redirects=False, verify=True,
                      headers={"User-Agent": "VibeCodedSecurityChecker/1.0 (non-destructive)"}) as client:
        for path, *_rest in EXPOSED_PATHS:
            finding = _check_endpoint(base, path, client)
            if finding:
                findings.append(finding)

    return findings