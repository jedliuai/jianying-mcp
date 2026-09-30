import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/jianying-mcp"
SERVER = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["jianying-local"]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows plugin launcher")


def test_install_scripts_parse_in_windows_powershell_51():
    script = """
$errorsFound = 0
foreach ($name in @('setup.ps1', 'register-mcp.ps1', 'install-plugin.ps1')) {
    $parseTokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $env:JIANYING_TEST_REPO $name), [ref]$parseTokens, [ref]$parseErrors) | Out-Null
    $errorsFound += $parseErrors.Count
    $parseErrors | ForEach-Object { Write-Error $_.Message }
}
exit $errorsFound
"""
    result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                            env={**os.environ, "JIANYING_TEST_REPO": str(ROOT)}, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


def test_installed_plugin_starts_from_other_directory_with_unicode_config(tmp_path):
    local = tmp_path / "本机配置"
    runtime_dir = local / "jianying-mcp"
    runtime_dir.mkdir(parents=True)
    drafts = tmp_path / "空草稿目录"
    drafts.mkdir()
    config = tmp_path / "剪映本机配置.json"
    config.write_text(json.dumps({"install_dir": str(tmp_path / "install"), "draft_root": str(drafts),
                                 "user_data": str(tmp_path / "user"), "work_root": str(tmp_path / "work")}), encoding="utf-8")
    (runtime_dir / "runtime.json").write_text(json.dumps({"python": sys.executable,
        "entry": str(ROOT / "run_mcp.py"), "config": str(config)}, ensure_ascii=False), encoding="utf-8")
    unrelated = tmp_path / "其他工作目录"
    unrelated.mkdir()
    before = config.read_bytes()

    async def exercise():
        params = StdioServerParameters(command=SERVER["command"], args=SERVER["args"],
                                      cwd=str(unrelated), env={**SERVER["env"], "LOCALAPPDATA": str(local)})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "prepare_sound_effects" in {t.name for t in tools.tools}
                guide = await session.call_tool("get_jianying_sound_design_guide", {})
                assert not guide.isError
                payload = json.loads(guide.content[0].text)
                assert payload["track_layout"]["default"] == "single"
                listing = await session.call_tool("list_jianying_drafts", {"limit": 1})
                assert not listing.isError and json.loads(listing.content[0].text)["total"] == 0
                doctor = await session.call_tool("jianying_doctor", {})
                assert not doctor.isError and Path(json.loads(doctor.content[0].text)["draft_root"]) == drafts
    asyncio.run(exercise())
    assert config.read_bytes() == before
    assert list(drafts.iterdir()) == []
    assert not (tmp_path / "work").exists()


@pytest.mark.parametrize("relocated", [False, True])
def test_missing_or_moved_runtime_fails_without_polluting_stdio(tmp_path, relocated):
    local = tmp_path / "appdata"
    runtime_dir = local / "jianying-mcp"
    runtime_dir.mkdir(parents=True)
    if relocated:
        (runtime_dir / "runtime.json").write_text(json.dumps({"python": str(tmp_path / "missing/python.exe"),
            "entry": str(tmp_path / "missing/run_mcp.py"), "config": str(tmp_path / "missing/config.json")}), encoding="utf-8")
    result = subprocess.run([SERVER["command"], *SERVER["args"]], cwd=tmp_path,
                            env={**os.environ, **SERVER["env"], "LOCALAPPDATA": str(local)},
                            capture_output=True, timeout=15)
    assert result.returncode != 0
    assert result.stdout == b""
    assert b"install-plugin.ps1" in result.stderr
