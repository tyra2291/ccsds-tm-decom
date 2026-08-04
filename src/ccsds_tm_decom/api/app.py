"""
FastAPI backend exposing decoded telemetry sessions, frames, and packets
stored in PostgreSQL. Supports session renaming/deletion, live TCP session
creation, file upload for offline decoding, mission config CRUD (with the
default missions protected from deletion), a byte-range inspector for raw
frames, multi-value packet filtering, and a live throughput status endpoint.
"""
import asyncio
import datetime
import json
import re
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ccsds_tm_decom.ground_segment.mission_config import load_mission_config
from ccsds_tm_decom.inspector import inspect_frame
from ccsds_tm_decom.io.batch import process_file
from ccsds_tm_decom.io.storage import (
    end_session,
    make_storage_callback,
    start_session,
    store_frame_result,
)
from ccsds_tm_decom.io.tcp_client import run_tcp_client

DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://ccsds:ccsds_dev_password@localhost:5432/ccsds_tm_decom",
)
MISSIONS_DIR = Path("src/ccsds_tm_decom/schemas/missions")
IDLE_APID = 2047
_PROTECTED_MISSIONS = {"cadu_only.json", "cortex_cadu.json"}
_background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open a connection pool on startup, close it on shutdown."""
    app.state.pool = await asyncpg.create_pool(DSN)
    yield
    await app.state.pool.close()


app = FastAPI(title="ccsds-tm-decom API", lifespan=lifespan)


class SessionUpdate(BaseModel):
    """Editable fields of a session."""
    name: str


class LayerModel(BaseModel):
    """A single ground segment layer, matching pipeline.Layer."""
    name: str
    header_bytes: int = 0
    tail_bytes: int = 0
    expected_tail_hex: str | None = None
    inner_frame_length: int | None = None


class MissionUpdate(BaseModel):
    """Full mission config, as stored in schemas/missions/*.json."""
    name: str
    frame_size: int
    security_header_bytes: int = 0
    layers: list[LayerModel]


class TcpSessionRequest(BaseModel):
    """Parameters to start a new live TCP acquisition session."""
    host: str
    port: int
    mission_config: str
    session_name: str


class InspectRequest(BaseModel):
    """Raw frame hex and mission config to inspect."""
    hex: str
    mission_config: str


# ---------- Missions ----------

@app.get("/api/missions")
async def list_missions():
    """List available mission configs."""
    missions = []
    for path in sorted(MISSIONS_DIR.glob("*.json")):
        config = load_mission_config(path)
        missions.append({"filename": path.name, "name": config.name})
    return missions


@app.get("/api/missions/{filename}")
async def get_mission(filename: str):
    """Return the full JSON content of a mission config file."""
    path = MISSIONS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Mission not found")
    with open(path) as f:
        return json.load(f)


@app.post("/api/missions")
async def create_mission(mission: MissionUpdate):
    """
    Create a new mission config file. The filename is derived from the
    mission name (slugified), and must not already exist.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", mission.name.lower()).strip("_")
    filename = f"{slug}.json"
    path = MISSIONS_DIR / filename

    if path.exists():
        raise HTTPException(status_code=409, detail=f"A mission file already exists: {filename}")

    with open(path, "w") as f:
        json.dump(mission.model_dump(), f, indent=2)

    return {"filename": filename, **mission.model_dump()}


@app.put("/api/missions/{filename}")
async def update_mission(filename: str, mission: MissionUpdate):
    """Overwrite a mission config file with new values."""
    path = MISSIONS_DIR / filename
    with open(path, "w") as f:
        json.dump(mission.model_dump(), f, indent=2)
    return mission


@app.delete("/api/missions/{filename}")
async def delete_mission(filename: str):
    """
    Delete a mission config file. The two default missions
    (cadu_only.json, cortex_cadu.json) cannot be deleted.
    """
    if filename in _PROTECTED_MISSIONS:
        raise HTTPException(status_code=403, detail="Default missions cannot be deleted")

    path = MISSIONS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Mission not found")

    path.unlink()
    return {"deleted": filename}


# ---------- Byte inspector ----------

@app.post("/api/inspect")
async def inspect(req: InspectRequest):
    """
    Decode a raw frame (pasted as hex) using the given mission config,
    returning byte-range regions for visual inspection in the UI.
    """
    mission_path = MISSIONS_DIR / req.mission_config
    mission = load_mission_config(mission_path)

    try:
        raw = bytes.fromhex(req.hex.replace(" ", "").strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid hex string")

    try:
        regions = inspect_frame(raw, mission)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decode failed: {e}")

    return {"length": len(raw), "regions": regions}


# ---------- Sessions ----------

@app.get("/api/sessions")
async def list_sessions(mission_name: str | None = None, host: str | None = None):
    """
    List all acquisition sessions, most recent first, optionally filtered
    by mission_name and/or host.
    """
    conditions = []
    params: list = []

    if mission_name is not None:
        params.append(mission_name)
        conditions.append(f"mission_name = ${len(params)}")
    if host is not None:
        params.append(host)
        conditions.append(f"host = ${len(params)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT id, name, connection_type, host, port, file_path,
               mission_name, started_at, ended_at
        FROM sessions
        {where_clause}
        ORDER BY started_at DESC
    """

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


@app.patch("/api/sessions/{session_id}")
async def rename_session(session_id: int, update: SessionUpdate):
    """Rename a session."""
    async with app.state.pool.acquire() as conn:
        await conn.execute("UPDATE sessions SET name = $1 WHERE id = $2", update.name, session_id)
        row = await conn.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
        return dict(row)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    """Delete a session and all its frames/packets (cascading delete)."""
    async with app.state.pool.acquire() as conn:
        await conn.execute("DELETE FROM sessions WHERE id = $1", session_id)
    return {"deleted": session_id}


@app.get("/api/sessions/{session_id}/status")
async def session_status(session_id: int):
    """
    Live status for a session: whether frames are currently being
    received, and the recent frame rate (frames/sec over the last 10s).
    """
    async with app.state.pool.acquire() as conn:
        last_frame = await conn.fetchrow(
            "SELECT received_at FROM frames WHERE session_id = $1 ORDER BY received_at DESC LIMIT 1",
            session_id,
        )
        recent_count = await conn.fetchval(
            "SELECT COUNT(*) FROM frames WHERE session_id = $1 AND received_at > now() - interval '10 seconds'",
            session_id,
        )
        session = await conn.fetchrow("SELECT ended_at FROM sessions WHERE id = $1", session_id)

    now = datetime.datetime.now(datetime.timezone.utc)
    is_receiving = (
        session is not None
        and session["ended_at"] is None
        and last_frame is not None
        and (now - last_frame["received_at"]).total_seconds() < 5
    )

    return {
        "is_receiving": is_receiving,
        "frames_per_second": round((recent_count or 0) / 10, 2),
        "last_frame_at": last_frame["received_at"] if last_frame else None,
    }


@app.post("/api/sessions/tcp")
async def start_tcp_session(req: TcpSessionRequest):
    """
    Start a new TCP acquisition session as a background task: connects to
    the given telemetry server, decodes incoming frames, and stores them
    under a newly created session. Returns immediately with the session id.
    """
    mission_path = MISSIONS_DIR / req.mission_config
    mission = load_mission_config(mission_path)

    session_id = await start_session(
        app.state.pool,
        name=req.session_name,
        connection_type="tcp",
        mission_name=mission.name,
        host=req.host,
        port=req.port,
    )
    on_frame = make_storage_callback(app.state.pool, session_id)

    async def _run():
        try:
            await run_tcp_client(
                host=req.host,
                port=req.port,
                frame_size=mission.frame_size,
                layers=mission.layers,
                on_frame=on_frame,
                security_header_bytes=mission.security_header_bytes,
            )
        finally:
            await end_session(app.state.pool, session_id)

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"session_id": session_id}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    mission_config: str = Form(...),
    session_name: str = Form(...),
):
    """
    Decode an uploaded raw binary frame file and store the results under
    a new session.
    """
    mission_path = MISSIONS_DIR / mission_config
    mission = load_mission_config(mission_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        session_id = await start_session(
            app.state.pool,
            name=session_name,
            connection_type="file",
            mission_name=mission.name,
            file_path=file.filename,
        )

        results = process_file(
            tmp_path,
            frame_size=mission.frame_size,
            layers=mission.layers,
            security_header_bytes=mission.security_header_bytes,
        )
        for result in results:
            await store_frame_result(app.state.pool, session_id, result)

        await end_session(app.state.pool, session_id)
        return {"session_id": session_id, "frames_decoded": len(results)}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/api/sessions/{session_id}/frames")
async def list_frames(session_id: int, spacecraft_id: int | None = None, limit: int = Query(100, le=1000)):
    """List frames for a given session, optionally filtered by spacecraft_id."""
    async with app.state.pool.acquire() as conn:
        if spacecraft_id is not None:
            rows = await conn.fetch(
                """
                SELECT * FROM frames
                WHERE session_id = $1 AND spacecraft_id = $2
                ORDER BY received_at DESC LIMIT $3
                """,
                session_id, spacecraft_id, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM frames WHERE session_id = $1 ORDER BY received_at DESC LIMIT $2",
                session_id, limit,
            )
        return [dict(row) for row in rows]


@app.get("/api/sessions/{session_id}/packets")
async def list_packets(
    session_id: int,
    apid: list[int] | None = Query(None),
    pus_type: list[int] | None = Query(None),
    pus_subtype: list[int] | None = Query(None),
    spacecraft_id: list[int] | None = Query(None),
    exclude_idle: bool = False,
    limit: int = Query(200, le=2000),
):
    """
    List packets for a session, with multi-value filters. exclude_idle
    drops CCSDS Idle Packets (APID 2047).
    """
    conditions = ["f.session_id = $1"]
    params: list = [session_id]

    if apid:
        params.append(apid)
        conditions.append(f"p.apid = ANY(${len(params)})")
    if pus_type:
        params.append(pus_type)
        conditions.append(f"p.pus_type = ANY(${len(params)})")
    if pus_subtype:
        params.append(pus_subtype)
        conditions.append(f"p.pus_subtype = ANY(${len(params)})")
    if spacecraft_id:
        params.append(spacecraft_id)
        conditions.append(f"f.spacecraft_id = ANY(${len(params)})")
    if exclude_idle:
        conditions.append(f"p.apid != {IDLE_APID}")

    params.append(limit)
    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT p.id, p.frame_id, p.apid, p.sequence_count, p.packet_length,
               p.pus_type, p.pus_subtype, p.raw_bytes, f.spacecraft_id, f.received_at
        FROM packets p
        JOIN frames f ON f.id = p.frame_id
        WHERE {where_clause}
        ORDER BY f.received_at DESC
        LIMIT ${len(params)}
    """

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        results = []
        for row in rows:
            item = dict(row)
            item["raw_bytes"] = item["raw_bytes"].hex().upper()
            item["is_idle"] = item["apid"] == IDLE_APID
            results.append(item)
        return results


app.mount("/", StaticFiles(directory="src/ccsds_tm_decom/api/static", html=True), name="static")