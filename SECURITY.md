# Security Policy

## Design-level risk: arbitrary code execution by design

AI Repo Buddy's core feature is cloning **any** GitHub repository you point it
at and then executing that repository's install/run commands — sourced from
dependency-file conventions, its README (parsed by rules or by an LLM), or
structural guesses — directly on the host machine via a shell.

This means:

- Pasting a malicious repo URL can run arbitrary code on your machine, with
  whatever privileges the app process has.
- A repo's README can itself be adversarial input to the AI extraction step
  (prompt injection): crafted text could try to steer the model into
  suggesting a harmful command, which would then be executed the same way as
  any legitimate one.
- There is currently no sandboxing, network isolation, or command allow-list
  between "command discovered" and "command executed."

**Only run this against repositories you trust, and prefer running it inside
an isolated environment** (a disposable VM, a container with no access to
secrets or the host filesystem, or similar) rather than directly on a primary
machine. Do not run it against untrusted or unfamiliar repositories.

Hardening this properly (e.g. containerized execution per session, a command
allow-list/confirmation step before running anything, resource limits) is
tracked as future work and contributions in this direction are welcome.

## Reporting a vulnerability

If you find a security issue in AI Repo Buddy itself (as opposed to the
inherent risk described above), please open a private report via GitHub's
"Report a vulnerability" flow on this repository, or contact the maintainer
directly, rather than filing a public issue.
