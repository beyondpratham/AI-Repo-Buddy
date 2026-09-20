import os
import re
import shutil
import subprocess
import tempfile
 
 
GITHUB_URL_RE = re.compile(
    r"(?:https?://)?github\.com/([^/\s]+)/([^/\s?#]+)(?:/tree/([^/\s?#]+))?"
)


def parse_github_url(url):
    """
    Parse a GitHub repo URL, tolerating a missing scheme, trailing paths
    (besides /tree/<ref>), query strings, and a missing/extra .git suffix.

    Returns (clone_url, ref) where `ref` is the branch/tag named in a
    /tree/<ref> path segment, or None to use the repo's default branch.
    Returns None if the URL doesn't look like a GitHub repo URL.
    """
    url = url.strip()
    match = GITHUB_URL_RE.match(url)
    if not match:
        return None
    owner, repo, ref = match.group(1), match.group(2), match.group(3)
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}.git", ref


def clone_repo(url, base_dir=None, timeout=180):
    """
    Clone the given GitHub URL into a fresh temporary directory. If the URL
    points at a specific branch/tag (a /tree/<ref> path), that ref is
    cloned instead of the default branch.
    Returns (repo_path, repo_name). Raises ValueError/RuntimeError on failure.
    """
    parsed = parse_github_url(url)
    if not parsed:
        raise ValueError(
            "That doesn't look like a valid GitHub repository URL. "
            "Expected something like https://github.com/owner/repo"
        )
    clone_url, ref = parsed

    repo_name = clone_url[:-4].split("/")[-1]  # strip trailing ".git"

    if base_dir is None:
        base_dir = tempfile.mkdtemp(prefix="repo_setup_bot_")

    dest = os.path.join(base_dir, repo_name)
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)

    if shutil.which("git") is None:
        raise RuntimeError("git is not installed or not on PATH. Please install git first.")

    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [clone_url, dest]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        if ref:
            raise RuntimeError(
                f"git clone failed (branch/tag '{ref}' may not exist):\n{result.stderr.strip()}"
            )
        raise RuntimeError(f"git clone failed:\n{result.stderr.strip()}")

    return dest, repo_name
 
 
def cleanup_dir(path):
    """Best-effort recursive delete, never raises."""
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass