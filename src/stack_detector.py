
import json
import os
 
STACK_SIGNATURES = {
    "python": ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"],
    "node": ["package.json"],
    "go": ["go.mod"],
    "ruby": ["Gemfile"],
    "java_maven": ["pom.xml"],
    "java_gradle": ["build.gradle", "build.gradle.kts"],
    "rust": ["Cargo.toml"],
    "docker": ["Dockerfile"],
    "docker_compose": ["docker-compose.yml", "docker-compose.yaml"],
}
 
 
def detect_stack(repo_path):
    """Return {stack_name: [matched files]} for every stack detected at repo root."""
    detected = {}
    try:
        entries = os.listdir(repo_path)
    except FileNotFoundError:
        return detected
    for stack, files in STACK_SIGNATURES.items():
        found = [f for f in files if f in entries]
        if found:
            detected[stack] = found
    # A Node project often lives in a subfolder (e.g. frontend/, client/) rather
    # than the repo root. If we didn't spot package.json at the root, look deeper.
    if "node" not in detected and find_package_json(repo_path):
        detected["node"] = ["package.json"]
    return detected
 
 
def find_readme(repo_path):
    """Case-insensitive search for a README file in the repo root."""
    candidates = ["README.md", "README.rst", "README.txt", "README"]
    try:
        entries = {f.lower(): f for f in os.listdir(repo_path)}
    except FileNotFoundError:
        return None
    for c in candidates:
        if c.lower() in entries:
            return os.path.join(repo_path, entries[c.lower()])
    return None


# Doc filenames (besides README) that commonly hold setup / install / run steps.
SETUP_DOC_KEYWORDS = [
    "install", "setup", "set-up", "getting-started", "getting_started",
    "quickstart", "quick-start", "usage", "run", "running", "build",
    "development", "develop", "contributing", "deploy", "docs",
]

_DOC_EXTENSIONS = (".md", ".rst", ".txt")


def find_setup_docs(repo_path, max_files=8):
    """
    Collect setup/documentation files that may contain install or run steps.
    Returns a list of absolute paths: the README first (if any), followed by
    other relevant docs at the repo root and inside a top-level docs/ folder.
    """
    found = []
    seen = set()

    def add(path):
        real = os.path.normpath(path)
        low = real.lower()
        if low not in seen and os.path.isfile(real):
            seen.add(low)
            found.append(real)

    # README always comes first when present.
    readme = find_readme(repo_path)
    if readme:
        add(readme)

    # Root-level docs whose name hints at setup/usage.
    try:
        root_entries = os.listdir(repo_path)
    except FileNotFoundError:
        return found
    for name in sorted(root_entries):
        full = os.path.join(repo_path, name)
        if not os.path.isfile(full) or not name.lower().endswith(_DOC_EXTENSIONS):
            continue
        if any(k in name.lower() for k in SETUP_DOC_KEYWORDS):
            add(full)

    # A top-level docs/ folder often holds setup guides.
    docs_dir = os.path.join(repo_path, "docs")
    if os.path.isdir(docs_dir):
        for root, _dirs, files in os.walk(docs_dir):
            for name in sorted(files):
                if not name.lower().endswith(_DOC_EXTENSIONS):
                    continue
                base = name.lower()
                if base.startswith("readme") or any(k in base for k in SETUP_DOC_KEYWORDS):
                    add(os.path.join(root, name))
            if len(found) >= max_files:
                break

    return found[:max_files]
 
 
# Directories not worth searching when hunting for a package.json in a monorepo.
_NODE_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".venv_bot", "venv",
    "env", ".idea", ".vscode", "dist", "build", "out", "coverage",
}

# Subfolder names that commonly hold a front-end / Node app in a larger repo.
_FRONTEND_HINT_DIRS = ["frontend", "client", "web", "webapp", "ui", "app", "www", "site", "public"]


# Scripts in package.json that indicate the app can actually be started.
_RUNNABLE_SCRIPT_KEYS = ("start", "dev", "serve", "develop")


def _pkg_has_runnable_script(pkg_path):
    """True if the package.json declares a start/dev/serve-style script."""
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    scripts = data.get("scripts")
    return isinstance(scripts, dict) and any(k in scripts for k in _RUNNABLE_SCRIPT_KEYS)


def _iter_package_jsons(repo_path):
    """Yield absolute paths to every package.json in the tree (skipping junk dirs)."""
    found = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _NODE_SKIP_DIRS]
        if "package.json" in files:
            found.append(os.path.join(root, "package.json"))
    return found


def find_package_json(repo_path):
    """
    Locate the most relevant package.json for the repo, searching every folder
    (not just the root).

    When several exist, the best one is chosen by preferring, in order:
      1. A package.json that declares a runnable script (start/dev/serve). This
         lets us skip a bare root placeholder in favour of, e.g., frontend/.
      2. The shallowest location (closest to the repo root).
      3. A folder whose name looks like a front-end app (frontend/, client/, ...).

    Returns an absolute path, or None if no package.json exists anywhere.
    """
    candidates = _iter_package_jsons(repo_path)
    if not candidates:
        return None

    def score(path):
        parent = os.path.dirname(path)
        rel = os.path.relpath(parent, repo_path)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dir_name = os.path.basename(parent).lower()
        has_script = _pkg_has_runnable_script(path)
        is_frontend = dir_name in _FRONTEND_HINT_DIRS
        # Higher tuple wins: runnable first, then shallower, then front-end-named.
        return (has_script, -depth, is_frontend)

    return max(candidates, key=score)


def find_package_json_dir(repo_path):
    """
    Return the directory (relative to repo_path) that holds the relevant
    package.json. Returns "" when it lives at the repo root, or None if there
    is no package.json anywhere.
    """
    pkg = find_package_json(repo_path)
    if not pkg:
        return None
    rel = os.path.relpath(os.path.dirname(pkg), repo_path)
    return "" if rel == "." else rel


def read_package_json(repo_path):
    path = find_package_json(repo_path)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_package_json_at(dir_path):
    """Read the package.json located directly in dir_path (no searching)."""
    path = os.path.join(dir_path, "package.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_runnable_package_json_dirs(repo_path):
    """
    Return the relative directories of every package.json in the repo that
    declares a runnable script (start/dev/serve). This is what lets us run a
    frontend/ and a backend/ as two separate services at the same time.

    Results are ordered shallowest-first, with front-end-named folders taking
    precedence at the same depth. Returns [] if none qualify.
    """
    dirs = []
    for pkg in _iter_package_jsons(repo_path):
        if not _pkg_has_runnable_script(pkg):
            continue
        rel = os.path.relpath(os.path.dirname(pkg), repo_path)
        dirs.append("" if rel == "." else rel)

    def sort_key(d):
        depth = 0 if d == "" else d.count(os.sep) + 1
        is_frontend = os.path.basename(d).lower() in _FRONTEND_HINT_DIRS
        return (depth, 0 if is_frontend else 1, d)

    dirs.sort(key=sort_key)
    return dirs


# First tokens that mark a command as a Node/JS command which must run from the
# directory that actually contains package.json (e.g. a frontend/ subfolder).
_NODE_CMD_TOOLS = {
    "npm", "yarn", "pnpm", "npx", "node", "bun",
    "vite", "next", "react-scripts", "ng", "nuxt", "webpack",
}


def wrap_node_cwd(cmd, subdir):
    """
    Prefix a Node command with `cd "<subdir>" &&` so it runs from the directory
    holding package.json. No-op when there is no subfolder or the command isn't
    a recognized Node command.
    """
    if not subdir:
        return cmd
    stripped = cmd.strip()
    if not stripped:
        return cmd
    first = stripped.split()[0].strip('"').strip("'")
    if os.path.basename(first).lower() in _NODE_CMD_TOOLS:
        return f'cd "{subdir}" && {cmd}'
    return cmd
 
 
def find_python_entrypoint(repo_path):
    """Guess the most likely Python file to run, in priority order."""
    priorities = ["app.py", "main.py", "manage.py", "run.py", "server.py", "streamlit_app.py"]
    try:
        entries = os.listdir(repo_path)
    except FileNotFoundError:
        return None
    for p in priorities:
        if p in entries:
            return p
    for f in sorted(entries):
        if f.endswith(".py"):
            return f
    return None