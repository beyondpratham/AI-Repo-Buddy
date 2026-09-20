# AI Repo Buddy

**Paste a GitHub URL, get a running app.** AI Repo Buddy is a Streamlit
assistant that clones a repository, figures out its stack, installs its
dependencies, and starts it for you — with an optional Gemini-powered
chat layer that reads the README when rule-based parsing isn't enough.

![CI](https://github.com/beyondpratham/AI-Repo-Buddy/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

---

## Security: read before you run this

AI Repo Buddy's entire job is to **execute code from repositories you give
it** — install commands, run commands, and (optionally) commands an LLM
extracted from that repo's README — directly on your machine via a shell.
This is inherent to what the tool does, not a bug:

- A malicious or compromised repo can run arbitrary code with your user's
  privileges.
- A crafted README is untrusted input to the AI extraction step and could
  attempt prompt injection.
- There is no sandboxing, network isolation, or approval step between
  "command discovered" and "command executed."

**Only point this at repositories you trust, and prefer running it inside an
isolated environment** (a disposable VM or container with no access to your
secrets or host filesystem) rather than on your primary machine. See
[SECURITY.md](SECURITY.md) for details.

---

## Features

- **Auto-clone** — paste any `https://github.com/<owner>/<repo>` URL
- **Stack detection** — Python, Node.js, Go, Rust, Ruby, Java (Maven/Gradle), Docker Compose
- **README-aware setup** — parses install/run commands via rules, or via Gemini when a key is configured
- **Isolated installs** — Python projects get a per-clone virtual environment (`.venv_bot/`), never your system interpreter
- **Multi-service run** — starts a frontend and backend concurrently when a repo has both, streams live logs, and auto-detects the listening port
- **Self-healing runs** — retries a failed run command and attempts to repair broken file paths before giving up
- **Conversational fallback** — ask general questions in the same chat once a Gemini API key is set

## Folder structure

```
AI-Repo-Buddy/
├── .github/workflows/ci.yml   # lint/test on push & PR
├── .streamlit/config.toml     # Streamlit theme config
├── src/                       # application source
│   ├── app.py                 # Streamlit entrypoint & UI
│   ├── ai_helper.py           # Gemini chat + AI-based README extraction
│   ├── installer.py           # builds the dependency-install plan
│   ├── process_manager.py     # background process streaming/lifecycle
│   ├── readme_parser.py       # rule-based command extraction from docs
│   ├── repo_handler.py        # GitHub URL parsing & git clone
│   ├── runner.py              # run-command discovery, service startup, retry/repair
│   └── stack_detector.py      # stack + setup-doc detection
├── tests/                     # pytest suite for the pure-logic modules
├── .env.example                # documents required/optional env vars
├── requirements.txt
├── SECURITY.md
└── CONTRIBUTORS.md
```

## Getting started

### Prerequisites

- Python 3.9+
- [git](https://git-scm.com/) on your `PATH`
- (Optional) a [Gemini API key](https://aistudio.google.com/apikey) for AI-powered chat and README parsing

### Install

```bash
git clone https://github.com/beyondpratham/AI-Repo-Buddy.git
cd AI-Repo-Buddy
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure (optional)

```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY
```

Without a key, the app still clones/installs/runs projects using rule-based
README parsing — you just lose the AI chat and AI-assisted extraction. A key
can also be pasted directly into the sidebar at runtime instead of using
`.env`.

### Run

```bash
streamlit run src/app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`), paste a
GitHub repository URL into the chat box, and AI Repo Buddy takes it from
there.

## How it works

1. **Clone** — `repo_handler.py` validates the URL and does a shallow
   (`--depth 1`) clone into a temporary directory.
2. **Detect** — `stack_detector.py` looks for dependency-file signatures
   (`requirements.txt`, `package.json`, `go.mod`, …) and locates setup docs.
3. **Parse setup docs** — `readme_parser.py` extracts install/run commands
   with keyword rules; if a Gemini key is available, `ai_helper.py` asks the
   model to read the docs instead, which handles prose instructions rules
   can't.
4. **Install** — `installer.py` builds an ordered install plan (creating an
   isolated `.venv_bot/` for Python projects) and executes it, streaming
   output live via `process_manager.py`.
5. **Run** — `runner.py` discovers one or more runnable services (e.g. a
   `frontend/` and a `backend/` in the same repo), starts them concurrently,
   detects the listening port from logs, and retries with a path fix if a
   command fails because a file couldn't be found.

## Development

```bash
pip install -r requirements.txt pytest
pytest tests/ -q
```

Tests cover the pure-logic modules (URL parsing, README command extraction,
stack detection, port detection). `app.py`, `process_manager.py`, and the
Gemini calls in `ai_helper.py` are integration surfaces best verified by
running the app.

## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE).
