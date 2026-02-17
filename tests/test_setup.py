"""Tests for agent setup module."""

import json
import os

import pytest


@pytest.fixture
def claude_home(tmp_path):
    """Create a temporary ~/.claude directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return claude_dir


@pytest.fixture
def claude_home_with_settings(claude_home):
    """Create ~/.claude with an existing settings.json."""
    settings = {"permissions": {"allow": ["Bash(memory:*)"]}}
    (claude_home / "settings.json").write_text(json.dumps(settings, indent=2))
    return claude_home


def _mcp_json_path(claude_home):
    """Return the .mcp.json path (project root = parent of .claude)."""
    return claude_home.parent / ".mcp.json"


class TestClaudeCodeSetup:
    def test_writes_mcp_server_config(self, claude_home):
        from memory.setup import setup_claude_code
        setup_claude_code(str(claude_home))
        mcp_path = _mcp_json_path(claude_home)
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "mcpServers" in data
        assert "echovault" in data["mcpServers"]
        mcp = data["mcpServers"]["echovault"]
        assert mcp["command"] == "memory"
        assert mcp["args"] == ["mcp"]

    def test_does_not_write_hooks(self, claude_home):
        from memory.setup import setup_claude_code
        setup_claude_code(str(claude_home))
        settings_path = claude_home / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            assert "hooks" not in settings or "UserPromptSubmit" not in settings.get("hooks", {})

    def test_preserves_existing_settings(self, claude_home):
        from memory.setup import setup_claude_code
        (claude_home / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(memory:*)"]}}, indent=2))
        setup_claude_code(str(claude_home))
        settings = json.loads((claude_home / "settings.json").read_text())
        assert settings["permissions"]["allow"] == ["Bash(memory:*)"]

    def test_does_not_duplicate_mcp_config(self, claude_home):
        from memory.setup import setup_claude_code
        setup_claude_code(str(claude_home))
        setup_claude_code(str(claude_home))
        data = json.loads(_mcp_json_path(claude_home).read_text())
        assert "echovault" in data["mcpServers"]

    def test_removes_old_hooks_on_setup(self, claude_home):
        from memory.setup import setup_claude_code
        old_settings = {
            "hooks": {
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "memory context --project"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "echo | memory auto-save"}]}],
            }
        }
        (claude_home / "settings.json").write_text(json.dumps(old_settings, indent=2))
        setup_claude_code(str(claude_home))
        settings = json.loads((claude_home / "settings.json").read_text())
        assert "hooks" not in settings or "UserPromptSubmit" not in settings.get("hooks", {})
        data = json.loads(_mcp_json_path(claude_home).read_text())
        assert "mcpServers" in data

    def test_migrates_mcp_from_settings_to_mcp_json(self, claude_home):
        from memory.setup import setup_claude_code
        old_settings = {
            "mcpServers": {"echovault": {"command": "memory", "args": ["mcp"], "type": "stdio"}},
            "permissions": {"allow": []}
        }
        (claude_home / "settings.json").write_text(json.dumps(old_settings, indent=2))
        setup_claude_code(str(claude_home))
        # Should be removed from settings.json
        settings = json.loads((claude_home / "settings.json").read_text())
        assert "mcpServers" not in settings
        # Should be in .mcp.json
        data = json.loads(_mcp_json_path(claude_home).read_text())
        assert "echovault" in data["mcpServers"]

    def test_removes_old_skill_on_setup(self, claude_home):
        from memory.setup import setup_claude_code
        skill_dir = claude_home / "skills" / "echovault"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("old skill")
        setup_claude_code(str(claude_home))
        assert not skill_dir.exists()

    def test_returns_success_result(self, claude_home):
        from memory.setup import setup_claude_code
        result = setup_claude_code(str(claude_home))
        assert result["status"] == "ok"


@pytest.fixture
def cursor_home(tmp_path):
    """Create a temporary .cursor directory."""
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    return cursor_dir


@pytest.fixture
def cursor_home_with_hooks(cursor_home):
    """Create .cursor with an existing hooks.json."""
    hooks = {
        "version": 1,
        "hooks": {
            "afterFileEdit": [
                {"command": "./format.sh"}
            ]
        }
    }
    (cursor_home / "hooks.json").write_text(json.dumps(hooks, indent=2))
    return cursor_home


class TestCursorSetup:
    def test_writes_mcp_config(self, cursor_home):
        from memory.setup import setup_cursor
        setup_cursor(str(cursor_home))
        mcp_path = cursor_home / "mcp.json"
        assert mcp_path.exists()
        data = json.loads(mcp_path.read_text())
        assert "mcpServers" in data
        assert "echovault" in data["mcpServers"]

    def test_does_not_duplicate(self, cursor_home):
        from memory.setup import setup_cursor
        setup_cursor(str(cursor_home))
        setup_cursor(str(cursor_home))
        data = json.loads((cursor_home / "mcp.json").read_text())
        assert "echovault" in data["mcpServers"]

    def test_returns_success_result(self, cursor_home):
        from memory.setup import setup_cursor
        result = setup_cursor(str(cursor_home))
        assert result["status"] == "ok"


@pytest.fixture
def codex_home(tmp_path):
    """Create a temporary ~/.codex directory."""
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    return codex_dir


@pytest.fixture
def codex_home_with_agents_md(codex_home):
    """Create ~/.codex with an existing AGENTS.md."""
    (codex_home / "AGENTS.md").write_text("# My Codex Rules\n\nBe concise.\n")
    return codex_home


class TestCodexSetup:
    def test_creates_agents_md_if_missing(self, codex_home):
        from memory.setup import setup_codex

        setup_codex(str(codex_home))

        agents_path = codex_home / "AGENTS.md"
        assert agents_path.exists()
        content = agents_path.read_text()
        assert "memory context --project" in content
        assert "memory save" in content

    def test_appends_to_existing_agents_md(self, codex_home_with_agents_md):
        from memory.setup import setup_codex

        setup_codex(str(codex_home_with_agents_md))

        content = (codex_home_with_agents_md / "AGENTS.md").read_text()
        assert "# My Codex Rules" in content
        assert "Be concise." in content
        assert "memory context --project" in content

    def test_does_not_duplicate_section(self, codex_home):
        from memory.setup import setup_codex

        setup_codex(str(codex_home))
        setup_codex(str(codex_home))

        content = (codex_home / "AGENTS.md").read_text()
        assert content.count("## EchoVault") == 1

    def test_installs_skill_md(self, codex_home):
        from memory.setup import setup_codex

        setup_codex(str(codex_home))

        skill_path = codex_home / "skills" / "echovault" / "SKILL.md"
        assert skill_path.exists()

    def test_returns_success_result(self, codex_home):
        from memory.setup import setup_codex

        result = setup_codex(str(codex_home))

        assert result["status"] == "ok"


class TestUninstall:
    def test_uninstall_claude_code_removes_mcp_config(self, claude_home):
        from memory.setup import setup_claude_code, uninstall_claude_code
        setup_claude_code(str(claude_home))
        uninstall_claude_code(str(claude_home))
        mcp_path = _mcp_json_path(claude_home)
        if mcp_path.exists():
            data = json.loads(mcp_path.read_text())
            assert "echovault" not in data.get("mcpServers", {})

    def test_uninstall_claude_code_removes_old_hooks(self, claude_home):
        from memory.setup import uninstall_claude_code
        old_settings = {
            "hooks": {
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "memory context"}]}],
                "PreToolUse": [{"hooks": [{"type": "command", "command": "echo hi"}]}],
            }
        }
        (claude_home / "settings.json").write_text(json.dumps(old_settings, indent=2))
        uninstall_claude_code(str(claude_home))
        settings = json.loads((claude_home / "settings.json").read_text())
        assert "UserPromptSubmit" not in settings.get("hooks", {})
        assert "PreToolUse" in settings.get("hooks", {})

    def test_uninstall_cursor_removes_mcp_config(self, cursor_home):
        from memory.setup import setup_cursor, uninstall_cursor
        setup_cursor(str(cursor_home))
        uninstall_cursor(str(cursor_home))
        data = json.loads((cursor_home / "mcp.json").read_text())
        assert "echovault" not in data.get("mcpServers", {})

    def test_uninstall_codex_removes_section(self, codex_home):
        from memory.setup import setup_codex, uninstall_codex
        setup_codex(str(codex_home))
        uninstall_codex(str(codex_home))
        content = (codex_home / "AGENTS.md").read_text()
        assert "## EchoVault" not in content

    def test_uninstall_noop_when_not_installed(self, claude_home):
        from memory.setup import uninstall_claude_code
        result = uninstall_claude_code(str(claude_home))
        assert result["status"] == "ok"
