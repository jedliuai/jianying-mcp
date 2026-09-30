"""Read cached audio titles without fetching assets or exposing signed URLs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3


def find_cached_sound_effects(cache_root: Path, query: str = "", limit: int = 80) -> dict:
    if not 1 <= limit <= 300:
        raise ValueError("limit 范围为 1 到 300。")
    audio_dir = cache_root / "music"
    if not audio_dir.is_dir():
        return {"matched": 0, "effects": [], "issues": ["剪映音频缓存目录不存在。"]}
    files = {path.stem.lower(): path for path in audio_dir.iterdir()
             if path.is_file() and path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}}
    found = {}
    issues = []
    for database in sorted((cache_root / "ressdk_db").rglob("rp.db")):
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
            try:
                rows = connection.execute("SELECT response_body FROM http_cache ORDER BY timestamp DESC LIMIT 2000")
                for (raw,) in rows:
                    try:
                        payload = json.loads(raw)
                    except (ValueError, TypeError):
                        continue
                    stack = [payload]
                    while stack:
                        node = stack.pop()
                        if isinstance(node, list):
                            stack.extend(reversed(node))
                        elif isinstance(node, dict):
                            title = node.get("title") or node.get("name")
                            md5 = node.get("md5") or node.get("file_md5")
                            # Audio payload identity must match an existing file;
                            # metadata for animations or absent downloads is ignored.
                            if (isinstance(title, str) and isinstance(md5, str)
                                    and re.fullmatch(r"[a-fA-F0-9]{32}", md5)):
                                key = md5.lower()
                                file = files.get(key)
                                if file and key not in found:
                                    identifier = node.get("id") or node.get("resource_id") or ""
                                    found[key] = {"resource_id": str(identifier), "title": title,
                                                  "path": str(file.resolve()), "md5": key,
                                                  "cached": True}
                            stack.extend(child for child in reversed(list(node.values()))
                                         if isinstance(child, (list, dict)))
            finally:
                connection.close()
        except sqlite3.Error:
            # Never echo database paths, account IDs, raw payloads or URLs.
            issues.append("一个剪映资源数据库暂不可读，已跳过。")
    matches = sorted((item for item in found.values() if query.casefold() in item["title"].casefold()),
                     key=lambda item: (item["title"], item["resource_id"]))
    return {"matched": len(matches), "effects": matches[:limit], "issues": issues,
            "note": "仅列出剪映已经下载到本机的音效；不会联网下载，也不会更改会员状态。"}
