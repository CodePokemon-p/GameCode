"""The app starts the real MCP server only when enable_mcp=True."""
from gamecode.tui import GameCodeApp

KEY = "sk-test-key-1234567890abc"


async def test_mcp_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("GAMECODE_API_KEY", raising=False)
    app = GameCodeApp(api_key=KEY, base_dir=tmp_path, config_dir=tmp_path / "cfg")
    async with app.run_test():
        assert app.agent_mgr.mcp is None


async def test_mcp_starts_when_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("GAMECODE_API_KEY", raising=False)
    app = GameCodeApp(
        api_key=KEY, base_dir=tmp_path, config_dir=tmp_path / "cfg", enable_mcp=True
    )
    async with app.run_test():
        assert app.agent_mgr.mcp is not None
        names = {t["name"] for t in app.agent_mgr.mcp.list_tools()}
        assert "write_markdown" in names