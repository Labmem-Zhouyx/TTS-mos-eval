"""CLI to aggregate rater JSON files into MOS / ABX statistics.

Examples
--------
    python scripts/aggregate.py
    python scripts/aggregate.py --results data/results --output data/reports
    python scripts/aggregate.py --include-drafts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running directly via `python scripts/aggregate.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.analytics import aggregate, load_sessions, write_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate MOS evaluation results.")
    parser.add_argument(
        "--results",
        default=str(ROOT / "data" / "results"),
        help="directory containing rater session JSON files",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "reports"),
        help="output directory for aggregated tables",
    )
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help="include unsubmitted (draft) panels as well",
    )
    args = parser.parse_args()

    results_dir = Path(args.results).resolve()
    output_dir = Path(args.output).resolve()
    if not results_dir.is_dir():
        print(f"[error] results dir not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    sessions = load_sessions(results_dir)
    if not sessions:
        print(f"[warn] no session JSON files in {results_dir}")
    report = aggregate(sessions, include_drafts=args.include_drafts)
    paths = write_all(report, output_dir)

    print("Aggregated:")
    print(f"  sessions: {report.sessions}, raters: {report.raters}")
    print("Outputs:")
    for k, p in paths.items():
        print(f"  {k:8s} {p}")


if __name__ == "__main__":
    main()
