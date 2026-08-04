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
    results: list[FrameResult] = []
    leftover = b""
    skipped_count = 0

    for i, raw_frame in enumerate(iter_frames_from_file(path, frame_size)):
        try:
            result = process_frame(
                raw_frame, layers, leftover=leftover,
                security_header_bytes=security_header_bytes,
            )
        except ValueError as e:
            print(f"Warning: skipping malformed frame #{i}: {e}")
            skipped_count += 1
            leftover = b""  # reset: can't trust leftover after a decode failure
            continue

        results.append(result)
        leftover = result.leftover

    if skipped_count:
        print(f"Warning: {skipped_count} frame(s) skipped due to decode errors")

    return results