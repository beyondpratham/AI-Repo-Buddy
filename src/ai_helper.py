
import json
import os

# Default Gemini model used across the app. Override with the GEMINI_MODEL
# env var. Check https://ai.google.dev/gemini-api/docs/models for the current
# list of available model names before relying on this default.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _make_client(api_key):
    """
    Build a google-genai Client. Falls back to the GEMINI_API_KEY environment
    variable when no key is passed explicitly. Returns the client on success,
    or None if the SDK isn't installed or no key is available.
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
    except ImportError:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def chat_with_ai(user_message, api_key="", model=DEFAULT_MODEL, history=None, repo_context=""):
    """
    Send a conversational message to Gemini and return the assistant's reply.

    `history` is an optional list of prior messages ({"role", "content"}) so the
    model can see the earlier conversation. `repo_context` is an optional string
    describing the repository the user has already cloned/set up, so follow-up
    questions can be answered with that context in mind.

    Returns a string response on success, or None if unavailable/failed.
    """
    client = _make_client(api_key)
    if client is None:
        return None

    from google.genai import types

    system_instruction = (
        "You are a helpful assistant integrated into AI Repo Buddy. "
        "The bot can clone GitHub repositories, install dependencies, and run apps. "
        "If the user asks about these capabilities, answer helpfully. "
        "Keep responses concise and friendly."
    )
    if repo_context:
        system_instruction += (
            "\n\nHere is the current session context about the repository the user "
            "has already cloned and set up. Use it when answering follow-up "
            "questions:\n" + repo_context
        )

    # Build a running transcript so the model retains the earlier conversation.
    transcript = []
    for msg in (history or []):
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if content:
            transcript.append(f"{role}: {content}")
    transcript.append(f"User: {user_message}")
    transcript.append("Assistant:")
    conversation = "\n".join(transcript)

    try:
        response = client.models.generate_content(
            model=model,
            contents=conversation,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        text = (response.text or "").strip()
        return text or None
    except Exception:
        return None


def extract_commands_with_ai(readme_text, api_key="", model=DEFAULT_MODEL):
    """
    Ask a Gemini model to read the README and return install/run commands.
    Returns (install_commands, run_commands) on success, or (None, None) if
    the AI path is unavailable or fails for any reason (missing package,
    bad key, network error, malformed response, etc). Callers should treat
    (None, None) as "fall back to rule-based parsing".
    """
    client = _make_client(api_key)
    if client is None:
        return None, None

    from google.genai import types

    try:
        prompt = (
            "You are analyzing a GitHub project's README to figure out exactly how to "
            "set it up and run it locally on a fresh machine.\n\n"
            "Return a JSON object with two keys, \"install_commands\" and "
            "\"run_commands\", each a list of shell command strings in the order they "
            "should be executed. If nothing relevant is found, return empty lists for "
            "the corresponding key.\n\n"
            f"README CONTENT:\n{readme_text[:8000]}"
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = json.loads((response.text or "").strip())
        install_cmds = data.get("install_commands") or []
        run_cmds = data.get("run_commands") or []
        return install_cmds, run_cmds
    except Exception:
        return None, None
