"""
DataPilot FastAPI Backend (api.py)

Exposes:
  POST /upload          — upload a CSV file, returns a session token
  GET  /analyze         — SSE stream: runs the full pipeline, streams
                          real-time JSON events to the browser
  GET  /                — serves the built React SPA (production)
"""

import os
import json
import base64
import asyncio
import shutil
import uuid
import mimetypes
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config import WORKSPACE_DIR, MAX_RETRIES_PER_TASK

from profiler import profile_csv
from planner import plan_tasks
from coder import generate_code
from executor import prepare_workspace, run_script, verify_artifacts
from reviewer import review

APP_PASSWORD = os.getenv("APP_PASSWORD", "DataPilot123!")

app = FastAPI(title="DataPilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, Path] = {}
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _encode_artifact(path: Path) -> dict | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return {"filename": path.name, "mime": mime, "data": encoded}


def verify_password(pwd: str):
    if APP_PASSWORD and pwd != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized: Incorrect password.")

@app.post("/login")
def login(pwd: str = Query(...)):
    verify_password(pwd)
    return {"status": "ok"}


@app.post("/upload")
async def upload_csv(pwd: str = Query(None), file: UploadFile = File(...)):
    verify_password(pwd)
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    token = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{token}.csv"
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    _sessions[token] = dest
    return {"token": token, "filename": file.filename}


@app.get("/analyze")
async def analyze(
    token: str = Query(...),
    request: str = Query(...),
    pwd: str = Query(None),
    use_pro: bool = Query(False),
):
    verify_password(pwd)
    csv_path = _sessions.get(token)
    if not csv_path or not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found. Upload a CSV first.")

    async def event_generator():
        loop = asyncio.get_event_loop()
        max_retries = MAX_RETRIES_PER_TASK

        session_workspace = WORKSPACE_DIR / token
        try:
            await loop.run_in_executor(None, prepare_workspace, str(csv_path), session_workspace)
            schema = await loop.run_in_executor(None, profile_csv, str(csv_path))
            yield _event({"type": "schema", "schema": schema})

            plan = await loop.run_in_executor(None, plan_tasks, request, schema, use_pro)

            for step in plan.steps:
                # Ensure the planner provided artifacts
                if not step.expected_artifacts:
                    step.expected_artifacts = []

            yield _event({
                "type": "plan",
                "steps": [
                    {"name": s.step_name, "description": s.description, "artifacts": s.expected_artifacts}
                    for s in plan.steps
                ],
            })

            results_summary = []
            for i, step in enumerate(plan.steps, 1):
                yield _event({
                    "type": "step_start",
                    "step": i,
                    "total": len(plan.steps),
                    "name": step.step_name,
                    "description": step.description,
                })

                script_path = session_workspace / step.step_name
                code = None
                error_context = None
                success = False

                for attempt in range(1, max_retries + 1):
                    yield _event({"type": "step_attempt", "step": i, "attempt": attempt, "max": max_retries})
                    try:
                        _code = code
                        _err = error_context
                        _desc = step.description
                        _arts = step.expected_artifacts
                        code = await loop.run_in_executor(
                            None,
                            lambda: generate_code(
                                task_description=_desc,
                                csv_schema=schema,
                                workspace_dir=str(session_workspace),
                                expected_artifacts=_arts,
                                previous_code=_code,
                                error=_err,
                                use_pro=use_pro,
                            ),
                        )
                        script_path.write_text(code, encoding="utf-8")
                        exec_result = await loop.run_in_executor(None, run_script, str(script_path), session_workspace)
                        artifact_check = await loop.run_in_executor(None, verify_artifacts, step.expected_artifacts, session_workspace)
                        review_result = await loop.run_in_executor(None, review, step.description, exec_result, artifact_check, use_pro)

                        yield _event({
                            "type": "step_result",
                            "step": i,
                            "attempt": attempt,
                            "approved": review_result.approved,
                            "reason": review_result.reason or "",
                            "suggestion": review_result.retry_suggestion or "",
                        })

                        if review_result.approved:
                            success = True
                            for artifact_name in (step.expected_artifacts or []):
                                artifact_path = session_workspace / artifact_name
                                payload = _encode_artifact(artifact_path)
                                if payload:
                                    yield _event({"type": "artifact", **payload})
                            break
                        else:
                            error_context = (
                                f"stdout:\n{exec_result.get('stdout', '')}\n"
                                f"stderr:\n{exec_result.get('stderr', '')}\n"
                                f"returncode: {exec_result.get('returncode')}\n"
                                f"Reviewer rejection feedback:\n{review_result.reason}"
                            )
                    except Exception as e:
                        error_context = str(e)
                        yield _event({"type": "step_result", "step": i, "attempt": attempt, "approved": False, "reason": str(e), "suggestion": ""})

                results_summary.append({"name": step.step_name, "status": "SUCCESS" if success else "FAILED"})

            yield _event({"type": "done", "summary": results_summary})

        except Exception as e:
            yield _event({"type": "error", "message": str(e)})
        finally:
            # Clean up the uploaded file and the isolated workspace
            if csv_path.exists():
                csv_path.unlink()
            shutil.rmtree(session_workspace, ignore_errors=True)
            _sessions.pop(token, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve Vanilla JS Frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
