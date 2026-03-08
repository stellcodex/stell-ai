from __future__ import annotations

import argparse
import json

from .ingest import run_ingest
from .self_learning import write_incident, write_solved_case


def main() -> int:
    parser = argparse.ArgumentParser(description="STELL-AI memory tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("query")
    query_parser.add_argument("--top-k", type=int, default=5)

    subparsers.add_parser("daemon")
    subparsers.add_parser("evaluate")

    solved_parser = subparsers.add_parser("record-success")
    solved_parser.add_argument("--name", required=True)
    solved_parser.add_argument("--problem", required=True)
    solved_parser.add_argument("--plan", required=True)
    solved_parser.add_argument("--commands", required=True)
    solved_parser.add_argument("--result", required=True)

    incident_parser = subparsers.add_parser("record-failure")
    incident_parser.add_argument("--name", required=True)
    incident_parser.add_argument("--failure", required=True)
    incident_parser.add_argument("--root-cause", required=True)
    incident_parser.add_argument("--fix-attempt", required=True)

    args = parser.parse_args()

    if args.command == "ingest":
        print(json.dumps(run_ingest(reason="cli"), indent=2))
        return 0

    if args.command == "query":
        from .memory import StellHybridMemory

        with StellHybridMemory() as memory:
            print(json.dumps(memory.retrieve(args.query, top_k=args.top_k), indent=2))
        return 0

    if args.command == "daemon":
        from .daemon import run_forever

        run_forever()
        return 0

    if args.command == "evaluate":
        from .evaluate import run_evaluation

        print(json.dumps(run_evaluation(), indent=2))
        return 0

    if args.command == "record-success":
        path = write_solved_case(args.name, args.problem, args.plan, args.commands, args.result)
        print(str(path))
        return 0

    if args.command == "record-failure":
        path = write_incident(args.name, args.failure, args.root_cause, args.fix_attempt)
        print(str(path))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
