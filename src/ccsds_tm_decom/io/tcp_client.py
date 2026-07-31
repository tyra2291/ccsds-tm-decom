"""
Real-time TCP client for consuming TM Transfer Frames from a telemetry
front-end server (e.g. CORTEX). Connects out to the given host/port and
reads fixed-size frames continuously until the connection closes.
"""
import asyncio
from collections.abc import Awaitable, Callable

from ccsds_tm_decom.ground_segment.pipeline import Layer
from ccsds_tm_decom.orchestration.decoder import FrameResult, process_frame

FrameCallback = Callable[[FrameResult], Awaitable[None]]


async def run_tcp_client(
    host: str,
    port: int,
    frame_size: int,
    layers: list[Layer],
    on_frame: FrameCallback,
    security_header_bytes: int = 0,
) -> None:
    """
    Connect to a telemetry server and decode incoming TM Transfer Frames
    in real time until the connection is closed by the remote side.

    Args:
        host: Hostname or IP of the telemetry server to connect to.
        port: TCP port of the telemetry server.
        frame_size: Exact byte size of each incoming frame.
        layers: Ground segment layers to strip (see pipeline.load_layers).
        on_frame: Async callback invoked with each decoded FrameResult,
            in arrival order.
        security_header_bytes: Mission-specific security header size (see
            decoder.process_frame).
    """
    reader, writer = await asyncio.open_connection(host, port)
    leftover = b""

    try:
        while True:
            raw_frame = await reader.readexactly(frame_size)
            result = process_frame(
                raw_frame, layers, leftover=leftover,
                security_header_bytes=security_header_bytes,
            )
            leftover = result.leftover
            await on_frame(result)
    except asyncio.IncompleteReadError:
        # Server closed the connection, possibly mid-frame
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"Disconnected from {host}:{port}")