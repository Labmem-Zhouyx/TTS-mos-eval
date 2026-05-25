"""One-click entry point for the MOS evaluation server.

Usage:
    python run.py                 # default host 0.0.0.0, port 8000
    python run.py --port 9000     # custom port
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the MOS evaluation server.")
    parser.add_argument("--host", default="0.0.0.0", help="bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="bind port (default 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="enable autoreload (for development only)",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="override data root directory (default: ./data)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    import os

    if args.data_root is not None:
        os.environ["MOS_EVAL_DATA_ROOT"] = str(Path(args.data_root).resolve())
    else:
        os.environ.setdefault("MOS_EVAL_DATA_ROOT", str(project_root / "data"))

    print("=" * 64)
    print(" MOS Evaluation Server")
    print(f" data root : {os.environ['MOS_EVAL_DATA_ROOT']}")
    print(f" listening : http://{args.host}:{args.port}")
    print(" open a browser to the URL above to start rating")
    print("=" * 64)

    uvicorn.run(
        "server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
