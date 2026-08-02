"""
Asynchronous PostgreSQL storage for decoded TM Transfer Frames and their
extracted Space Packets, grouped by acquisition session (e.g. one TCP
connection or one processed file). Sessions carry connection metadata
(host/port or file path) and the mission config used, and can be renamed
after creation.
"""
from functools import partial

import asyncpg

from ccsds_tm_decom.orchestration.decoder import FrameResult


async def create_pool(dsn: str) -> asyncpg.Pool:
    """
    Create a connection pool to the PostgreSQL database.

    Args:
        dsn: PostgreSQL connection string.

    Returns:
        An asyncpg connection pool, to be reused across the application's
        lifetime.
    """
    return await asyncpg.create_pool(dsn)


async def start_session(
    pool: asyncpg.Pool,
    name: str,
    connection_type: str,
    mission_name: str,
    host: str | None = None,
    port: int | None = None,
    file_path: str | None = None,
) -> int:
    """
    Create a new acquisition session and return its id.

    Args:
        pool: An active asyncpg connection pool.
        name: Human-readable name for this session.
        connection_type: "tcp" or "file".
        mission_name: Name of the mission config used to decode this session.
        host: Telemetry server hostname/IP, if connection_type == "tcp".
        port: Telemetry server port, if connection_type == "tcp".
        file_path: Path to the source file, if connection_type == "file".

    Returns:
        The newly created session's id, to pass to store_frame_result.
    """
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO sessions (name, connection_type, host, port, file_path, mission_name)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            name, connection_type, host, port, file_path, mission_name,
        )


async def update_session(pool: asyncpg.Pool, session_id: int, name: str | None = None) -> None:
    """
    Update editable fields of an existing session (currently: name only).

    Args:
        pool: An active asyncpg connection pool.
        session_id: The session to update.
        name: New name for the session, if provided. No-op if None.
    """
    if name is None:
        return
    async with pool.acquire() as conn:
        await conn.execute("UPDATE sessions SET name = $1 WHERE id = $2", name, session_id)


async def end_session(pool: asyncpg.Pool, session_id: int) -> None:
    """
    Mark a session as ended by setting its ended_at timestamp to now.

    Args:
        pool: An active asyncpg connection pool.
        session_id: The session id returned by start_session.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sessions SET ended_at = now() WHERE id = $1",
            session_id,
        )


async def store_frame_result(pool: asyncpg.Pool, session_id: int, result: FrameResult) -> None:
    """
    Persist a decoded frame and all its extracted packets to PostgreSQL,
    linked to the given acquisition session.

    Args:
        pool: An active asyncpg connection pool.
        session_id: The session this frame belongs to (see start_session).
        result: The decoded FrameResult to store.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            frame_id = await conn.fetchval(
                """
                INSERT INTO frames (
                    session_id, spacecraft_id, virtual_channel_id,
                    virtual_channel_frame_count, fecf_valid
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                session_id,
                result.tf_header["spacecraft_id"],
                result.tf_header["virtual_channel_id"],
                result.tf_header["virtual_channel_frame_count"],
                result.trailer["fecf_valid"],
            )

            for packet in result.packets:
                await conn.execute(
                    """
                    INSERT INTO packets (
                        frame_id, apid, sequence_count, packet_length,
                        pus_type, pus_subtype, raw_bytes
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    frame_id,
                    packet["apid"],
                    packet["sequence_count"],
                    packet["packet_length"],
                    packet["pus_type"],
                    packet["pus_subtype"],
                    packet["raw_bytes"],
                )


def make_storage_callback(pool: asyncpg.Pool, session_id: int):
    """
    Build an `on_frame` callback (see io.tcp_client, io.batch) that
    stores each decoded FrameResult under the given session.

    Args:
        pool: An active asyncpg connection pool.
        session_id: The session to link stored frames to (see start_session).

    Returns:
        An async callable taking a single FrameResult argument, suitable
        for use as `on_frame` in run_tcp_client or process_file.
    """
    return partial(store_frame_result, pool, session_id)