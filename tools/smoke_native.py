"""Generate an unpublished integration-test copy; source stays untouched."""
import json
from pathlib import Path
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jianying_bridge.core import Bridge, save_json


def main():
    bridge = Bridge()
    source_name = sys.argv[1]
    source = bridge.source(source_name)
    original = bridge.fingerprints(source)
    audio = bridge.work / "smoke-assets/codec-test.wav"
    audio.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(audio), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(8000)
        file.writeframes(struct.pack("<h", 100) * 1600)
    plan = bridge.prepare(source_name, "接入验证副本-未发布", [{"path": str(audio), "start_seconds": 1,
                         "volume": 0.2, "fade_in_seconds": 0.03, "fade_out_seconds": 0.05, "label": "仅用于接入测试"}])
    result = bridge.build(plan["plan_id"])
    assert bridge.fingerprints(source) == original
    result["source_files_unchanged"] = True
    result["smoke_test_only"] = True
    save_json(bridge.work / "native-smoke.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
