"""
Batch processing of a raw binary file containing multiple fixed-size TM
Transfer Frames, back to back (e.g. a recorded CADU stream). Frames are
processed sequentially through `decoder.process_frame`, carrying the
Space Packet spillover leftover from one frame to the next across the
entire file.
"""
from collections.abc import Iterator
from pathlib import Path

from ccsds_tm_decom.orchestration.decoder import FrameResult, process_frame
from ccsds_tm_decom.ground_segment.pipeline import Layer


def iter_frames_from_file(path: str | Path, frame_size: int) -> Iterator[bytes]:
    """
    Read fixed-size raw frames sequentially from a binary file.

    Args:
        path: Path to the binary file containing back-to-back frames.
        frame_size: Exact byte size of each frame (including any ground
            segment wrapper, sync markers, etc. — whatever `layers` will
            strip downstream).

    Yields:
        Raw bytes for each frame, in file order. If the final chunk is
        shorter than frame_size (a truncated trailing frame), it is
        skipped with a printed warning rather than yielded, since it
        cannot be a complete, valid frame.
    """
    with open(path, "rb") as f:
        while True:
            chunk = f.read(frame_size)
            if not chunk:
                break
            if len(chunk) < frame_size:
                print(
                    f"Warning: skipping truncated trailing frame "
                    f"({len(chunk)} bytes, expected {frame_size})"
                )
                break
            yield chunk


def process_file(
    path: str | Path,
    frame_size: int,
    layers: list[Layer],
    security_header_bytes: int = 0,
) -> list[FrameResult]:
    """
    Decode every frame in a raw binary file end to end, carrying Space
    Packet spillover leftover across frame boundaries throughout the file.

    Args:
        path: Path to the binary file containing back-to-back frames.
        frame_size: Exact byte size of each frame.
        layers: Ordered list of Layer objects for ground segment stripping
            (see pipeline.load_layers). Pass an empty list if frames have
            no ground segment wrapper (e.g. already-stripped CADU).
        security_header_bytes: Mission-specific security header size, if
            secondary_header_flag is set (see decoder.process_frame).

    Returns:
        A list of FrameResult, one per frame in file order.
    """
    results: list[FrameResult] = []
    leftover = b""

    for raw_frame in iter_frames_from_file(path, frame_size):
        result = process_frame(
            raw_frame, layers, leftover=leftover,
            security_header_bytes=security_header_bytes,
        )
        results.append(result)
        leftover = result.leftover

    return results