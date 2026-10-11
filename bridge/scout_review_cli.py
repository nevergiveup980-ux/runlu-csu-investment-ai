"""Local CLI for importing Scout scans and recording joint research outcomes.

No network access and no brokerage actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scout_registry import apply_joint_review, ranked_candidates, record_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="RUNLU Scout private research workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import-scan")
    imp.add_argument("file", help="Scout scan JSON file")

    sub.add_parser("list")

    review = sub.add_parser("review")
    review.add_argument("symbol")
    review.add_argument("file", help="Joint research decision JSON file")

    args = parser.parse_args()

    if args.command == "import-scan":
        with open(args.file, "r", encoding="utf-8") as handle:
            result = record_scan(json.load(handle))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "list":
        print(json.dumps(ranked_candidates(), indent=2, ensure_ascii=False))
        return

    if args.command == "review":
        with open(args.file, "r", encoding="utf-8") as handle:
            decision = json.load(handle)
        result = apply_joint_review(args.symbol, decision)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
