
import os
import re
 
CODE_FENCE_RE = re.compile(r"```(?:\w*\n)?(.*?)```", re.DOTALL)
 
INSTALL_KEYWORDS = [
    "pip install", "pip3 install", "conda install", "conda env create",
    "poetry install", "npm install", "npm ci", "yarn install", "yarn add",
    "bundle install", "go mod download", "go get", "cargo build",
    "mvn install", "mvn package", "gradle build", "./gradlew build",
    "apt-get install", "apt install", "brew install", "pipenv install",
]
 
RUN_KEYWORDS = [
    "streamlit run", "python manage.py runserver", "python app.py",
    "python main.py", "python3 app.py", "python3 main.py", "flask run",
    "uvicorn", "gunicorn", "npm start", "npm run dev", "npm run start",
    "yarn start", "yarn dev", "node ", "go run", "cargo run",
    "docker-compose up", "docker compose up", "make run", "./gradlew run",
    "rails server", "rails s",
]
 
 
def _clean_line(line):
    line = line.strip()
    line = re.sub(r"^\$\s*", "", line)
    line = re.sub(r"^>\s*", "", line)
    return line
 
 
def extract_commands(readme_text):
    """Return (install_commands, run_commands) as ordered, deduplicated lists."""
    install_cmds = []
    run_cmds = []
    seen = set()
 
    blocks = CODE_FENCE_RE.findall(readme_text)
    sources = blocks if blocks else [readme_text]
 
    for block in sources:
        for raw_line in block.splitlines():
            line = _clean_line(raw_line)
            if not line or line.startswith("#"):
                continue
            if line in seen:
                continue
            lower = line.lower()
            if any(k in lower for k in INSTALL_KEYWORDS):
                install_cmds.append(line)
                seen.add(line)
            elif any(k in lower for k in RUN_KEYWORDS):
                run_cmds.append(line)
                seen.add(line)
 
    return install_cmds, run_cmds
 
 
def load_readme(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def load_docs(paths):
    """
    Load and concatenate several doc files into one text blob. Each file's
    content is prefixed with a header naming its source so downstream parsing
    (rule-based or AI) can tell the sections apart.
    """
    parts = []
    for p in paths:
        text = load_readme(p)
        if text.strip():
            parts.append(f"===== FILE: {os.path.basename(p)} =====\n{text}")
    return "\n\n".join(parts)