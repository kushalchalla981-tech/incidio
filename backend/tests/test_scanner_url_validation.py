import pytest

from app.services.scanner import validate_repo_url

VALID_URLS = [
    "https://github.com/org/repo",
    "https://github.com/org/repo.git",
    "https://github.com/org/group/repo",
    "https://gitlab.com/group/project",
    "https://gitlab.com/group/subgroup/project.git",
    "https://bitbucket.org/team/repo",
    "https://bitbucket.org/team/repo.git",
    "https://github.com/org/repo/tree/main/src",
    "  https://github.com/org/repo  ",
]


@pytest.mark.parametrize("url", VALID_URLS)
def test_valid_repo_urls_accepted(url):
    assert validate_repo_url(url) == url.strip()


INVALID_URLS = [
    "https://github.com./org/repo",
    "https://evil.example.com/org/repo",
    "https://github.com.evil.example.com/org/repo",
    "https://user:pass@github.com/org/repo",
    "https://github.com/org/../repo",
    "https://github.com/org/%2e%2e/repo",
    "https://github.com/%2E%2E/repo",
    "file:///etc/passwd",
    "ssh://git@github.com/org/repo.git",
    "http://github.com/org/repo",
    "git://github.com/org/repo.git",
    "-https://github.com/org/repo",
    "",
    "   ",
    "https://unknownhost.example/org/repo",
    "https://github.com/" + ("a" * 2100),
]


@pytest.mark.parametrize("url", INVALID_URLS)
def test_invalid_repo_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_repo_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/org/%2e%2e/repo",
        "https://github.com/%2E%2E/repo",
        "https://github.com/org/%2e%2e%2fsecret",
    ],
)
def test_url_encoded_dotdot_is_decoded_and_rejected(url):
    """%2e%2e must be decoded before traversal checks so it cannot bypass them."""
    with pytest.raises(ValueError):
        validate_repo_url(url)


def test_url_encoded_dotdot_error_is_about_path():
    with pytest.raises(ValueError, match=r"\.\."):
        validate_repo_url("https://github.com/org/%2e%2e/repo")


def test_url_with_trailing_dot_host_rejected():
    with pytest.raises(ValueError, match="must not end with"):
        validate_repo_url("https://github.com./org/repo")


def test_credentials_rejected_even_on_allowed_host():
    with pytest.raises(ValueError, match="credentials"):
        validate_repo_url("https://user:pass@github.com/org/repo")


def test_unknown_host_rejected():
    with pytest.raises(ValueError, match="host not allowed"):
        validate_repo_url("https://gitlab.example.com/org/repo")


def test_url_longer_than_2048_chars_rejected():
    with pytest.raises(ValueError, match="too long"):
        validate_repo_url("https://github.com/" + ("a" * 2100))


def test_empty_url_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_repo_url("")


def test_leading_dash_rejected():
    with pytest.raises(ValueError, match="start with"):
        validate_repo_url("-https://github.com/org/repo")


def test_scheme_must_be_https():
    for url in ("http://github.com/org/repo", "ssh://git@github.com/org/repo.git", "git://github.com/org/repo.git", "file:///etc/passwd"):
        with pytest.raises(ValueError, match="https"):
            validate_repo_url(url)
