"""Read-only compatibility probe. Never writes to the source draft."""
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jianying_bridge.core import Bridge

bridge = Bridge()
if len(sys.argv) != 2:
    raise SystemExit("Usage: python tools/probe_codec.py <draft-folder-name>")
source = bridge.source(sys.argv[1])
codec = bridge.codec
result = {"source": source.name, "checks": []}
main, _ = bridge.layout(source)
for input_file in [main, source / "draft_meta_info.json"]:
    name = input_file.relative_to(source).as_posix()
    raw = input_file.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    data, _ = bridge.read(input_file)
    encoded = codec.encode(json.dumps(data, ensure_ascii=False))
    assert codec.decode(encoded) == data
    assert hashlib.sha256(input_file.read_bytes()).hexdigest() == before
    summary = {"file": name, "roundtrip": True, "source_sha256": before}
    if "tracks" in data:
        summary.update(duration_seconds=data.get("duration", 0) / 1e6,
                       tracks=[{"type": t.get("type"), "name": t.get("name"),
                                "segments": len(t.get("segments", []))} for t in data["tracks"]],
                       material_types={k: len(v) for k, v in data.get("materials", {}).items() if v},
                       content_id=data.get("id"), content_name=data.get("name"))
    else:
        summary.update(meta={k: data.get(k) for k in
                            ["draft_id", "draft_name", "draft_fold_path", "draft_root_path", "tm_duration"]})
    result["checks"].append(summary)
project = source / "Timelines" / "project.json"
if project.exists():
    result["timeline_project"] = json.loads(project.read_bytes())
bridge.work.mkdir(exist_ok=True)
(bridge.work / "codec-probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
