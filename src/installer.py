 
import os
import shutil
import sys

from stack_detector import find_package_json_dir, wrap_node_cwd
 
VENV_DIRNAME = ".venv_bot"
 
 
def get_venv_paths(repo_path):
    venv_path = os.path.join(repo_path, VENV_DIRNAME)
    if os.name == "nt":
        bin_dir = os.path.join(venv_path, "Scripts")
        python_bin = os.path.join(bin_dir, "python.exe")
        pip_bin = os.path.join(bin_dir, "pip.exe")
    else:
        bin_dir = os.path.join(venv_path, "bin")
        python_bin = os.path.join(bin_dir, "python")
        pip_bin = os.path.join(bin_dir, "pip")
    return venv_path, bin_dir, python_bin, pip_bin
 
 
def get_python_bin(repo_path):
    """Return the venv's python if it exists, otherwise the system interpreter."""
    _, _, python_bin, _ = get_venv_paths(repo_path)
    if os.path.exists(python_bin):
        return python_bin
    return sys.executable
 
 
def build_install_plan(repo_path, detected_stack, readme_install_cmds):
    """Return an ordered list of (label, command) tuples to execute."""
    plan = []
 
    if "python" in detected_stack:
        files = detected_stack["python"]
        venv_path, bin_dir, _, pip_bin = get_venv_paths(repo_path)
        plan.append(("Create Python virtual environment", f'"{sys.executable}" -m venv "{venv_path}"'))
        plan.append(("Upgrade pip", f'"{pip_bin}" install --upgrade pip'))

        if "requirements.txt" in files:
            plan.append(("Install Python dependencies (requirements.txt)",
                         f'"{pip_bin}" install -r requirements.txt'))
        elif "Pipfile" in files:
            pipenv_bin = os.path.join(bin_dir, "pipenv.exe" if os.name == "nt" else "pipenv")
            plan.append(("Install pipenv", f'"{pip_bin}" install pipenv'))
            plan.append(("Install Python dependencies (pipenv)",
                         f'"{pipenv_bin}" install --system --deploy'))
        elif "pyproject.toml" in files:
            plan.append(("Install Python project (pyproject.toml)", f'"{pip_bin}" install .'))
        elif "setup.py" in files:
            plan.append(("Install Python project (setup.py)", f'"{pip_bin}" install .'))
 
    if "node" in detected_stack:
        subdir = find_package_json_dir(repo_path) or ""
        lock_dir = os.path.join(repo_path, subdir) if subdir else repo_path
        label_suffix = f" ({subdir})" if subdir else ""
        cd = f'cd "{subdir}" && ' if subdir else ""
        use_yarn = os.path.exists(os.path.join(lock_dir, "yarn.lock")) and shutil.which("yarn")
        if use_yarn:
            plan.append((f"Install Node dependencies (yarn){label_suffix}", f"{cd}yarn install"))
        else:
            plan.append((f"Install Node dependencies (npm){label_suffix}", f"{cd}npm install"))
 
    if "go" in detected_stack:
        plan.append(("Download Go modules", "go mod download"))
 
    if "ruby" in detected_stack:
        plan.append(("Install Ruby gems", "bundle install"))
 
    if "rust" in detected_stack:
        plan.append(("Build Rust project", "cargo build"))
 
    if "java_maven" in detected_stack:
        plan.append(("Build Maven project", "mvn install -DskipTests"))
 
    if "java_gradle" in detected_stack:
        gradlew = "./gradlew" if os.path.exists(os.path.join(repo_path, "gradlew")) else "gradle"
        plan.append(("Build Gradle project", f"{gradlew} build -x test"))
 
    # Append any install-looking commands the README mentioned that aren't
    # already covered by the plan above (dependency-file-driven installs
    # are generally more reliable, so those come first).
    node_subdir = (find_package_json_dir(repo_path) or "") if "node" in detected_stack else ""
    existing_lower = {c.lower() for _, c in plan}
    for cmd in readme_install_cmds:
        wrapped = wrap_node_cwd(cmd, node_subdir)
        if wrapped.lower() not in existing_lower:
            plan.append((f"README instruction: {cmd}", wrapped))
            existing_lower.add(wrapped.lower())

    return plan