import json
from pathlib import Path
import struct
import wave

import pytest

from jianying_bridge.core import Bridge, BridgeError, check_preserved, digest, remap_paths, valid_name


def make_audio(path):
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(8000)
        file.writeframes(struct.pack("<h", 200) * 8000)


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / "drafts"
    source = root / "原草稿"
    source.mkdir(parents=True)
    (source / "Resources").mkdir()
    (source / "Resources/clip.mp4").write_bytes(b"unchanged-original-media")
    content = {
        "id": "old-id", "duration": 10_000_000, "fps": 30,
        "canvas_config": {"width": 1080, "height": 1920, "ratio": "9:16", "future_field": {"a": 3}},
        "config": {"future_feature": True}, "unknown_native_field": [1, {"foo": 2}],
        "tracks": [
            {"id": "video", "type": "video", "segments": [{"id": "v1", "material_id": "vm", "render_index": 19, "keyframes": [{"x": 2}]}]},
            {"id": "text", "type": "text", "segments": [{"id": "t1", "future_field": 42}]},
            {"id": "compound", "type": "unknown_compound", "nested": {"native": True}, "segments": []},
        ],
        "materials": {"videos": [{"id": "vm", "path": str(source / "Resources/clip.mp4")}],
                      "texts": [{"id": "tm", "content": '{ "text": "字幕", "styles": [] }'}],
                      "native_future_materials": [{"id": "future", "keep": True}]},
    }
    (source / "draft_content.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    (source / "draft_content.json.bak").write_bytes((source / "draft_content.json").read_bytes())
    (source / "draft_meta_info.json").write_text(json.dumps({"draft_id": "old-id", "draft_name": "旧名", "unknown": 123}), encoding="utf-8")
    user = tmp_path / "user"
    index = user / "Projects/com.lveditor.draft/root_meta_info.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"all_draft_store": [{"draft_id": "old-id", "draft_name": "原草稿"}], "draft_ids": 57, "unknown": {"keep": True}}), encoding="utf-8")
    bridge = Bridge({"draft_root": str(root), "install_dir": str(tmp_path / "install"),
                     "user_data": str(user), "work_root": str(tmp_path / "work")})
    bridge.running = lambda: []
    audio = tmp_path / "click.wav"
    make_audio(audio)
    return bridge, source, content, audio


def prepare(fixture, **overrides):
    bridge, source, content, audio = fixture
    effect = {"path": str(audio), "start_seconds": 2, "volume": 0.5,
              "fade_in_seconds": 0.05, "fade_out_seconds": 0.1, **overrides}
    return bridge.prepare(source.name, "音效副本", [effect])


def test_copy_preserves_unknown_tracks_materials_and_subtitle_text(fixture):
    bridge, source, original, audio = fixture
    before = bridge.fingerprints(source)
    plan = prepare(fixture)
    result = bridge.build(plan["plan_id"])
    target = Path(result["draft_path"])
    edited, _ = bridge.read(target / "draft_content.json")
    assert edited["tracks"][:3] == original["tracks"]
    assert edited["materials"]["texts"] == original["materials"]["texts"]
    assert edited["canvas_config"] == original["canvas_config"]
    assert edited["unknown_native_field"] == original["unknown_native_field"]
    assert edited["materials"]["native_future_materials"] == original["materials"]["native_future_materials"]
    assert edited["materials"]["videos"][0]["path"] == (target / "Resources/clip.mp4").as_posix()
    assert bridge.fingerprints(source) == before
    assert result["added_audio_tracks"] == 1
    seg = edited["tracks"][-1]["segments"][0]
    assert seg["target_timerange"] == {"start": 2_000_000, "duration": 1_000_000}
    assert seg["volume"] == 0.5
    assert edited["duration"] == original["duration"]
    assert (target / "draft_content.json.bak").read_bytes() == (target / "draft_content.json").read_bytes()


def test_overlapping_effects_get_independent_tracks(fixture):
    bridge, source, _, audio = fixture
    plan = bridge.prepare(source.name, "音效副本", [{"path": str(audio), "start_seconds": 2}, {"path": str(audio), "start_seconds": 2.2}])
    result = bridge.build(plan["plan_id"])
    assert result["added_audio_tracks"] == 2
    assert bridge.verify(result["build_id"])["verified"]


@pytest.mark.parametrize("field,value", [
    ("start_seconds", -1), ("start_seconds", float("nan")),
    ("start_seconds", True), ("start_seconds", 10),
    ("duration_seconds", 0), ("duration_seconds", 2),
    ("source_start_seconds", 2), ("volume", float("inf")), ("volume", -1),
    ("fade_out_seconds", 2), ("fade_in_seconds", -0.1), ("start_second", 1),
])
def test_invalid_effects_rejected(fixture, field, value):
    with pytest.raises(BridgeError):
        prepare(fixture, **{field: value})


@pytest.mark.parametrize("name", ["../原草稿", "..", "CON", "con.wav", "bad.", " x", "a/b", "a\\b"])
def test_invalid_names_rejected(name):
    with pytest.raises(BridgeError):
        valid_name(name)


def test_plan_invalidated_by_source_edit(fixture):
    bridge, source, _, _ = fixture
    plan = prepare(fixture)
    (source / "draft_content.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BridgeError, match="旧计划失效"):
        bridge.build(plan["plan_id"])


def test_changed_audio_invalidates_plan_without_leaving_partial_copy(fixture):
    bridge, _, _, audio = fixture
    plan = prepare(fixture)
    audio.write_bytes(b"changed")
    with pytest.raises(BridgeError, match="音效文件已更新"):
        bridge.build(plan["plan_id"])
    assert list((bridge.work / "builds").iterdir()) == []


def test_tampered_build_rejected(fixture):
    bridge, _, _, _ = fixture
    result = bridge.build(prepare(fixture)["plan_id"])
    content = Path(result["draft_path"]) / "draft_content.json"
    edited = json.loads(content.read_bytes())
    edited["tracks"][0]["segments"][0]["render_index"] = 999
    content.write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(BridgeError, match="验证失败"):
        bridge.verify(result["build_id"])


def test_missing_original_local_media_stops_delivery(fixture):
    bridge, source, _, _ = fixture
    (source / "Resources/clip.mp4").unlink()
    with pytest.raises(BridgeError, match="素材缺失"):
        bridge.build(prepare(fixture)["plan_id"])


def test_publish_backs_up_index_rebases_resources_and_preserves_entries(fixture):
    bridge, source, _, _ = fixture
    result = bridge.build(prepare(fixture)["plan_id"])
    index_before = bridge.index.read_bytes()
    original_fingerprints = bridge.fingerprints(source)
    publication = bridge.publish(result["build_id"])
    final = Path(publication["draft_path"])
    index = json.loads(bridge.index.read_bytes())
    assert index["all_draft_store"][1:] == json.loads(index_before)["all_draft_store"]
    assert index["unknown"] == {"keep": True}
    assert index["draft_ids"] == 57
    assert Path(publication["index_backup"]).read_bytes() == index_before
    assert bridge.fingerprints(source) == original_fingerprints
    edited, _ = bridge.read(final / "draft_content.json")
    for audio in edited["materials"]["audios"]:
        assert Path(audio["path"]).is_file()
        assert str(final) in str(Path(audio["path"]))
    assert bridge.verify(result["build_id"])["verified"]
    with pytest.raises(BridgeError, match="同名"):
        bridge.publish(result["build_id"])


def test_publish_refuses_running_editor(fixture):
    bridge, _, _, _ = fixture
    result = bridge.build(prepare(fixture)["plan_id"])
    index_before = bridge.index.read_bytes()
    bridge.running = lambda: ["1234"]
    with pytest.raises(BridgeError, match="正常退出"):
        bridge.publish(result["build_id"])
    assert bridge.index.read_bytes() == index_before


def test_editing_previously_generated_copy_never_overwrites_existing_sound(fixture):
    bridge, source, _, audio = fixture
    first = bridge.build(prepare(fixture)["plan_id"])
    first_publication = bridge.publish(first["build_id"])
    new_source = Path(first_publication["draft_path"])
    first_content, _ = bridge.read(new_source / "draft_content.json")
    first_audio_path = Path(first_content["materials"]["audios"][0]["path"])
    first_hash = digest(first_audio_path.read_bytes())
    plan = bridge.prepare("音效副本", "音效副本-再加一条", [{"path": str(audio), "start_seconds": 3}])
    second = bridge.build(plan["plan_id"])
    second_content, _ = bridge.read(Path(second["draft_path"]) / "draft_content.json")
    old_sound, new_sound = second_content["materials"]["audios"]
    assert old_sound["path"] != new_sound["path"]
    assert digest(Path(old_sound["path"]).read_bytes()) == first_hash
    assert digest(first_audio_path.read_bytes()) == first_hash
    assert second_content["tracks"][:4] == first_content["tracks"]


def test_multitimeline_updates_main_mirrors_and_preserves_other_timelines(fixture):
    bridge, source, original, _ = fixture
    main = source / "Timelines/TIMELINE-1"
    other = source / "Timelines/TIMELINE-2"
    main.mkdir(parents=True)
    other.mkdir()
    (main / "draft_content.json").write_bytes((source / "draft_content.json").read_bytes())
    (other / "draft_content.json").write_text(json.dumps({**original, "id": "other-id"}), encoding="utf-8")
    project = {"id": "old-project", "main_timeline_id": "TIMELINE-1", "timelines": [{"id": "TIMELINE-1"}, {"id": "TIMELINE-2"}], "unknown": True}
    (source / "Timelines/project.json").write_text(json.dumps(project), encoding="utf-8")
    result = bridge.build(prepare(fixture)["plan_id"])
    target = Path(result["draft_path"])
    assert (target / "draft_content.json").read_bytes() == (target / "Timelines/TIMELINE-1/draft_content.json").read_bytes()
    edited_other, _ = bridge.read(target / "Timelines/TIMELINE-2/draft_content.json")
    assert edited_other == remap_paths({**original, "id": "other-id"}, source, target)
    updated_project, _ = bridge.read(target / "Timelines/project.json")
    assert updated_project["timelines"] == project["timelines"]
    assert updated_project["main_timeline_id"] == project["main_timeline_id"]
    bridge.publish(result["build_id"])


def test_preservation_detects_unknown_field_changes(fixture):
    _, source, original, _ = fixture
    edited = remap_paths(original, source, source)
    edited["unknown_native_field"] = []
    with pytest.raises(BridgeError, match="工程字段"):
        check_preserved(original, edited, source, source)
