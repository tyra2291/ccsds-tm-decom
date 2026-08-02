"""
FastAPI backend exposing decoded telemetry sessions, frames, and packets
stored in PostgreSQL, with filtering support (by satellite, APID, PUS
type/subtype) for the web UI.
"""
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

DSN = "postgresql://ccsds:ccsds_dev_password@localhost:5432/ccsds_tm_decom"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open a connection pool on startup, close it on shutdown."""
    app.state.pool = await asyncpg.create_pool(DSN)
    yield
    await app.state.pool.close()


app = FastAPI(title="ccsds-tm-decom API", lifespan=lifespan)


@app.get("/api/sessions")
async def list_sessions():
    """List all acquisition sessions, most recent first."""
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, source, started_at, ended_at FROM sessions ORDER BY started_at DESC"
        )
        return [dict(row) for row in rows]


@app.get("/api/sessions/{session_id}/frames")
async def list_frames(session_id: int, spacecraft_id: int | None = None, limit: int = Query(100, le=1000)):
    """
    List frames for a given session, optionally filtered by spacecraft_id.
    """
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
    apid: int | None = None,
    pus_type: int | None = None,
    pus_subtype: int | None = None,
    limit: int = Query(100, le=1000),
):
    """
    List packets for a given session, optionally filtered by APID and/or
    PUS type/subtype. raw_bytes is returned as a hex string, not raw
    binary, for easy consumption by the web UI.
    """
    conditions = ["f.session_id = $1"]
    params: list = [session_id]

    if apid is not None:
        params.append(apid)
        conditions.append(f"p.apid = ${len(params)}")
    if pus_type is not None:
        params.append(pus_type)
        conditions.append(f"p.pus_type = ${len(params)}")
    if pus_subtype is not None:
        params.append(pus_subtype)
        conditions.append(f"p.pus_subtype = ${len(params)}")

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
            results.append(item)
        return results


app.mount("/", StaticFiles(directory="src/ccsds_tm_decom/api/static", html=True), name="static")