"""
Integration test for PostgreSQL storage, using an ephemeral Docker
container (via testcontainers) rather than a pre-existing database — the
test is fully self-contained and works in CI without prior setup.
"""
import asyncio
from pathlib import Path

from testcontainers.community.postgres import PostgresContainer

from ccsds_tm_decom.io.storage import create_pool, end_session, start_session, store_frame_result
from ccsds_tm_decom.orchestration.decoder import FrameResult

_SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def test_store_frame_result_persists_frame_and_packets():
    """
    Spin up a temporary PostgreSQL container, apply the schema, start a
    named session, store a FrameResult with two packets, then verify the
    session/frame/packet rows are correctly inserted and linked.
    """
    with PostgresContainer("postgres:16") as postgres:
        dsn = postgres.get_connection_url().replace("postgresql+psycopg2", "postgresql")

        async def run_test():
            pool = await create_pool(dsn)
            try:
                async with pool.acquire() as conn:
                    await conn.execute(_SCHEMA_PATH.read_text())

                session_id = await start_session(
                pool, name="test-session", connection_type="tcp",
                mission_name="test-mission", host="127.0.0.1", port=9999,
                )

                result = FrameResult(
                    tf_header={
                        "spacecraft_id": 13,
                        "virtual_channel_id": 0,
                        "virtual_channel_frame_count": 150,
                        "secondary_header_flag": 1,
                        "first_header_pointer": 10,
                        "ocf_flag": 1,
                    },
                    trailer={"fecf_valid": True, "ocf": None, "fecf_received": 0, "fecf_computed": 0},
                    packets=[
                        {
                            "apid": 212, "sequence_count": 1052, "packet_length": 736,
                            "pus_type": 3, "pus_subtype": 25, "raw_bytes": b"\x01\x02\x03",
                        },
                        {
                            "apid": 212, "sequence_count": 1054, "packet_length": 83,
                            "pus_type": 3, "pus_subtype": 25, "raw_bytes": b"\x04\x05\x06",
                        },
                    ],
                    leftover=b"",
                )

                await store_frame_result(pool, session_id, result)
                await end_session(pool, session_id)

                async with pool.acquire() as conn:
                    session_row = await conn.fetchrow(
                        "SELECT * FROM sessions WHERE id = $1", session_id
                    )
                    assert session_row["name"] == "test-session"
                    assert session_row["ended_at"] is not None

                    frame_row = await conn.fetchrow(
                        "SELECT * FROM frames WHERE session_id = $1", session_id
                    )
                    assert frame_row["spacecraft_id"] == 13
                    assert frame_row["fecf_valid"] is True

                    packet_rows = await conn.fetch(
                        "SELECT * FROM packets WHERE frame_id = $1 ORDER BY sequence_count",
                        frame_row["id"],
                    )
                    assert len(packet_rows) == 2
                    assert packet_rows[0]["pus_type"] == 3
                    assert packet_rows[0]["raw_bytes"] == b"\x01\x02\x03"
            finally:
                await pool.close()

        asyncio.run(run_test())