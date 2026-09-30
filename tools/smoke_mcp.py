"""Exercise the real stdio MCP handshake and read-only tools."""
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "run_mcp.py")],
                                  cwd=str(Path.home()), env={"PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("list_jianying_drafts", {"limit": 1})
            assert not result.isError
            payload = json.loads(result.content[0].text)
            print(json.dumps({"handshake": True, "tools": [t.name for t in tools.tools],
                              "list_success": True, "draft_total": payload["total"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
