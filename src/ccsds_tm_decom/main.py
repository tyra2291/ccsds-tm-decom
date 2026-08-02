"""
Entry point: decode TM Transfer Frames either from a live TCP connection
to a telemetry front-end, or from a raw binary file — optionally
persisting results to PostgreSQL under a named acquisition session.
"""
import argparse
import asyncio
from pathlib import Path

from ccsds_tm_decom.ground_segment.mission_config import load_mission_config
from ccsds_tm_decom.io.batch import process_file
from ccsds_tm_decom.io.storage import create_pool, end_session, make_storage_callback, start_session
from ccsds_tm_decom.io.tcp_client import run_tcp_client
from ccsds_tm_decom.orchestration.decoder import FrameResult


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments, supporting `tcp` and `file` subcommands."""
    parser = argparse.ArgumentParser(
        description="Decode TM Transfer Frames from a live TCP source or a file."
    )
    parser.add_argument("--mission-config", required=True, type=Path, help="Path to the mission config JSON")
    parser.add_argument("--session-name", help="Session name; enables PostgreSQL storage if provided")
    parser.add_argument(
        "--dsn",
        default="postgresql://ccsds:ccsds_dev_password@localhost:5432/ccsds_tm_decom",
        help="PostgreSQL connection string (only used if --session-name is set)",
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    tcp_parser = subparsers.add_parser("tcp", help="Connect to a live telemetry front-end over TCP")
    tcp_parser.add_argument("--host", required=True, help="Telemetry server hostname or IP")
    tcp_parser.add_argument("--port", required=True, type=int, help="Telemetry server TCP port")

    file_parser = subparsers.add_parser("file", help="Decode frames from a raw binary file")
    file_parser.add_argument("--path", required=True, type=Path, help="Path to the binary frame file")

    return parser.parse_args()


async def _print_summary(result: FrameResult) -> None:
    """Default on_frame callback when no storage is configured: prints a one-line summary."""
    scid = result.tf_header["spacecraft_id"]
    n_packets = len(result.packets)
    fecf_ok = result.trailer["fecf_valid"]
    print(f"Frame decoded: spacecraft_id={scid} packets={n_packets} fecf_valid={fecf_ok}")


async def _run(args: argparse.Namespace) -> None:
    """Wire together mission config, optional storage, and the chosen input source."""
    mission = load_mission_config(args.mission_config)

    pool = None
    session_id = None
    on_frame = _print_summary

    if args.session_name:
        pool = await create_pool(args.dsn)
        source = f"tcp:{args.host}:{args.port}" if args.mode == "tcp" else f"file:{args.path}"
        session_id = await start_session(pool, name=args.session_name, source=source)
        print(f"Session '{args.session_name}' started (id={session_id})")
        on_frame = make_storage_callback(pool, session_id)

    try:
        if args.mode == "tcp":
            await run_tcp_client(
                host=args.host,
                port=args.port,
                frame_size=mission.frame_size,
                layers=mission.layers,
                on_frame=on_frame,
                security_header_bytes=mission.security_header_bytes,
            )
        else:
            results = process_file(
                args.path,
                frame_size=mission.frame_size,
                layers=mission.layers,
                security_header_bytes=mission.security_header_bytes,
            )
            for result in results:
                await on_frame(result)
    finally:
        if session_id is not None:
            await end_session(pool, session_id)
            print(f"Session '{args.session_name}' ended")
        if pool is not None:
            await pool.close()


def main() -> None:
    """CLI entry point."""
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()