"""FastAPI application for the MOS evaluation tool."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    PanelSubmission,
    SessionStart,
    SessionStartResponse,
    SessionUpdate,
)
from .scanner import (
    get_data_root,
    panel_to_dict,
    resolve_token,
    scan_panels,
)
from .storage import (
    list_sessions,
    load_session,
    make_session_id,
    save_session,
)

logger = logging.getLogger("mos_eval")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def create_app() -> FastAPI:
    app = FastAPI(title="MOS Evaluation Server", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    data_root = get_data_root()
    audio_root = data_root / "audio"
    static_root = _project_root() / "static"

    audio_root.mkdir(parents=True, exist_ok=True)

    # Frontend static files. Audio files are *not* mounted statically so
    # that the on-disk path (which would otherwise leak the system name)
    # is never exposed to the listener; see /audio/{token} below.
    app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(str(static_root / "index.html"))

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {"ok": True, "data_root": str(data_root)}

    @app.get("/api/panels")
    def get_panels() -> Dict[str, Any]:
        # scan_panels registers every audio file under an opaque token;
        # the returned payload only contains /audio/<token> URLs.
        panels = scan_panels(audio_root)
        return {"panels": [panel_to_dict(p) for p in panels]}

    @app.get("/audio/{token}", include_in_schema=False)
    def get_audio(token: str) -> FileResponse:
        path = resolve_token(token)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="audio not found")
        # The HTTP filename is the token, not the original file name, so
        # browsers' "save as" or devtools will not reveal the system id.
        return FileResponse(
            str(path),
            filename=f"{token}{path.suffix}",
            media_type="audio/wav" if path.suffix.lower() == ".wav" else None,
        )

    @app.post("/api/session", response_model=SessionStartResponse)
    def start_session(payload: SessionStart) -> SessionStartResponse:
        session_id = make_session_id(payload.nickname)
        started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        record = {
            "session_id": session_id,
            "nickname": payload.nickname,
            "language": payload.language,
            "notes": payload.notes,
            "started_at": started_at,
            "updated_at": started_at,
            "submitted_at": None,
            "panels": [],
        }
        save_session(data_root, session_id, record)
        return SessionStartResponse(
            session_id=session_id,
            nickname=payload.nickname,
            language=payload.language,
            started_at=started_at,
        )

    @app.get("/api/session/{session_id}")
    def fetch_session(session_id: str) -> Dict[str, Any]:
        rec = load_session(data_root, session_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="session not found")
        return rec

    @app.post("/api/session/update")
    def update_session(payload: SessionUpdate) -> Dict[str, Any]:
        rec = load_session(data_root, payload.session_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="session not found")
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        if payload.nickname is not None:
            rec["nickname"] = payload.nickname
        if payload.language is not None:
            rec["language"] = payload.language

        # merge panels by panel name
        existing: Dict[str, PanelSubmission] = {p["panel"]: p for p in rec.get("panels", [])}
        for panel in payload.panels:
            existing[panel.panel] = panel.dict()
        rec["panels"] = list(existing.values())

        rec["updated_at"] = now
        if payload.final:
            rec["submitted_at"] = now
            # mark every panel without a status as submitted, otherwise keep
            for p in rec["panels"]:
                if p.get("status") != "submitted":
                    p["status"] = "submitted"
        save_session(data_root, payload.session_id, rec)
        return {"ok": True, "session_id": payload.session_id, "submitted_at": rec["submitted_at"]}

    @app.get("/api/sessions")
    def all_sessions() -> Dict[str, Any]:
        return {"sessions": list_sessions(data_root)}

    @app.exception_handler(HTTPException)
    def _http_exc(_, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    logger.info("data root: %s", data_root)
    logger.info("audio root: %s", audio_root)
    return app


app = create_app()
