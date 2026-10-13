"""Local CLI for Scout research result writeback.

This CLI only stores assistant research in the private registry/archive. It
cannot record user confirmation, promote a candidate, or enable trading.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scout_registry import DEFAULT_REGISTRY, record_assistant_research
from scout_research_writeback import DEFAULT_ARCHIVE, build_result_template


def _load_candidate(symbol: str, registry_path: Path):
    from scout_registry import _read

    registry = _read(registry_path)
    candidate = registry["candidates"].get(symbol.upper())
    if not candidate:
        raise SystemExit("Unknown Scout candidate")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="RUNLU Scout research writeback")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template")
    template.add_argument("symbol")
    template.add_argument("--output")

    writeback = sub.add_parser("writeback")
    writeback.add_argument("file")

    args = parser.parse_args()
    registry_path = Path(args.registry).expanduser()
    archive_path = Path(args.archive).expanduser()

    if args.command == "template":
        candidate = _load_candidate(args.symbol, registry_path)
        packet = build_result_template(candidate)
        rendered = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = Path(args.output).expanduser()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(str(output))
        else:
            print(rendered, end="")
        return

    packet = json.loads(Path(args.file).expanduser().read_text(encoding="utf-8"))
    symbol = str(packet.get("symbol") or "").upper()
    row = record_assistant_research(
        symbol,
        packet,
        registry_path,
        archive_path,
    )
    print(json.dumps({
        "symbol": row["symbol"],
        "stage": row["stage"],
        "researchStatus": row["researchStatus"],
        "researchDigest": row["researchDraft"]["digest"],
        "archiveVersion": row["researchDraft"]["archiveVersion"],
        "userConfirmed": False,
        "tradeEligible": False,
        "brokerSubmissionEnabled": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
