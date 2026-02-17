"""Agent setup — installs hooks, skills, and configuration for supported agents."""

import json
import os
import shutil
from typing import Any


def _read_json(path: str) -> dict:
    """Read a JSON file, returning empty dict if missing or empty."""
    try:
        with open(path) as f:
            return json.load(f) or {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: str, data: dict) -> None:
    """Write a dict as formatted JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


MCP_CONFIG = {
    "command": "memory",
    "args": ["mcp"],
    "type": "stdio",
}


def _remove_old_hooks(settings: dict) -> list[str]:
    """Remove legacy EchoVault hooks from settings. Returns list of removed event names."""
    hooks = settings.get("hooks", {})
    removed = []
    memory_fragments = ("memory context", "memory auto-save")

    for event in list(hooks.keys()):
        event_hooks = hooks[event]
        filtered = [
            group for group in event_hooks
            if not any(
                any(frag in h.get("command", "") for frag in memory_fragments)
                for h in group.get("hooks", [])
            )
        ]
        if len(filtered) != len(event_hooks):
            removed.append(event)
            if filtered:
                hooks[event] = filtered
            else:
                del hooks[event]

    if not hooks and "hooks" in settings:
        del settings["hooks"]

    return removed


def _get_skill_md_path() -> str:
    """Get the path to the bundled SKILL.md file."""
    # Walk up from this file to find skills/echovault/SKILL.md in the package root.
    # In an installed package, use importlib.resources; for dev, use relative path.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    # Try dev layout: src/memory/setup.py -> ../../skills/echovault/SKILL.md
    dev_path = os.path.join(this_dir, "..", "..", "skills", "echovault", "SKILL.md")
    if os.path.exists(dev_path):
        return os.path.abspath(dev_path)
    # Try installed layout: check package data
    try:
        from importlib.resources import files
        pkg_path = str(files("memory").joinpath("skill", "SKILL.md"))
        if os.path.exists(pkg_path):
            return pkg_path
    except (ImportError, TypeError):
        pass
    return ""


def _install_skill(agent_home: str) -> bool:
    """Install the echovault SKILL.md into an agent's skills directory.

    Args:
        agent_home: Path to the agent's config directory (e.g. ~/.claude).

    Returns:
        True if skill was installed, False if already present.
    """
    skill_dir = os.path.join(agent_home, "skills", "echovault")
    skill_path = os.path.join(skill_dir, "SKILL.md")

    if os.path.exists(skill_path):
        return False

    source = _get_skill_md_path()
    os.makedirs(skill_dir, exist_ok=True)

    if source:
        shutil.copy2(source, skill_path)
    else:
        # Fallback: write a minimal skill file
        with open(skill_path, "w") as f:
            f.write(_FALLBACK_SKILL_MD)

    return True


def _uninstall_skill(agent_home: str) -> bool:
    """Remove the echovault skill from an agent's skills directory.

    Returns:
        True if skill was removed, False if not found.
    """
    skill_dir = os.path.join(agent_home, "skills", "echovault")
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
        return True
    return False


_FALLBACK_SKILL_MD = """\
---
name: echovault
description: Local-first memory for coding agents. You MUST retrieve memories at session start and save memories before session end. This is not optional.
---

# EchoVault — Agent Memory System

You have persistent memory across sessions. USE IT.

## Session start — MANDATORY

Before doing ANY work, retrieve context from previous sessions:

```bash
memory context --project
```

If the user's request relates to a specific topic, also search for it:

```bash
memory search "<relevant terms>"
```

When search results show "Details: available", fetch them:

```bash
memory details <memory-id>
```

Do not skip this step. Prior sessions may contain decisions, bugs, and context that directly affect your current task.

## Session end — MANDATORY

Before ending your response to ANY task that involved making changes, debugging, deciding, or learning something, you MUST save a memory. This is not optional. If you did meaningful work, save it.

```bash
memory save \\
  --title "Short descriptive title" \\
  --what "What happened or was decided" \\
  --why "Reasoning behind it" \\
  --impact "What changed as a result" \\
  --tags "tag1,tag2,tag3" \\
  --category "<category>" \\
  --related-files "path/to/file1,path/to/file2" \\
  --source "claude-code" \\
  --details "Full context with all important details. Be thorough.
             Include alternatives considered, tradeoffs, config values,
             and anything someone would need to understand this fully later."
```

Categories: `decision`, `bug`, `pattern`, `learning`, `context`.

Use `--source` to identify the agent: `claude-code`, `codex`, or `cursor`.

### What to save

You MUST save when any of these happen:

- You made an architectural or design decision
- You fixed a bug (include root cause and solution)
- You discovered a non-obvious pattern or gotcha
- You set up infrastructure, tooling, or configuration
- You chose one approach over alternatives
- You learned something about the codebase that isn't in the code
- The user corrected you or clarified a requirement

### What NOT to save

- Trivial changes (typo fixes, formatting)
- Information that's already obvious from reading the code
- Duplicate of an existing memory (search first)

## Other commands

```bash
memory config       # show current configuration
memory sessions     # list session files
memory reindex      # rebuild search index
memory delete <id>  # remove a memory
```

## Rules

- Retrieve before working. Save before finishing. No exceptions.
- Always capture thorough details — write for a future agent with no context.
- Never include API keys, secrets, or credentials.
- Wrap sensitive values in `<redacted>` tags.
- Search before saving to avoid duplicates.
- One memory per distinct decision or event. Don't bundle unrelated things.
"""


def setup_claude_code(claude_home: str) -> dict[str, str]:
    """Install EchoVault MCP server into Claude Code settings."""
    settings_path = os.path.join(claude_home, "settings.json")
    settings = _read_json(settings_path)

    installed = []

    # Remove old hooks if present
    removed = _remove_old_hooks(settings)
    if removed:
        installed.append(f"removed old hooks: {', '.join(removed)}")

    # Remove old skill if present
    _uninstall_skill(claude_home)

    # Add MCP server config
    mcp_servers = settings.setdefault("mcpServers", {})
    if "echovault" not in mcp_servers:
        mcp_servers["echovault"] = MCP_CONFIG
        installed.append("mcpServers")

    _write_json(settings_path, settings)

    if installed:
        return {"status": "ok", "message": f"Installed: {', '.join(installed)}"}
    return {"status": "ok", "message": "Already installed"}


def setup_cursor(cursor_home: str) -> dict[str, str]:
    """Install EchoVault MCP server into Cursor mcp.json."""
    mcp_path = os.path.join(cursor_home, "mcp.json")
    data = _read_json(mcp_path)

    installed = []

    # Remove old hooks if present
    old_hooks_path = os.path.join(cursor_home, "hooks.json")
    if os.path.exists(old_hooks_path):
        old_data = _read_json(old_hooks_path)
        hooks = old_data.get("hooks", {})
        for event in list(hooks.keys()):
            event_hooks = hooks[event]
            filtered = [h for h in event_hooks if "memory context" not in h.get("command", "")]
            if len(filtered) != len(event_hooks):
                installed.append(f"removed old hook: {event}")
                if filtered:
                    hooks[event] = filtered
                else:
                    del hooks[event]
        _write_json(old_hooks_path, old_data)

    # Remove old skill if present
    _uninstall_skill(cursor_home)

    # Add MCP server config
    mcp_servers = data.setdefault("mcpServers", {})
    if "echovault" not in mcp_servers:
        mcp_servers["echovault"] = MCP_CONFIG
        installed.append("mcpServers")

    _write_json(mcp_path, data)

    if installed:
        return {"status": "ok", "message": f"Installed: {', '.join(installed)}"}
    return {"status": "ok", "message": "Already installed"}


CODEX_AGENTS_MD_SECTION = """\

## EchoVault — Persistent Memory

You have persistent memory across sessions. Use it.

### Session start — MANDATORY

Before doing any work, retrieve context:

```bash
memory context --project
```

Search for relevant memories:

```bash
memory search "<relevant terms>"
```

When results show "Details: available", fetch them:

```bash
memory details <memory-id>
```

### Session end — MANDATORY

Before finishing any task that involved changes, debugging, decisions, or learning, save a memory:

```bash
memory save \\
  --title "Short descriptive title" \\
  --what "What happened or was decided" \\
  --why "Reasoning behind it" \\
  --impact "What changed as a result" \\
  --tags "tag1,tag2,tag3" \\
  --category "decision" \\
  --related-files "path/to/file1,path/to/file2" \\
  --source "codex" \\
  --details "Full context. Be thorough."
```

Categories: `decision`, `bug`, `pattern`, `learning`, `context`.

### Rules

- Retrieve before working. Save before finishing. No exceptions.
- Never include API keys, secrets, or credentials.
- Search before saving to avoid duplicates.
"""


def setup_codex(codex_home: str) -> dict[str, str]:
    """Install EchoVault instructions into Codex AGENTS.md.

    Codex lacks a hook system, so we append memory instructions
    to the global AGENTS.md file.

    Args:
        codex_home: Path to the .codex directory (e.g. ~/.codex).

    Returns:
        Dict with 'status' and 'message' keys.
    """
    agents_path = os.path.join(codex_home, "AGENTS.md")

    existing = ""
    try:
        with open(agents_path) as f:
            existing = f.read()
    except FileNotFoundError:
        pass

    if "## EchoVault" in existing:
        return {"status": "ok", "message": "AGENTS.md already contains EchoVault section"}

    os.makedirs(os.path.dirname(agents_path), exist_ok=True)
    with open(agents_path, "w") as f:
        f.write(existing.rstrip("\n") + "\n" + CODEX_AGENTS_MD_SECTION)

    installed = ["AGENTS.md"]
    skill_installed = _install_skill(codex_home)
    if skill_installed:
        installed.append("skill")

    msg = f"Installed: {', '.join(installed)}"
    msg += "\nNote: Auto-persist (Stop hook) is only available for Claude Code. Codex relies on AGENTS.md instructions for saving."
    return {"status": "ok", "message": msg}


def uninstall_claude_code(claude_home: str) -> dict[str, str]:
    """Remove EchoVault from Claude Code settings (MCP config + old hooks)."""
    settings_path = os.path.join(claude_home, "settings.json")
    settings = _read_json(settings_path)

    removed = []

    # Remove MCP config
    mcp_servers = settings.get("mcpServers", {})
    if "echovault" in mcp_servers:
        del mcp_servers["echovault"]
        removed.append("mcpServers")
        if not mcp_servers and "mcpServers" in settings:
            del settings["mcpServers"]

    # Remove old hooks
    old_removed = _remove_old_hooks(settings)
    removed.extend(old_removed)

    # Remove old skill
    if _uninstall_skill(claude_home):
        removed.append("skill")

    if removed:
        _write_json(settings_path, settings)
        return {"status": "ok", "message": f"Removed: {', '.join(removed)}"}
    return {"status": "ok", "message": "Nothing to remove"}


def uninstall_cursor(cursor_home: str) -> dict[str, str]:
    """Remove EchoVault from Cursor (MCP config + old hooks)."""
    mcp_path = os.path.join(cursor_home, "mcp.json")
    data = _read_json(mcp_path)

    removed = []

    mcp_servers = data.get("mcpServers", {})
    if "echovault" in mcp_servers:
        del mcp_servers["echovault"]
        removed.append("mcpServers")
        if not mcp_servers and "mcpServers" in data:
            del data["mcpServers"]

    # Remove old hooks
    old_hooks_path = os.path.join(cursor_home, "hooks.json")
    if os.path.exists(old_hooks_path):
        old_data = _read_json(old_hooks_path)
        hooks = old_data.get("hooks", {})
        for event in list(hooks.keys()):
            event_hooks = hooks[event]
            filtered = [h for h in event_hooks if "memory context" not in h.get("command", "")]
            if len(filtered) != len(event_hooks):
                removed.append(event)
                if filtered:
                    hooks[event] = filtered
                else:
                    del hooks[event]
        _write_json(old_hooks_path, old_data)

    if _uninstall_skill(cursor_home):
        removed.append("skill")

    if removed:
        _write_json(mcp_path, data)
        return {"status": "ok", "message": f"Removed: {', '.join(removed)}"}
    return {"status": "ok", "message": "Nothing to remove"}


def uninstall_codex(codex_home: str) -> dict[str, str]:
    """Remove EchoVault section from Codex AGENTS.md."""
    import re

    agents_path = os.path.join(codex_home, "AGENTS.md")

    try:
        with open(agents_path) as f:
            content = f.read()
    except FileNotFoundError:
        return {"status": "ok", "message": "No AGENTS.md found"}

    if "## EchoVault" not in content:
        return {"status": "ok", "message": "No EchoVault section found"}

    cleaned = re.sub(
        r"\n*## EchoVault[^\n]*\n.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    )

    with open(agents_path, "w") as f:
        f.write(cleaned.strip() + "\n")

    removed = ["AGENTS.md"]
    skill_removed = _uninstall_skill(codex_home)
    if skill_removed:
        removed.append("skill")

    return {"status": "ok", "message": f"Removed: {', '.join(removed)}"}
