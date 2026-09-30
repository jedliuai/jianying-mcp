from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager

import pyJianYingDraft as draft
from pyJianYingDraft.draft_codec import load_json_object_with_codec, write_json_object_with_codec
from pyJianYingDraft.draft_registration import DraftFolderRegistration

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".wma", ".aiff"}
FILE_KEYS = {"path", "file_Path", "font_path", "resource_path", "draft_fold_path",
             "draft_root_path", "draft_json_file", "draft_cover", "cover_path"}


class BridgeError(ValueError):
    pass


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json_text(data), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def valid_name(name: str) -> str:
    if (not name or name != name.strip() or name.endswith(".") or len(name) > 100
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name in {".", ".."}
            or re.match(r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)", name, re.I)):
        raise BridgeError("草稿名称必须是合法的 Windows 文件夹名，不能包含路径。")
    return name


def within(path: Path, root: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise BridgeError("路径必须位于指定工作目录内。")
    return path


def remap_paths(value, old: Path, new: Path):
    """Only change known file fields. Never reserialize subtitle content."""
    result = copy.deepcopy(value)
    old_prefix = str(old).replace("\\", "/").rstrip("/")

    def walk(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in FILE_KEYS and isinstance(child, str):
                    normalized = child.replace("\\", "/")
                    if normalized.casefold().startswith(old_prefix.casefold() + "/"):
                        item[key] = new.as_posix() + normalized[len(old_prefix):]
                    elif normalized.casefold() == old_prefix.casefold():
                        item[key] = new.as_posix()
                elif isinstance(child, (list, dict)):
                    walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(result)
    return result


def check_preserved(original, edited, source: Path, target: Path, *, legacy=False):
    expected = remap_paths(original, source, target)
    original_tracks = expected.get("tracks", [])
    if edited.get("tracks", [])[:len(original_tracks)] != original_tracks:
        raise BridgeError("原有轨道发生变化，停止交付。")
    for kind, materials in expected.get("materials", {}).items():
        actual = edited.get("materials", {}).get(kind, [])
        if isinstance(materials, list):
            if actual[:len(materials)] != materials:
                raise BridgeError(f"原有 {kind} 素材发生变化，停止交付。")
        elif actual != materials:
            raise BridgeError(f"原有 {kind} 数据发生变化。")
    for key, value in expected.items():
        if key in {"tracks", "materials"} or (legacy and key == "id"):
            continue
        if edited.get(key) != value:
            raise BridgeError(f"原有工程字段 {key} 发生变化，停止交付。")
    return {"original_tracks_preserved": len(original_tracks),
            "original_segments_preserved": sum(len(t.get("segments", [])) for t in original_tracks),
            "original_materials_preserved": sum(len(v) for v in expected.get("materials", {}).values() if isinstance(v, list))}


def us(value, field: str, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BridgeError(f"{field} 必须是有限数字，单位为秒。")
    number = round(value * 1_000_000)
    if number < 0 or (positive and number <= 0):
        raise BridgeError(f"{field} 的时间范围不合法。")
    return number


class Bridge:
    def __init__(self, config=None):
        config_path = Path(os.environ.get("JIANYING_BRIDGE_CONFIG", PROJECT_ROOT / "local.config.json"))
        if config is None:
            config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        self.user_data = Path(config.get("user_data", local / "JianyingPro/User Data")).resolve()
        configured_root = os.environ.get("JIANYING_DRAFT_ROOT", config.get("draft_root"))
        if not configured_root:
            setting = self.user_data / "Config/globalSetting"
            if setting.exists():
                match = re.search(r"^currentCustomDraftPath=(.+)$", setting.read_text(encoding="utf-8-sig"), re.M)
                if match:
                    configured_root = match.group(1).strip().replace("\\\\", "\\")
        self.draft_root = Path(configured_root or self.user_data / "Projects/com.lveditor.draft").resolve()
        install_dir = os.environ.get("JIANYING_INSTALL_DIR", config.get("install_dir"))
        if not install_dir:
            raise BridgeError("请在 local.config.json 设置 install_dir，指向本机剪映版本目录。")
        self.install_dir = Path(install_dir).resolve()
        self.work = Path(config.get("work_root", PROJECT_ROOT / "work")).resolve()
        self.codec = draft.JianyingDraftCryptoCodec(draft.DraftCryptoConfig(
            jy_install_dir=str(self.install_dir), timeout=30, isolated=True,
            validate_roundtrip=True, backup=False))
        self.index = self.user_data / "Projects/com.lveditor.draft/root_meta_info.json"

    def read(self, path: Path):
        return load_json_object_with_codec(path, content_codec=self.codec)

    def write(self, path: Path, data, encrypted: bool):
        write_json_object_with_codec(path, data, content_codec=self.codec if encrypted else None)

    @staticmethod
    def running():
        if os.name != "nt":
            return []
        proc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe", "/FO", "CSV", "/NH"],
                              capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if proc.returncode:
            raise BridgeError("无法检查剪映运行状态，暂不允许登记草稿。")
        rows = csv.reader(io.StringIO(proc.stdout.decode("utf-8", errors="replace")))
        return [row[1] for row in rows if len(row) > 1 and row[0].casefold() == "jianyingpro.exe"]

    def doctor(self):
        dll = self.install_dir / "videoeditor.dll"
        return {"platform": os.name, "draft_root": str(self.draft_root),
                "draft_root_exists": self.draft_root.is_dir(), "install_dir": str(self.install_dir),
                "native_codec_exists": dll.is_file(), "native_codec_sha256": digest(dll.read_bytes()) if dll.is_file() else None,
                "index_exists": self.index.is_file(), "jianying_processes": self.running(),
                "transport": "stdio", "edit_mode": "editable_draft_copy",
                "note": "doctor 仅检查环境；草稿读写兼容性由 inspect/build 的实际结果确认。"}

    def source(self, name):
        path = within(self.draft_root / valid_name(name), self.draft_root)
        if not path.is_dir():
            raise BridgeError(f"找不到草稿：{name}")
        return path

    def list_drafts(self, limit=20):
        if not 1 <= limit <= 200:
            raise BridgeError("limit 范围为 1 到 200。")
        candidates = []
        for p in self.draft_root.iterdir():
            if p.is_dir() and not p.name.startswith(".") and any((p / f).exists() for f in ["draft_info.json", "draft_content.json"]):
                candidates.append(p)
        def modified(p):
            return max([p.stat().st_mtime] + [(p / f).stat().st_mtime for f in ["draft_info.json", "draft_content.json"] if (p / f).exists()])
        candidates.sort(key=modified, reverse=True)
        return {"total": len(candidates), "drafts": [{"name": p.name, "modified": modified(p)} for p in candidates[:limit]]}

    @staticmethod
    def layout(source):
        project = source / "Timelines/project.json"
        if project.exists():
            data = json.loads(project.read_bytes())
            timeline_id = data.get("main_timeline_id")
            if not isinstance(timeline_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", timeline_id):
                raise BridgeError("主时间线 ID 格式不支持。")
            directory = source / "Timelines" / timeline_id
            for name in ["draft_info.json", "draft_content.json"]:
                if (directory / name).is_file():
                    return directory / name, project
            raise BridgeError("多时间线工程的主时间线文件缺失。")
        for name in ["draft_info.json", "draft_content.json"]:
            if (source / name).exists():
                return source / name, None
        raise BridgeError("草稿主文件缺失。")

    @staticmethod
    def core_files(source):
        names = {"draft_content.json", "draft_info.json", "draft_meta_info.json"}
        files = [p for p in source.rglob("*.json") if p.name in names and ".backup" not in p.parts]
        project = source / "Timelines/project.json"
        if project.exists():
            files.append(project)
        return sorted(files)

    def fingerprints(self, source):
        return {p.relative_to(source).as_posix(): digest(p.read_bytes()) for p in self.core_files(source)}

    def inspect(self, name, include_segments=False, limit=80, offset=0):
        if not 1 <= limit <= 500 or offset < 0:
            raise BridgeError("片段分页参数不合法。")
        source = self.source(name)
        timeline, project = self.layout(source)
        data, encrypted = self.read(timeline)
        result = {"name": name, "encrypted": encrypted, "duration_seconds": data.get("duration", 0) / 1e6,
                  "timeline_file": timeline.relative_to(source).as_posix(), "multi_timeline": bool(project),
                  "tracks": [{"id": t.get("id"), "type": t.get("type"), "name": t.get("name"),
                              "segments": len(t.get("segments", []))} for t in data.get("tracks", [])]}
        if include_segments:
            texts = {m.get("id"): m.get("content") for m in data.get("materials", {}).get("texts", [])}
            segments = []
            for track in data.get("tracks", []):
                for seg in track.get("segments", []):
                    timerange = seg.get("target_timerange", {})
                    item = {"track_id": track.get("id"), "type": track.get("type"), "id": seg.get("id"),
                            "start_seconds": timerange.get("start", 0) / 1e6, "duration_seconds": timerange.get("duration", 0) / 1e6}
                    content = texts.get(seg.get("material_id"))
                    if content:
                        try:
                            item["text"] = json.loads(content).get("text", "")
                        except (ValueError, AttributeError):
                            pass
                    segments.append(item)
            segments.sort(key=lambda s: s["start_seconds"])
            result.update(segments_total=len(segments), offset=offset, segments=segments[offset:offset+limit])
        return result

    def list_audio(self, directory, limit=100):
        root = Path(directory).expanduser().resolve()
        if not root.is_dir() or not 1 <= limit <= 300:
            raise BridgeError("音效目录不存在，或 limit 不在 1 到 300。")
        files = []
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES:
                files.append({"path": str(p), "name": p.name})
                if len(files) >= limit:
                    break
        return {"files": files, "limit": limit}

    def cached_sound_effects(self, query="", limit=80):
        from .sound_cache import find_cached_sound_effects
        cache = self.user_data / "Cache"
        setting = self.user_data / "Config/globalSetting"
        if setting.exists():
            match = re.search(r"^currentCachePath=(.+)$", setting.read_text(encoding="utf-8-sig"), re.M)
            if match:
                cache = Path(match.group(1).strip().replace("\\\\", "\\"))
        return find_cached_sound_effects(cache, query, limit)

    def prepare(self, source_name, new_name, effects):
        source = self.source(source_name)
        valid_name(new_name)
        if (self.draft_root / new_name).exists() or new_name.casefold() == source_name.casefold():
            raise BridgeError("副本名称已存在或与原草稿相同，请换一个新名称。")
        if not isinstance(effects, list) or not 1 <= len(effects) <= 500:
            raise BridgeError("effects 必须包含 1 到 500 个音效。")
        fingerprints = self.fingerprints(source)
        timeline, project = self.layout(source)
        content, _ = self.read(timeline)
        duration = content.get("duration", 0)
        prepared = []
        for effect in effects:
            if not isinstance(effect, dict) or "path" not in effect:
                raise BridgeError("每个音效必须包含 path 和 start_seconds。")
            unknown = set(effect) - {"path", "start_seconds", "source_start_seconds", "duration_seconds", "volume", "fade_in_seconds", "fade_out_seconds", "label"}
            if unknown:
                raise BridgeError(f"不支持的音效字段：{sorted(unknown)}")
            path = Path(effect["path"]).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in AUDIO_SUFFIXES:
                raise BridgeError(f"音效必须是本地音频文件：{path}")
            audio = draft.AudioMaterial(str(path))
            start = us(effect.get("start_seconds"), "start_seconds")
            source_start = us(effect.get("source_start_seconds", 0), "source_start_seconds")
            length = us(effect["duration_seconds"], "duration_seconds", positive=True) if "duration_seconds" in effect else audio.duration - source_start
            if length <= 0 or source_start + length > audio.duration:
                raise BridgeError(f"截取时间超出了音效素材时长：{path.name}")
            if start + length > duration:
                raise BridgeError("音效不能超出原工程时长；请缩短音效或修改起始时间。")
            volume = effect.get("volume", 1.0)
            if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or not 0 <= volume <= 2:
                raise BridgeError("volume 范围为 0 到 2，1 表示原始音量。")
            fade_in = us(effect.get("fade_in_seconds", 0), "fade_in_seconds")
            fade_out = us(effect.get("fade_out_seconds", 0), "fade_out_seconds")
            if fade_in + fade_out > length:
                raise BridgeError("淡入和淡出总时长不能超过音效片段时长。")
            label = effect.get("label", path.stem)
            if not isinstance(label, str) or not label.strip() or len(label) > 100:
                raise BridgeError("音效 label 必须为 1 到 100 字符。")
            prepared.append({"path": str(path), "sha256": digest(path.read_bytes()), "start_us": start,
                             "source_start_us": source_start, "duration_us": length, "volume": volume,
                             "fade_in_us": fade_in, "fade_out_us": fade_out, "label": label})
        if self.fingerprints(source) != fingerprints:
            raise BridgeError("读取期间原工程发生变化，请保存剪映后重新准备。")
        plan_id = uuid.uuid4().hex
        plan = {"plan_id": plan_id, "source_name": source_name, "source_path": str(source), "new_name": new_name,
                "source_fingerprints": fingerprints, "timeline_relative": timeline.relative_to(source).as_posix(),
                "legacy": not bool(project), "duration_us": duration, "effects": prepared}
        save_json(self.work / "plans" / f"{plan_id}.json", plan)
        return {"plan_id": plan_id, "source_name": source_name, "new_name": new_name,
                "original_duration_seconds": duration / 1e6, "new_audio_tracks": len(prepared),
                "effects": [{"label": e["label"], "start_seconds": e["start_us"] / 1e6,
                             "duration_seconds": e["duration_us"] / 1e6, "volume": e["volume"]} for e in prepared]}

    def plan(self, plan_id):
        if not re.fullmatch(r"[a-f0-9]{32}", plan_id):
            raise BridgeError("plan_id 格式不合法。")
        path = self.work / "plans" / f"{plan_id}.json"
        if not path.is_file():
            raise BridgeError("找不到准备好的音效计划。")
        return json.loads(path.read_text(encoding="utf-8"))

    @contextmanager
    def lock(self):
        self.work.mkdir(parents=True, exist_ok=True)
        path = self.work / ".bridge.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise BridgeError("另一个草稿写入操作尚未完成。") from exc
        try:
            os.write(fd, str(os.getpid()).encode())
            yield
        finally:
            os.close(fd)
            path.unlink(missing_ok=True)

    @staticmethod
    def reject_links(directory):
        for root, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                path = Path(root) / name
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise BridgeError("草稿包含符号链接或目录联接，不能安全地复制编辑。")

    @staticmethod
    def semantic_hash(data, directory):
        normalized = remap_paths(data, directory, Path("PROJECT"))
        return digest(json.dumps(normalized, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())

    def build(self, plan_id):
        with self.lock():
            plan = self.plan(plan_id)
            source = self.source(plan["source_name"])
            if self.fingerprints(source) != plan["source_fingerprints"]:
                raise BridgeError("原草稿已更新，旧计划失效；请重新 prepare。")
            if (self.draft_root / plan["new_name"]).exists():
                raise BridgeError("副本草稿名称已存在。")
            self.reject_links(source)
            build_id = uuid.uuid4().hex
            build_dir = self.work / "builds" / build_id
            target = build_dir / plan["new_name"]
            build_dir.mkdir(parents=True)
            try:
                shutil.copytree(source, target, ignore=shutil.ignore_patterns(".backup"))
                if self.fingerprints(source) != plan["source_fingerprints"] or self.fingerprints(target) != plan["source_fingerprints"]:
                    raise BridgeError("复制过程中原工程发生变化，请保存工程后重新准备。")
                baseline = build_dir / "baseline"
                files = {}
                originals = {}
                for relative in plan["source_fingerprints"]:
                    path = target / relative
                    data, encrypted = self.read(path)
                    original_file = baseline / relative
                    original_file.parent.mkdir(parents=True, exist_ok=True)
                    original_file.write_bytes(path.read_bytes())
                    originals[relative] = data
                    files[relative] = {"encrypted": encrypted, "baseline_sha256": digest(path.read_bytes())}
                relative = plan["timeline_relative"]
                original = originals[relative]
                main = remap_paths(original, source, target)
                additions = draft.ScriptFile(1920, 1080, 30, False)
                embedded_audio = []
                for number, effect in enumerate(plan["effects"], 1):
                    audio_source = Path(effect["path"])
                    audio_relative = Path("bridge_audio") / build_id / f"{number:03d}_{audio_source.name}"
                    copied = target / audio_relative
                    copied.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(audio_source, copied)
                    if digest(copied.read_bytes()) != effect["sha256"]:
                        raise BridgeError("音效文件已更新，旧计划失效，请重新 prepare。")
                    material = draft.AudioMaterial(str(copied), material_name=effect["label"])
                    track_name = f"音效 {number:03d} · {effect['label']}"
                    track_ref = additions.append_track(draft.TrackSpec(draft.TrackType.audio, track_name))
                    segment = draft.AudioSegment(material, draft.Timerange(effect["start_us"], effect["duration_us"]),
                                                 source_timerange=draft.Timerange(effect["source_start_us"], effect["duration_us"]),
                                                 volume=effect["volume"])
                    if effect["fade_in_us"] or effect["fade_out_us"]:
                        segment.add_fade(effect["fade_in_us"], effect["fade_out_us"])
                    additions.add_segment(segment, track_ref)
                    embedded_audio.append({"relative": audio_relative.as_posix(), "sha256": effect["sha256"]})
                generated = json.loads(additions.dumps())
                original_track_count = len(main["tracks"])
                for i, track in enumerate(generated["tracks"], original_track_count):
                    for segment in track["segments"]:
                        segment["render_index"] = i
                    main["tracks"].append(track)
                for kind, values in generated["materials"].items():
                    if values:
                        main["materials"].setdefault(kind, []).extend(values)
                new_draft_id = str(uuid.uuid4()).upper()
                if plan["legacy"]:
                    main["id"] = new_draft_id
                preservation = check_preserved(original, main, source, target, legacy=plan["legacy"])
                aliases = {}
                main_hash = plan["source_fingerprints"][relative]
                for sibling in [target, (target / relative).parent]:
                    for candidate in sibling.iterdir():
                        if candidate.is_file() and candidate.name in {"draft_content.json", "draft_info.json", "draft_content.json.bak", "draft_info.json.bak", "template-2.tmp"}:
                            rel = candidate.relative_to(target).as_posix()
                            if rel != relative:
                                if digest(candidate.read_bytes()) == main_hash:
                                    aliases[rel] = relative
                                elif candidate.name in {"draft_content.json", "draft_info.json"}:
                                    raise BridgeError("根草稿与主时间线内容不一致，请先在剪映保存工程。")
                now = time.time_ns() // 1000
                for rel, data in originals.items():
                    updated = main if rel == relative or rel in aliases else remap_paths(data, source, target)
                    if rel == "draft_meta_info.json":
                        DraftFolderRegistration(str(self.draft_root)).sync_draft_materials(updated, additions)
                        updated.update(draft_id=new_draft_id, draft_name=plan["new_name"],
                                       draft_fold_path=target.as_posix(), draft_root_path=self.draft_root.as_posix(),
                                       tm_draft_create=now, tm_draft_modified=now, tm_duration=plan["duration_us"])
                        updated["cloud_draft_sync"] = False
                        for field in ["tm_draft_cloud_entry_id", "tm_draft_cloud_parent_entry_id", "tm_draft_cloud_space_id", "tm_draft_cloud_user_id"]:
                            if field in updated:
                                updated[field] = -1
                    elif rel == "Timelines/project.json":
                        updated["id"] = str(uuid.uuid4()).upper()
                        updated["create_time"] = now
                        updated["update_time"] = now
                    self.write(target / rel, updated, files[rel]["encrypted"])
                    files[rel]["expected_hash"] = self.semantic_hash(updated, target)
                for alias, master in aliases.items():
                    shutil.copy2(target / master, target / alias)
                # Rebase sidecar file references, while keeping arbitrary text untouched.
                for path in target.rglob("*.json"):
                    if path.relative_to(target).as_posix() in files:
                        continue
                    try:
                        data = json.loads(path.read_bytes())
                    except (ValueError, UnicodeError):
                        continue
                    updated = remap_paths(data, source, target)
                    if updated != data:
                        save_json(path, updated)
                manifest = {"build_id": build_id, "plan_id": plan_id, "name": plan["new_name"],
                            "source_name": plan["source_name"], "source_path": str(source),
                            "source_fingerprints": plan["source_fingerprints"], "timeline_relative": relative,
                            "legacy": plan["legacy"], "draft_id": new_draft_id, "files": files,
                            "aliases": aliases, "embedded_audio": embedded_audio,
                            "new_track_ids": [t["id"] for t in generated["tracks"]], "preservation": preservation}
                save_json(build_dir / "manifest.json", manifest)
                result = self.verify(build_id)
                if self.fingerprints(source) != plan["source_fingerprints"]:
                    raise BridgeError("原工程在构建时更新，请重新准备。")
                return {**result, "draft_path": str(target), "published": False,
                        "next": "保存当前剪映工程并退出剪映后，调用 publish_build 登记这个副本。"}
            except Exception:
                # Only this invocation's new, resolved workspace directory is removed.
                within(build_dir, self.work / "builds")
                shutil.rmtree(build_dir)
                raise

    def load_build(self, build_id):
        if not re.fullmatch(r"[a-f0-9]{32}", build_id):
            raise BridgeError("build_id 格式不合法。")
        directory = within(self.work / "builds" / build_id, self.work / "builds")
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        valid_name(manifest["name"])
        return directory, manifest

    def verify(self, build_id, *, physical=None, logical=None):
        directory, manifest = self.load_build(build_id)
        physical = physical or directory / manifest["name"]
        logical = logical or physical
        self.reject_links(physical)
        for relative, record in manifest["files"].items():
            file = within(physical / relative, physical)
            data, encrypted = self.read(file)
            if encrypted != record["encrypted"] or self.semantic_hash(data, logical) != record["expected_hash"]:
                raise BridgeError(f"构建文件验证失败：{relative}")
            baseline = within(directory / "baseline" / relative, directory / "baseline")
            if digest(baseline.read_bytes()) != record["baseline_sha256"]:
                raise BridgeError("原始快照校验失败。")
        relative = manifest["timeline_relative"]
        original, _ = self.read(directory / "baseline" / relative)
        edited, _ = self.read(physical / relative)
        preservation = check_preserved(original, edited, Path(manifest["source_path"]), logical, legacy=manifest["legacy"])
        missing_media = []
        for kind in ["videos", "audios"]:
            for material in edited.get("materials", {}).get(kind, []):
                value = material.get("path", "")
                if not value or value.startswith(("<", "http://", "https://")) or material.get("type") == "music":
                    continue
                file = Path(value)
                if file.is_absolute() and file.is_relative_to(logical):
                    file = physical / file.relative_to(logical)
                elif not file.is_absolute():
                    file = physical / file
                if not file.is_file():
                    missing_media.append(value)
        if missing_media:
            raise BridgeError("本地音视频素材缺失，请先在剪映定位素材：" + "; ".join(missing_media[:10]))
        extra = edited["tracks"][len(original["tracks"]):]
        if [t.get("id") for t in extra] != manifest["new_track_ids"] or any(t.get("type") != "audio" or len(t.get("segments", [])) != 1 for t in extra):
            raise BridgeError("新增音效轨道验证失败。")
        for audio in manifest["embedded_audio"]:
            file = within(physical / audio["relative"], physical)
            if digest(file.read_bytes()) != audio["sha256"]:
                raise BridgeError("音效素材丢失或被修改。")
        for alias, master in manifest["aliases"].items():
            if (physical / alias).read_bytes() != (physical / master).read_bytes():
                raise BridgeError("主时间线的镜像文件不同步。")
        return {"build_id": build_id, "name": manifest["name"], "verified": True,
                **preservation, "added_audio_tracks": len(extra),
                "original_duration_seconds": edited["duration"] / 1e6,
                "note": "已验证工程结构、音效文件和加密读写；剪映打开、播放、保存后的验收仍需进行。"}

    def publish(self, build_id):
        with self.lock():
            if self.running():
                raise BridgeError("请先保存工程并正常退出剪映。首页索引只能在剪映退出后更新。")
            self.verify(build_id)
            directory, manifest = self.load_build(build_id)
            stage = directory / manifest["name"]
            final = within(self.draft_root / manifest["name"], self.draft_root)
            if final.exists():
                raise BridgeError("同名草稿已存在；登记操作不覆盖任何草稿。")
            if not self.index.exists():
                raise BridgeError("首页索引不存在，请先在剪映创建并保存一个工程。")
            index_before = self.index.read_bytes()
            payload = json.loads(index_before)
            entries = payload.get("all_draft_store")
            if not isinstance(entries, list):
                raise BridgeError("剪映首页索引结构不支持。")
            if any(e.get("draft_id") == manifest["draft_id"] for e in entries):
                raise BridgeError("新草稿 ID 已经登记。")
            temporary = within(self.draft_root / f".bridge-{uuid.uuid4().hex}", self.draft_root)
            index_replaced = False
            moved = False
            try:
                shutil.copytree(stage, temporary)
                for relative, record in manifest["files"].items():
                    data, _ = self.read(temporary / relative)
                    self.write(temporary / relative, remap_paths(data, stage, final), record["encrypted"])
                for alias, master in manifest["aliases"].items():
                    shutil.copy2(temporary / master, temporary / alias)
                for path in temporary.rglob("*.json"):
                    if path.relative_to(temporary).as_posix() in manifest["files"]:
                        continue
                    try:
                        data = json.loads(path.read_bytes())
                    except (ValueError, UnicodeError):
                        continue
                    updated = remap_paths(data, stage, final)
                    if updated != data:
                        save_json(path, updated)
                verification = self.verify(build_id, physical=temporary, logical=final)
                content, _ = self.read(temporary / manifest["timeline_relative"])
                meta, _ = self.read(temporary / "draft_meta_info.json")
                registration = DraftFolderRegistration(str(self.draft_root))
                now = time.time_ns() // 1000
                entry = registration.build_root_meta_entry(
                    existing_entry=None, draft_json_file=str(final / "draft_content.json" if (temporary / "draft_content.json").exists() else final / "draft_info.json"),
                    draft_name=manifest["name"], draft_path=str(final), draft_id=manifest["draft_id"],
                    draft_new_version=meta.get("draft_new_version", ""), tm_draft_create=now,
                    tm_draft_modified=now, tm_duration=content["duration"],
                    timeline_materials_size=meta.get("draft_timeline_materials_size_", 0))
                entries.insert(0, entry)
                backup = self.work / "index_backups" / f"{build_id}-{uuid.uuid4().hex}-root_meta_info.json"
                backup.parent.mkdir(parents=True, exist_ok=True)
                with backup.open("xb") as file:
                    file.write(index_before)
                if self.running() or self.index.read_bytes() != index_before:
                    raise BridgeError("剪映重新启动或首页索引已更新，停止登记。")
                os.rename(temporary, final)
                moved = True
                save_json(self.index, payload)
                index_replaced = True
            except Exception:
                # Never remove a registered draft; rollback only our unpublished copy.
                if not index_replaced:
                    cleanup = final if moved else temporary
                    if cleanup.exists():
                        within(cleanup, self.draft_root)
                        shutil.rmtree(cleanup)
                raise
            result = {**verification, "published": True, "draft_path": str(final),
                      "index_backup": str(backup), "next": "启动剪映，在首页打开这个副本，播放音效并保存，再确认可继续调整。"}
            save_json(directory / "published.json", result)
            return result
