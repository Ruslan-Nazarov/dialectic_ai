"""Command line.

    python -m dialectic_world build "описание области" [--model openai:gpt-5] [--worlds worlds] [--trace path]
    python -m dialectic_world show "описание области" [--version N] [--worlds worlds]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from dialectic_world import Context, Settings, WorldAdapter, WorldStore, build_world
from dialectic_world.llm import build_llm
from dialectic_world.trace import Trace


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles otherwise break Cyrillic
    load_dotenv()
    parser = argparse.ArgumentParser(prog="dialectic_world")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("domain")
    b.add_argument("--model", default=Settings.builder_model)
    b.add_argument("--worlds", default="worlds")
    b.add_argument("--trace")
    s = sub.add_parser("show")
    s.add_argument("domain")
    s.add_argument("--version", type=int)
    s.add_argument("--worlds", default="worlds")
    args = parser.parse_args()

    store = WorldStore(args.worlds)
    if args.cmd == "show":
        print(WorldAdapter(store.load(args.domain, args.version), max_chars=10**6).brief())
        return
    settings = Settings(builder_model=args.model)
    llm = build_llm(args.model)
    trace = Trace(args.trace or Path(args.worlds) / "traces" / "build.jsonl")
    world = asyncio.run(build_world(args.domain, Context(llm=llm, settings=settings, trace=trace), store))
    print(WorldAdapter(world, max_chars=10**6).brief())
    print("\n" + json.dumps({"status": world.status, "version": world.version, "processes": len(world.processes),
                             "calls": llm.usage.calls, "tokens": llm.usage.total}, ensure_ascii=False))


if __name__ == "__main__":
    main()
