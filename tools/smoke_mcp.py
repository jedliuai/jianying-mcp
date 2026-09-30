"""Exercise the real stdio MCP handshake and read-only tools."""
import asyncio
import argparse
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, help="使用插件实际 .mcp.json 测试，不依赖工作目录")
    args = parser.parse_args()
    if args.plugin:
        config = json.loads((args.plugin / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["jianying-local"]
        params = StdioServerParameters(command=config["command"], args=config["args"],
                                      cwd=str(Path.home()), env=config.get("env"))
    else:
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "run_mcp.py")],
                                      cwd=str(Path.home()), env={"PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("list_jianying_drafts", {"limit": 1})
            assert not result.isError
            payload = json.loads(result.content[0].text)
            guide = await session.call_tool("get_jianying_sound_design_guide", {})
            assert not guide.isError
            guidance = json.loads(guide.content[0].text)
            assert guidance["track_layout"]["default"] == "single"
            print(json.dumps({"handshake": True, "tools": [t.name for t in tools.tools],
                              "list_success": True, "draft_total": payload["total"],
                              "guide_success": True, "cached_presets": len(guidance["cached_presets"])}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
