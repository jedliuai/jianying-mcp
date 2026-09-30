"""Absolute-path entry point, independent of the MCP client's working directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jianying_bridge.server import main

if __name__ == "__main__":
    main()
