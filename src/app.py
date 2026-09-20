 
import os
import time
 
import streamlit as st
 
from ai_helper import DEFAULT_MODEL, chat_with_ai, extract_commands_with_ai
from installer import build_install_plan
from process_manager import StreamingProcess
from readme_parser import extract_commands, load_docs, load_readme
from repo_handler import cleanup_dir, clone_repo, parse_github_url
from runner import discover_services, detect_port_from_logs, resolve_run_command, start_run
from stack_detector import detect_stack, find_readme, find_setup_docs
 
st.set_page_config(
    page_title="AI Repo Buddy",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Global styling
# --------------------------------------------------------------------------
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --grad: linear-gradient(120deg, #8b5cf6 0%, #6366f1 45%, #ec4899 100%);
            --card: #161826;
            --card-border: rgba(255,255,255,0.07);
            --muted: #9ca3b8;
        }

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* App background: subtle radial glow */
        .stApp {
            background:
                radial-gradient(1100px 500px at 15% -10%, rgba(139,92,246,0.16), transparent 60%),
                radial-gradient(900px 500px at 100% 0%, rgba(236,72,153,0.12), transparent 55%),
                #0d0e18;
        }

        /* Hide default Streamlit chrome for a cleaner canvas */
        #MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
        .block-container { padding-top: 2.2rem; max-width: 900px; }

        /* ---------- Hero ---------- */
        .hero { text-align: center; padding: 0.5rem 0 1.4rem; }
        .hero-badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 6px 14px; border-radius: 999px;
            background: rgba(139,92,246,0.12);
            border: 1px solid rgba(139,92,246,0.35);
            color: #c4b5fd; font-size: 0.78rem; font-weight: 600;
            letter-spacing: 0.02em; margin-bottom: 1.1rem;
        }
        .hero-dot {
            width: 7px; height: 7px; border-radius: 50%;
            background: #34d399; box-shadow: 0 0 10px #34d399;
        }
        .hero h1 {
            font-size: 2.9rem; font-weight: 800; line-height: 1.1;
            margin: 0 0 0.6rem;
            background: var(--grad);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero p { color: var(--muted); font-size: 1.05rem; max-width: 560px; margin: 0 auto; }

        /* ---------- Feature chips ---------- */
        .chips { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-top: 1.3rem; }
        .chip {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 9px 15px; border-radius: 12px;
            background: var(--card); border: 1px solid var(--card-border);
            color: #d7d9e6; font-size: 0.85rem; font-weight: 500;
            transition: transform .15s ease, border-color .15s ease;
        }
        .chip:hover { transform: translateY(-2px); border-color: rgba(139,92,246,0.5); }

        /* ---------- Chat bubbles ---------- */
        [data-testid="stChatMessage"] {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 0.65rem 1rem;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        }
        [data-testid="stChatMessageAvatarUser"] { background: var(--grad) !important; }

        /* ---------- Chat input ---------- */
        [data-testid="stChatInput"] {
            border-radius: 14px;
            border: 1px solid var(--card-border);
            background: var(--card);
        }
        [data-testid="stChatInput"]:focus-within {
            border-color: #8b5cf6;
            box-shadow: 0 0 0 3px rgba(139,92,246,0.25);
        }

        /* ---------- Buttons ---------- */
        .stButton > button {
            border-radius: 12px; font-weight: 600; border: 1px solid var(--card-border);
            background: var(--card); color: #e7e8f0; transition: all .15s ease;
        }
        .stButton > button:hover {
            border-color: #8b5cf6; color: #fff;
            box-shadow: 0 6px 18px rgba(139,92,246,0.28); transform: translateY(-1px);
        }

        /* ---------- Sidebar ---------- */
        [data-testid="stSidebar"] {
            background: #0b0c15;
            border-right: 1px solid var(--card-border);
        }
        .sb-brand {
            display: flex; align-items: center; gap: 12px; margin-bottom: 4px;
        }
        .sb-logo {
            width: 42px; height: 42px; border-radius: 12px; flex-shrink: 0;
            background: var(--grad); display: flex; align-items: center;
            justify-content: center; font-size: 1.3rem;
            box-shadow: 0 6px 18px rgba(139,92,246,0.4);
        }
        .sb-brand h2 { font-size: 1.15rem; font-weight: 700; margin: 0; color: #fff; }
        .sb-brand span { font-size: 0.75rem; color: var(--muted); }

        /* Status / code blocks */
        [data-testid="stStatusWidget"], .stStatus { border-radius: 14px !important; }
        code { font-family: 'JetBrains Mono', monospace; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
DEFAULTS = {
    "messages": [],
    "repo_path": None,
    "base_dir": None,
    # Each running service: {"name", "command", "proc", "logs": [...], "port"}.
    "services": [],
    "gemini_key": os.getenv("GEMINI_API_KEY", ""),
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def stop_all_services():
    """Terminate every running service process and clear the list."""
    for svc in st.session_state.services:
        proc = svc.get("proc")
        if proc is not None:
            try:
                proc.stop()
            except Exception:
                pass
    st.session_state.services = []


def format_elapsed(seconds):
    """Render a second count as e.g. '2m 05s' or '47s'."""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


# --------------------------------------------------------------------------
# Live server status panel (auto-refreshes while a server is running)
# --------------------------------------------------------------------------
@st.fragment(run_every=2.0)
def render_server_status():
    services = st.session_state.services

    # Drain output from every running service since the last refresh.
    for svc in services:
        proc = svc.get("proc")
        if proc is None:
            continue
        new_lines = proc.poll_lines()
        if new_lines:
            svc["logs"].extend(new_lines)
            if not svc.get("port"):
                port = detect_port_from_logs(new_lines)
                if port:
                    svc["port"] = port

    running = [s for s in services if s.get("proc") is not None and s["proc"].is_running()]
    if not running:
        return

    label = "🟢 **Server running**" if len(running) == 1 else f"🟢 **{len(running)} services running**"
    st.success(label)

    for idx, svc in enumerate(services):
        proc = svc.get("proc")
        if proc is None or not proc.is_running():
            continue

        st.markdown(f"**{svc['name']}**")
        started_at = svc.get("started_at")
        caption = f"`{svc['command']}`"
        if started_at:
            caption += f" · up {format_elapsed(time.time() - started_at)}"
        st.caption(caption)

        port = svc.get("port")
        if port:
            url = f"http://localhost:{port}"
            st.link_button(f"🔗 Open {svc['name']}", url, use_container_width=True)

        with st.expander(f"📜 Terminal logs — {svc['name']}", expanded=len(running) == 1):
            logs = svc["logs"][-200:]
            st.code("\n".join(logs) or "(waiting for output...)", language="bash")
            st.download_button(
                "⬇️ Download full log",
                "\n".join(svc["logs"]) or "(no output)",
                file_name=f"{svc['name']}.log",
                key=f"download_{idx}",
                use_container_width=True,
            )

        if st.button(f"⏹ Stop {svc['name']}", key=f"stop_{idx}", use_container_width=True):
            try:
                proc.stop()
            except Exception:
                pass
            svc["proc"] = None
            st.rerun()

    if len(running) > 1 and st.button("⏹ Stop all services", use_container_width=True):
        stop_all_services()
        st.rerun()


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="sb-brand">
            <div class="sb-logo">🛠️</div>
            <div>
                <h2>AI Repo Buddy</h2>
                <span>Clone · Install · Run — automatically</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    env_key_set = bool(os.getenv("GEMINI_API_KEY"))
    key_input = st.text_input(
        "Gemini API key",
        value=st.session_state.gemini_key,
        type="password",
        placeholder="Using GEMINI_API_KEY from environment" if env_key_set else "AIza...",
        help="Enables AI-powered chat and smarter README parsing. "
        "Get a key at https://aistudio.google.com/apikey. "
        "Leave blank to use the GEMINI_API_KEY environment variable, or to run without AI features.",
    )
    st.session_state.gemini_key = key_input
    if key_input or env_key_set:
        st.caption("✅ AI features enabled")
    else:
        st.caption("⚠️ AI features disabled — add a key to enable AI chat and smarter README parsing")

    st.divider()

    if st.session_state.repo_path:
        st.success(f"**Active repo**\n\n`{os.path.basename(st.session_state.repo_path)}`")

    render_server_status()

    if st.button("🗑️ Reset session", use_container_width=True):
        stop_all_services()
        cleanup_dir(st.session_state.base_dir)
        for key, value in DEFAULTS.items():
            st.session_state[key] = value
        st.rerun()


# --------------------------------------------------------------------------
# Header / hero
# --------------------------------------------------------------------------
if not st.session_state.messages:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge"><span class="hero-dot"></span> Powered by Invictus</div>
            <h1>Set up any GitHub repo<br/>in one message</h1>
            <p>Paste a repository URL and I'll clone it, read the README, install its
            dependencies, and start it for you — fully automated.</p>
            <div class="chips">
                <div class="chip">📥 Auto-clone</div>
                <div class="chip">🔍 Stack detection</div>
                <div class="chip">📦 Smart install</div>
                <div class="chip">🚀 One-click run</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.4rem;">
            <div class="sb-logo" style="width:34px;height:34px;font-size:1rem;">🤖</div>
            <div style="font-weight:700;font-size:1.15rem;">AI Repo Buddy</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
 
 
# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})


def build_repo_context():
    """
    Summarize the currently cloned repo and its run state so the chat AI can
    answer follow-up questions with awareness of the previous clone.
    Returns an empty string when no repo has been set up yet.
    """
    if not st.session_state.repo_path:
        return ""

    lines = [f"- Cloned repository: {os.path.basename(st.session_state.repo_path)}"]
    services = st.session_state.services
    for svc in services:
        proc = svc.get("proc")
        status = "running" if (proc is not None and proc.is_running()) else "stopped"
        detail = f"- Service `{svc['name']}`: {status} (`{svc['command']}`)"
        if svc.get("port"):
            detail += f", port {svc['port']}"
        lines.append(detail)
        if svc.get("logs"):
            recent = "\n".join(svc["logs"][-15:])
            lines.append(f"  Recent logs:\n{recent}")

    return "\n".join(lines)

 
 
def run_with_live_log(command, cwd, placeholder, timeout=900):
    """
    Run a command to completion, updating `placeholder` with the tail of its
    output as it goes. Returns (success, full_log_text, return_code).
    """
    proc = StreamingProcess(command, cwd=cwd).start()
    collected = []
    start = time.time()
    while True:
        new_lines = proc.poll_lines()
        if new_lines:
            collected.extend(new_lines)
            placeholder.code("\n".join(collected[-60:]), language="bash")
        if proc._finished:
            time.sleep(0.05)
            leftover = proc.poll_lines()
            if leftover:
                collected.extend(leftover)
                placeholder.code("\n".join(collected[-60:]) or "(no output)", language="bash")
            elif not collected:
                placeholder.code("(no output)", language="bash")
            return proc.return_code == 0, "\n".join(collected), proc.return_code
        if time.time() - start > timeout:
            proc.stop()
            collected.append(f"[Timed out after {timeout}s -- moving on]")
            placeholder.code("\n".join(collected[-60:]), language="bash")
            return False, "\n".join(collected), None
        time.sleep(0.2)
 
 
def finish(text):
    """Store the final assistant message and render it in the current chat bubble."""
    add_message("assistant", text)
    st.markdown(text)
 
 
def start_service(service, repo_path):
    """
    Try a single service's candidate commands until one stays running.

    Returns a running-service dict {"name", "command", "proc", "logs", "port"}
    on success, or None if every candidate failed. Progress is rendered into the
    current Streamlit container. A successful process keeps running in the
    background, so multiple services can run concurrently.
    """
    name = service["name"]
    candidates = service["commands"]
    proc = None
    run_command = None

    for cand_index, (candidate_command, source) in enumerate(candidates, start=1):
        run_command = candidate_command
        header = f"**{name}**"
        if len(candidates) > 1:
            header += f" — candidate {cand_index} of {len(candidates)}"
        st.write(f"{header} (source: {source}):")

        max_attempts = 3
        no_fix_retry_used = False

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                st.write(f"🔁 Attempt {attempt} of {max_attempts}:")
            st.code(run_command, language="bash")

            proc = start_run(run_command, repo_path)
            placeholder = st.empty()
            preview_lines = []
            start_time = time.time()
            while time.time() - start_time < 8:
                new_lines = proc.poll_lines()
                if new_lines:
                    preview_lines.extend(new_lines)
                    placeholder.code("\n".join(preview_lines[-40:]), language="bash")
                if not proc.is_running():
                    break
                time.sleep(0.3)

            # Success: still running, or exited cleanly.
            if proc.is_running() or proc.return_code in (0, None):
                return {
                    "name": name,
                    "command": run_command,
                    "proc": proc,
                    "logs": list(preview_lines),
                    "port": detect_port_from_logs(preview_lines),
                    "started_at": time.time(),
                }

            # Failed. If attempts remain, try to fix the command and retry.
            if attempt < max_attempts:
                log_text = "\n".join(preview_lines)
                fixed = resolve_run_command(run_command, repo_path, log_text)
                if fixed and fixed != run_command:
                    st.warning(
                        f"⚠️ {name}: run failed (exit code {proc.return_code}). Detected a path "
                        "issue — adjusting the command and retrying..."
                    )
                    run_command = fixed
                    continue
                if not no_fix_retry_used:
                    no_fix_retry_used = True
                    st.warning(
                        f"⚠️ {name}: run failed (exit code {proc.return_code}). "
                        "Retrying once in case the failure was transient..."
                    )
                    continue
                break

        if cand_index < len(candidates):
            st.warning(
                f"⚠️ `{run_command}` didn't start (exit code {proc.return_code}). "
                f"Trying the next command for {name}..."
            )

    return None


def process_repo_url(url):
    # Tear down any previous repo/background process before starting fresh.
    stop_all_services()
    cleanup_dir(st.session_state.base_dir)
    st.session_state.repo_path = None
    st.session_state.base_dir = None

    summary = []
 
    # ---------------- 1. Clone ----------------
    with st.status("📥 Cloning repository...", expanded=True) as status:
        try:
            repo_path, repo_name = clone_repo(url)
        except Exception as e:
            status.update(label="❌ Clone failed", state="error")
            st.error(str(e))
            finish(f"❌ I couldn't clone that repository:\n\n```\n{e}\n```")
            return
 
        st.session_state.repo_path = repo_path
        st.session_state.base_dir = os.path.dirname(repo_path)
        st.write(f"Cloned **{repo_name}** into a temporary workspace.")
        status.update(label=f"✅ Cloned {repo_name}", state="complete")
    summary.append(f"✅ Cloned `{repo_name}`")
 
    # ---------------- 2. Detect stack ----------------
    with st.status("🔍 Detecting project stack...", expanded=True) as status:
        detected = detect_stack(repo_path)
        if detected:
            st.write("Detected: " + ", ".join(detected.keys()))
        else:
            st.write("No standard dependency files detected at the repo root.")
        status.update(label="✅ Stack detection complete", state="complete")
    summary.append(f"✅ Detected stack: {', '.join(detected.keys()) if detected else 'unknown'}")
 
    # ---------------- 3. Read README ----------------
    readme_install_cmds, readme_run_cmds = [], []
    with st.status("📖 Reading setup docs...", expanded=True) as status:
        doc_paths = find_setup_docs(repo_path)
        if doc_paths:
            readme_text = load_docs(doc_paths)
            doc_names = ", ".join(os.path.basename(p) for p in doc_paths)
            st.write(f"Found {len(doc_paths)} setup doc(s): `{doc_names}` ({len(readme_text)} characters).")
 
            ai_install, ai_run = None, None
            if st.session_state.gemini_key or os.getenv("GEMINI_API_KEY"):
                st.write("Asking Gemini to interpret the setup instructions...")
                ai_install, ai_run = extract_commands_with_ai(readme_text, st.session_state.gemini_key)
 
            if ai_install or ai_run:
                readme_install_cmds, readme_run_cmds = ai_install or [], ai_run or []
                st.write("✅ AI-based extraction succeeded.")
            else:
                readme_install_cmds, readme_run_cmds = extract_commands(readme_text)
                st.write("Used rule-based extraction.")
 
            if readme_install_cmds:
                st.write("Install-related commands found in the docs:")
                st.code("\n".join(readme_install_cmds), language="bash")
            if readme_run_cmds:
                st.write("Run-related commands found in the docs:")
                st.code("\n".join(readme_run_cmds), language="bash")
            if not readme_install_cmds and not readme_run_cmds:
                st.write("No explicit setup commands found in the docs; relying on stack detection.")
        else:
            st.write("No README or setup docs found in the repository.")
        status.update(label="✅ Setup docs processed", state="complete")
    summary.append("✅ Setup docs parsed" if doc_paths else "⚠️ No setup docs found")
 
    # ---------------- 4. Install dependencies ----------------
    install_plan = build_install_plan(repo_path, detected, readme_install_cmds)
    if not install_plan:
        finish(
            "\n\n".join(summary)
            + "\n\n⚠️ I couldn't determine any dependencies to install for this project "
            "(no recognized dependency files and nothing usable in the README). "
            "You may need to set it up manually."
        )
        return
 
    install_results = []
    with st.status("📦 Installing dependencies...", expanded=True) as status:
        for label, cmd in install_plan:
            st.write(f"**{label}**")
            st.caption(f"`{cmd}`")
            placeholder = st.empty()
            success, _, rc = run_with_live_log(cmd, repo_path, placeholder, timeout=900)
            install_results.append((label, cmd, success, rc))
            if not success:
                st.warning(f"This step reported an issue (exit code {rc}). Continuing with remaining steps...")
 
        any_failed = any(not r[2] for r in install_results)
        status.update(
            label="✅ Dependencies installed" if not any_failed else "⚠️ Installed with some warnings",
            state="complete" if not any_failed else "error",
        )
    summary.append(
        "✅ Dependencies installed"
        if not any(not r[2] for r in install_results)
        else "⚠️ Some install steps reported issues (see logs above for details)"
    )
 
    # ---------------- 5. Run the app(s) ----------------
    with st.status("🚀 Starting the application...", expanded=True) as status:
        services = discover_services(repo_path, detected, readme_run_cmds)
        if not services:
            st.write("Couldn't confidently determine how to run this project.")
            status.update(label="⚠️ Could not determine a run command", state="error")
            summary.append(
                "⚠️ I installed the dependencies but couldn't figure out how to start the app. "
                "Check the README's usage section for the exact run command."
            )
        else:
            if len(services) > 1:
                names = ", ".join(f"`{s['name']}`" for s in services)
                st.write(f"Detected **{len(services)} services** to run concurrently: {names}.")
            elif not readme_run_cmds:
                st.write(
                    "No explicit run instructions were found, so I'll try "
                    f"{len(services[0]['commands'])} default command(s) based on the project structure."
                )

            started_services = []
            failed_services = []
            for service in services:
                result = start_service(service, repo_path)
                if result:
                    started_services.append(result)
                else:
                    failed_services.append(service["name"])

            st.session_state.services = started_services

            if started_services:
                status.update(
                    label="✅ App started" if not failed_services else "⚠️ Some services started",
                    state="complete",
                )
                for svc in started_services:
                    if svc["port"]:
                        st.write(f"`{svc['name']}` appears to be listening on port **{svc['port']}**.")
                        summary.append(
                            f"🚀 `{svc['name']}` is running in the background on port **{svc['port']}** "
                            f"(`{svc['command']}`)."
                        )
                    else:
                        summary.append(
                            f"🚀 `{svc['name']}` is running in the background (`{svc['command']}`)."
                        )
                if failed_services:
                    summary.append(
                        "⚠️ Couldn't start: " + ", ".join(f"`{n}`" for n in failed_services)
                        + ". See the logs above for details."
                    )
                summary.append("Use the **Stop** buttons in the sidebar when you're done.")
            else:
                names = ", ".join(f"`{s['name']}`" for s in services)
                status.update(label="❌ App exited with an error", state="error")
                summary.append(
                    f"❌ I tried to start {names} but none stayed running. "
                    "See the logs above for details."
                )

    finish("\n\n".join(summary))
 
 
# --------------------------------------------------------------------------
# Chat input
# --------------------------------------------------------------------------
user_input = st.chat_input("Ask me anything, or paste a GitHub repo URL (e.g. https://github.com/user/repo)...")
 
if user_input:
    add_message("user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)
 
    with st.chat_message("assistant"):
        if parse_github_url(user_input):
            process_repo_url(user_input.strip())
        else:
            key_available = bool(st.session_state.gemini_key or os.getenv("GEMINI_API_KEY"))
            ai_reply = chat_with_ai(
                user_input,
                st.session_state.gemini_key,
                history=st.session_state.messages[:-1],
                repo_context=build_repo_context(),
            )
            if ai_reply:
                finish(ai_reply)
            elif key_available:
                finish(
                    "⚠️ I couldn't get a response from Gemini just now. "
                    "This usually means the API key is invalid/expired, the model name "
                    f"(`{DEFAULT_MODEL}`) isn't available to your key, "
                    "or there was a network issue. Please double-check your key in the sidebar and try again."
                )
            else:
                finish(
                    "👋 Hello! I'm **AI Repo Buddy**. I can clone GitHub repositories and set them up automatically.\n\n"
                    "**What I can do:**\n"
                    "- Clone a GitHub repo and install its dependencies\n"
                    "- Detect the project stack (Python, Node.js, Go, etc.)\n"
                    "- Start the application automatically\n\n"
                    "**Just paste a GitHub URL** (e.g. `https://github.com/user/repo`) to get started!\n\n"
                    "To enable AI-powered conversations, add your **Google Gemini API key** in the sidebar."
                )
 
