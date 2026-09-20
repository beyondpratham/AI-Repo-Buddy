 
import os
import re
 
from installer import get_venv_paths
from process_manager import StreamingProcess
from stack_detector import (
    find_python_entrypoint,
    find_package_json_dir,
    find_runnable_package_json_dirs,
    read_package_json,
    read_package_json_at,
    wrap_node_cwd,
)
 
PYTHON_TOOLS = ["python3", "python", "streamlit", "flask", "uvicorn", "gunicorn", "pytest"]
 
 
def _use_venv_binary(cmd, repo_path):
    """
    If the command's first token is a known Python-ecosystem tool and the
    project has an isolated venv, rewrite that token to the venv's copy of
    the binary so the run uses the freshly-installed dependencies.
    """
    _, bin_dir, _, _ = get_venv_paths(repo_path)
    if not os.path.isdir(bin_dir):
        return cmd
 
    tokens = cmd.strip().split()
    if not tokens:
        return cmd
 
    first = tokens[0]
    if first in PYTHON_TOOLS:
        candidate = os.path.join(bin_dir, first)
        if os.path.exists(candidate):
            tokens[0] = f'"{candidate}"'
            return " ".join(tokens)
    return cmd
 
 
def _python_command(repo_path, entry):
    """Build a 'python <entry>' command using the venv interpreter when present."""
    _, _, python_bin, _ = get_venv_paths(repo_path)
    if not os.path.exists(python_bin):
        import sys
        python_bin = sys.executable
    return f'"{python_bin}" {entry}'


def default_run_commands(repo_path, detected_stack):
    """
    Produce a list of best-guess run commands derived purely from the project's
    structure, for use when the README/docs give no explicit run instructions.

    Returns an ordered list of (command, source_label) candidates. The caller
    can attempt each in turn until one starts successfully. May be empty if the
    structure offers no reasonable guess.
    """
    candidates = []

    # ---- Python ----
    if "python" in detected_stack:
        entry = find_python_entrypoint(repo_path)
        if entry:
            base = os.path.basename(entry).lower()
            # Framework-aware defaults take priority over a plain interpreter run.
            if base == "manage.py":
                candidates.append((_python_command(repo_path, f"{entry} runserver"), "default: Django manage.py"))
            elif base in ("streamlit_app.py", "app.py"):
                candidates.append((_use_venv_binary(f"streamlit run {entry}", repo_path), "default: Streamlit app"))
            candidates.append((_python_command(repo_path, entry), "default: Python entrypoint"))

    # ---- Node ----
    if "node" in detected_stack:
        subdir = find_package_json_dir(repo_path) or ""
        base_dir = os.path.join(repo_path, subdir) if subdir else repo_path
        # Run from the folder holding package.json (e.g. `cd "frontend" && ...`).
        cd = f'cd "{subdir}" && ' if subdir else ""
        label_suffix = f" ({subdir})" if subdir else ""

        pkg = read_package_json(repo_path)
        if pkg and isinstance(pkg.get("scripts"), dict):
            scripts = pkg["scripts"]
            for key in ("start", "dev", "serve"):
                if key in scripts:
                    cmd = f"{cd}npm start" if key == "start" else f"{cd}npm run {key}"
                    candidates.append((cmd, f"default: package.json scripts{label_suffix}"))
        main_file = (pkg or {}).get("main") if isinstance(pkg, dict) else None
        if main_file and os.path.exists(os.path.join(base_dir, main_file)):
            candidates.append((f'{cd}node "{main_file}"', f"default: package.json main{label_suffix}"))
        for guess in ("index.js", "server.js", "app.js", "src/index.js"):
            if os.path.exists(os.path.join(base_dir, guess)):
                candidates.append((f'{cd}node "{guess}"', f"default: Node entrypoint{label_suffix}"))

    # ---- Go ----
    if "go" in detected_stack:
        candidates.append(("go run .", "default: Go module"))

    # ---- Rust ----
    if "rust" in detected_stack:
        candidates.append(("cargo run", "default: Cargo"))

    # ---- Ruby ----
    if "ruby" in detected_stack:
        for guess in ("main.rb", "app.rb", "server.rb"):
            if os.path.exists(os.path.join(repo_path, guess)):
                candidates.append((f"ruby {guess}", "default: Ruby entrypoint"))

    # ---- Java ----
    if "java_maven" in detected_stack:
        candidates.append(("mvn spring-boot:run", "default: Maven Spring Boot"))
        candidates.append(("mvn compile exec:java", "default: Maven exec"))
    if "java_gradle" in detected_stack:
        gradlew = "gradlew.bat" if os.name == "nt" else "./gradlew"
        gradle_cmd = gradlew if os.path.exists(os.path.join(repo_path, os.path.basename(gradlew))) else "gradle"
        candidates.append((f"{gradle_cmd} run", "default: Gradle"))

    # ---- Docker ----
    if "docker_compose" in detected_stack:
        candidates.append(("docker compose up", "default: Docker Compose"))

    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for cmd, label in candidates:
        if cmd and cmd not in seen:
            seen.add(cmd)
            unique.append((cmd, label))
    return unique


def determine_run_commands(repo_path, detected_stack, readme_run_cmds):
    """
    Build an ordered list of (command, source_label) candidates to try running
    the project.

    README/doc-derived commands are preferred (stack-matched ones first), then
    fall back to structure-based defaults from `default_run_commands` so that a
    project with no run instructions is still attempted at least once.
    """
    candidates = []

    # Folder that holds package.json (may be "frontend" etc.) so Node commands
    # from the README are executed in the right place.
    node_subdir = (find_package_json_dir(repo_path) or "") if "node" in detected_stack else ""

    # 1. Explicit run commands mentioned in the README/docs.
    if readme_run_cmds:
        matched, others = [], []
        for cmd in readme_run_cmds:
            lower = cmd.lower()
            if "python" in detected_stack and any(
                k in lower for k in ["streamlit run", "python ", "python3 ", "flask run", "uvicorn", "gunicorn"]
            ):
                matched.append((_use_venv_binary(cmd, repo_path), "README"))
            elif "node" in detected_stack and any(k in lower for k in ["npm ", "yarn ", "node ", "pnpm ", "npx "]):
                matched.append((wrap_node_cwd(cmd, node_subdir), "README"))
            else:
                # Apply both transforms; each is a no-op unless it matches.
                others.append((wrap_node_cwd(_use_venv_binary(cmd, repo_path), node_subdir), "README"))
        candidates.extend(matched)
        candidates.extend(others)

    # 2. Structure-based defaults (also used as fallbacks after README commands).
    candidates.extend(default_run_commands(repo_path, detected_stack))

    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for cmd, label in candidates:
        if cmd and cmd not in seen:
            seen.add(cmd)
            unique.append((cmd, label))
    return unique


def determine_run_command(repo_path, detected_stack, readme_run_cmds):
    """
    Pick the single best command to run the project.
    Returns (command, source_label) or (None, None) if nothing could be
    determined. Prefer `determine_run_commands` when you want to try multiple
    candidates.
    """
    candidates = determine_run_commands(repo_path, detected_stack, readme_run_cmds)
    if candidates:
        return candidates[0]
    return None, None


def _node_service_commands(repo_path, subdir):
    """Ordered run-command candidates for the Node package.json in `subdir`."""
    base_dir = os.path.join(repo_path, subdir) if subdir else repo_path
    cd = f'cd "{subdir}" && ' if subdir else ""
    suffix = f" ({subdir})" if subdir else ""

    cmds = []
    pkg = read_package_json_at(base_dir)
    if pkg and isinstance(pkg.get("scripts"), dict):
        scripts = pkg["scripts"]
        for key in ("start", "dev", "serve"):
            if key in scripts:
                cmd = f"{cd}npm start" if key == "start" else f"{cd}npm run {key}"
                cmds.append((cmd, f"default: package.json scripts{suffix}"))
    main_file = (pkg or {}).get("main") if isinstance(pkg, dict) else None
    if main_file and os.path.exists(os.path.join(base_dir, main_file)):
        cmds.append((f'{cd}node "{main_file}"', f"default: package.json main{suffix}"))
    for guess in ("index.js", "server.js", "app.js", "src/index.js"):
        if os.path.exists(os.path.join(base_dir, guess)):
            cmds.append((f'{cd}node "{guess}"', f"default: Node entrypoint{suffix}"))

    seen, unique = set(), []
    for cmd, label in cmds:
        if cmd not in seen:
            seen.add(cmd)
            unique.append((cmd, label))
    return unique


def discover_services(repo_path, detected_stack, readme_run_cmds):
    """
    Identify the independently runnable services in a repository so they can be
    started concurrently (e.g. a frontend and a backend).

    Returns a list of dicts: {"name": str, "commands": [(command, source), ...]}.
    Each service's `commands` is an ordered candidate list to try until one
    starts. When the repo is a single service, this returns one entry equivalent
    to `determine_run_commands` (README instructions included).
    """
    services = []

    # ---- Node services: one per package.json that has a runnable script. ----
    if "node" in detected_stack:
        node_dirs = find_runnable_package_json_dirs(repo_path)
        if not node_dirs:
            only = find_package_json_dir(repo_path)
            node_dirs = [only] if only is not None else []
        for subdir in node_dirs:
            cmds = _node_service_commands(repo_path, subdir)
            if cmds:
                name = os.path.basename(subdir) if subdir else "app"
                services.append({"name": name, "commands": cmds})

    # ---- Python service (e.g. an API backend) alongside a Node frontend. ----
    if "python" in detected_stack:
        py_cmds = default_run_commands(repo_path, {"python"})
        if py_cmds:
            services.append({"name": "python", "commands": py_cmds})

    # ---- Other single-process stacks. ----
    _added_java = False
    for stack_name, svc_name in (
        ("go", "go"), ("rust", "rust"), ("ruby", "ruby"),
        ("java_maven", "java"), ("java_gradle", "java"),
        ("docker_compose", "docker"),
    ):
        if stack_name not in detected_stack:
            continue
        if svc_name == "java" and _added_java:
            continue
        cmds = default_run_commands(repo_path, {stack_name})
        if cmds:
            services.append({"name": svc_name, "commands": cmds})
            if svc_name == "java":
                _added_java = True

    # De-duplicate services that resolved to the same primary command.
    seen_primary, unique = set(), []
    for svc in services:
        primary = svc["commands"][0][0]
        if primary not in seen_primary:
            seen_primary.add(primary)
            unique.append(svc)
    services = unique

    # Single service (or none): fall back to the README-aware single-command
    # planner so existing behavior (README instructions, retries) is preserved.
    if len(services) <= 1:
        cmds = determine_run_commands(repo_path, detected_stack, readme_run_cmds)
        if cmds:
            name = services[0]["name"] if services else "app"
            return [{"name": name, "commands": cmds}]
        return []

    return services


def start_run(command, repo_path):
    """Start the run command in the background and return the StreamingProcess."""
    return StreamingProcess(command, cwd=repo_path).start()
 
 
def detect_port_from_logs(lines):
    port_pattern = re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{2,5})")
    for line in lines:
        m = port_pattern.search(line)
        if m:
            return m.group(1)
    return None


# Directories that are never worth searching when hunting for a missing file.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode"}

# Patterns that indicate a run failed because a file/module path couldn't be found.
_MISSING_PATH_PATTERNS = [
    re.compile(r"can't open file '([^']+)'"),
    re.compile(r"File does not exist:\s*([^\s]+)"),
    re.compile(r"Cannot find module '([^']+)'"),
    re.compile(r"No such file or directory:?\s*'?([^'\n\"]+?)'?\s*$", re.MULTILINE),
]


def _extract_missing_path(log_text):
    """Pull the first missing file/module path referenced in an error log."""
    for pattern in _MISSING_PATH_PATTERNS:
        match = pattern.search(log_text or "")
        if match:
            return match.group(1).strip().strip("'\"")
    return None


def _find_file_in_repo(repo_path, filename):
    """
    Search the repo tree for a file matching the given name (by basename).
    Returns the shallowest match relative to repo_path, or None.
    """
    basename = os.path.basename(filename)
    if not basename:
        return None

    matches = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        if basename in files:
            full = os.path.join(root, basename)
            matches.append(os.path.relpath(full, repo_path))

    if not matches:
        return None

    # Prefer the match closest to the repo root.
    matches.sort(key=lambda p: len(p.split(os.sep)))
    return matches[0]


def resolve_run_command(command, repo_path, log_text):
    """
    Attempt to repair a run command that failed because a referenced file/path
    could not be found. Locates the missing file elsewhere in the repo and
    rewrites the command to point at it.

    Returns a corrected command string, or None if no fix could be determined.
    """
    missing = _extract_missing_path(log_text)
    if not missing:
        return None

    relative = _find_file_in_repo(repo_path, missing)
    if not relative:
        return None

    basename = os.path.basename(missing)
    tokens = command.split()
    new_tokens = []
    replaced = False
    for token in tokens:
        stripped = token.strip("'\"")
        if not replaced and os.path.basename(stripped) == basename:
            new_tokens.append(f'"{relative}"' if " " in relative else relative)
            replaced = True
        else:
            new_tokens.append(token)

    if not replaced:
        return None

    new_command = " ".join(new_tokens)
    return new_command if new_command != command else None