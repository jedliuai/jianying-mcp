import argparse
import json
import sys

from .core import Bridge, json_text


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="剪映本地 CLI：保留轨道，复制工程，添加音效")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("guide")
    listing = commands.add_parser("list")
    listing.add_argument("--limit", type=int, default=20)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("name")
    inspect.add_argument("--segments", action="store_true")
    inspect.add_argument("--limit", type=int, default=80)
    inspect.add_argument("--offset", type=int, default=0)
    audio = commands.add_parser("audio")
    audio.add_argument("directory")
    audio.add_argument("--limit", type=int, default=100)
    cached = commands.add_parser("cached-audio")
    cached.add_argument("--query", default="")
    cached.add_argument("--limit", type=int, default=80)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("plan_file", help="JSON: source_name, new_name, effects；可设 track_mode、consolidate_track_ids")
    for name in ["build", "verify", "publish"]:
        command = commands.add_parser(name)
        command.add_argument("id", help="build 用 plan_id；verify/publish 用 build_id")
    commands.add_parser("mcp")
    args = parser.parse_args()
    try:
        if args.command == "mcp":
            from .server import main as run_server
            run_server()
            return
        if args.command == "guide":
            from .sound_design import sound_design_guide
            print(json_text(sound_design_guide()))
            return
        bridge = Bridge()
        if args.command == "doctor":
            result = bridge.doctor()
        elif args.command == "list":
            result = bridge.list_drafts(args.limit)
        elif args.command == "inspect":
            result = bridge.inspect(args.name, args.segments, args.limit, args.offset)
        elif args.command == "audio":
            result = bridge.list_audio(args.directory, args.limit)
        elif args.command == "cached-audio":
            result = bridge.cached_sound_effects(args.query, args.limit)
        elif args.command == "prepare":
            with open(args.plan_file, encoding="utf-8-sig") as file:
                plan = json.load(file)
            result = bridge.prepare(plan["source_name"], plan["new_name"], plan["effects"],
                                    plan.get("track_mode", "single"), plan.get("consolidate_track_ids"))
        else:
            result = getattr(bridge, args.command)(args.id)
        print(json_text(result))
    except Exception as exc:
        print(json_text({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
