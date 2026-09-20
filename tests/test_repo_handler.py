from repo_handler import parse_github_url


def test_parse_basic_url():
    assert parse_github_url("https://github.com/owner/repo") == ("https://github.com/owner/repo.git", None)


def test_parse_strips_dot_git():
    assert parse_github_url("https://github.com/owner/repo.git") == ("https://github.com/owner/repo.git", None)


def test_parse_extracts_branch_from_tree_path():
    assert parse_github_url("https://github.com/owner/repo/tree/feature-x") == (
        "https://github.com/owner/repo.git",
        "feature-x",
    )


def test_parse_strips_trailing_path_without_branch():
    assert parse_github_url("https://github.com/owner/repo/blob/main/file.py") == (
        "https://github.com/owner/repo.git",
        None,
    )


def test_parse_tolerates_missing_scheme():
    assert parse_github_url("github.com/owner/repo") == ("https://github.com/owner/repo.git", None)


def test_parse_rejects_non_github_url():
    assert parse_github_url("https://gitlab.com/owner/repo") is None


def test_parse_rejects_non_repo_url():
    assert parse_github_url("https://github.com/owner") is None


def test_parse_rejects_plain_text():
    assert parse_github_url("hello there") is None
