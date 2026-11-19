"""Authenticated HTTP entry point for a long-running RunPod Pod."""

import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.handler import Worker


OUTPUT_FILES = {"audio.wav", "audio.mp3", "audio_raw.wav", "captions.srt", "segments.json"}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    language: Literal["Chinese", "English", "Auto"] = "Auto"
    style: Literal["documentary", "energetic", "calm", "conversational"] = "documentary"
    speed: float = Field(default=1.0, ge=0.75, le=1.5)
    format: Literal["wav", "mp3"] = "wav"
    job_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")


def create_app(worker_factory=Worker, api_token: str | None = None) -> FastAPI:
    token = os.getenv("API_TOKEN", "") if api_token is None else api_token
    inference_lock = Lock()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if not token:
            raise RuntimeError("API_TOKEN must be set for the public Pod HTTP API")
        application.state.worker = worker_factory()
        yield

    application = FastAPI(title="AutoStudio Voice Worker", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def require_token(authorization: str | None = Header(default=None)):
        if not token or not authorization or not secrets.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    @application.get("/health")
    def health(request: Request):
        return {"ok": True, "ready": hasattr(request.app.state, "worker")}

    @application.post("/tts", dependencies=[Depends(require_token)])
    def tts(body: TTSRequest, request: Request):
        if not body.text.strip():
            raise HTTPException(status_code=422, detail="text must contain speech")
        if not inference_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="GPU worker is busy")
        try:
            result = request.app.state.worker.handle({"input": {
                "task_type": "tts_generate",
                "voice_id": "tech_narrator" if body.voice in {None, "default"} else body.voice,
                "text": body.text,
                "language": body.language,
                "style": body.style,
                "speed": body.speed,
                "format": body.format,
            }})
        finally:
            inference_lock.release()
        if result["status"] != "completed":
            error_code = 503 if result.get("error_type") == "RuntimeError" else 500 if result.get("error_type") == "ProcessingError" else 400
            raise HTTPException(status_code=error_code, detail=result["message"])
        if result["storage_mode"] == "local":
            root = request.app.state.worker.settings.output_dir.resolve()
            for name in ("audio", "wav", "raw_wav", "captions", "segments"):
                path = Path(result[f"{name}_path"]).resolve()
                if not path.is_relative_to(root) or not re.fullmatch(r"[0-9a-f]{32}", path.parent.name) or path.name not in OUTPUT_FILES:
                    raise HTTPException(status_code=500, detail="invalid output path")
                result[f"{name}_url"] = str(request.url_for("download_output", job_id=path.parent.name, filename=path.name))
        result["job_id"] = body.job_id
        return result

    @application.get("/outputs/{job_id}/{filename}", name="download_output", dependencies=[Depends(require_token)])
    def download_output(job_id: str, filename: str, request: Request):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id) or filename not in OUTPUT_FILES:
            raise HTTPException(status_code=404, detail="File not found")
        root = request.app.state.worker.settings.output_dir.resolve()
        path = (root / job_id / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path, headers={"Cache-Control": "private, no-store"})

    return application


app = create_app()
