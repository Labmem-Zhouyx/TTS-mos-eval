"""Persistence for rater sessions.

Each rater session is stored as a single JSON file under
``<data_root>/results/``.  Saving is atomic: we write to a temporary file
in the same directory and then rename, so a partially-written file is
never observed by readers.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_lock = threading.Lock()

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(s: str, fallback: str = "rater") -> str:
    s = (s or "").strip()
    if not s:
        return fallback
    cleaned = _SAFE.sub("_", s)
    return cleaned[:32] or fallback


def make_session_id(nickname: str) -> str:
    """Generate a unique-ish session id encoding the nickname."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{ts}_{_slug(nickname)}_{short}"


def results_dir(data_root: Path) -> Path:
    d = data_root / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_path(data_root: Path, session_id: str) -> Path:
    return results_dir(data_root) / f"{session_id}.json"


def load_session(data_root: Path, session_id: str) -> Optional[Dict[str, Any]]:
    p = session_path(data_root, session_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_session(data_root: Path, session_id: str, payload: Dict[str, Any]) -> Path:
    p = session_path(data_root, session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        # atomic write via temp file in the same directory
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        except Exception:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            raise
    return p


def list_sessions(data_root: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    d = results_dir(data_root)
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append(
            {
                "session_id": data.get("session_id", f.stem),
                "nickname": data.get("nickname"),
                "language": data.get("language"),
                "started_at": data.get("started_at"),
                "updated_at": data.get("updated_at"),
                "submitted_at": data.get("submitted_at"),
                "panels_completed": [
                    p["panel"]
                    for p in data.get("panels", [])
                    if p.get("status") == "submitted"
                ],
            }
        )
    return out
