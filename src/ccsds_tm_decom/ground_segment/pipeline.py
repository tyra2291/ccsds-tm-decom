"""
Ground segment layer stripping for CCSDS telemetry streams.

This module is intentionally generic and knows nothing about CCSDS itself:
it only strips fixed-size header/tail wrappers (e.g. CORTEX, CADU sync
markers) from raw byte streams, based on a configurable, ordered list of
layers. Each layer can also validate a known trailer value, and optionally
account for padding between the actual inner frame and the layer's tail.
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Layer:
    """
    Represents one encapsulation layer to strip before reaching the payload.

    A layer removes a fixed-size header and, optionally, a fixed-size tail
    from raw bytes. Some ground segment protocols (e.g. CORTEX) pad the
    space between the actual inner frame and their tail up to a fixed
    total size; `inner_frame_length` accounts for that so the padding is
    discarded along with the header/tail rather than leaking into the
    stripped output.

    Attributes:
        name: Human-readable identifier for this layer (used in logs/debugging).
        header_bytes: Number of bytes to discard from the start of the data.
        tail_bytes: Number of bytes to discard from the very end of the data.
        expected_tail_hex: Optional expected hex value (uppercase, no
            spaces) of the tail bytes. If set and the actual tail doesn't
            match, a warning is printed — this does not raise, since a
            mismatch may be worth investigating rather than treated as fatal.
        inner_frame_length: If set, the exact known length in bytes of the
            encapsulated frame immediately following the header. Only these
            bytes are kept as payload; anything between the end of this
            frame and the start of the tail is treated as padding and
            discarded. Required for protocols whose frame length is a link
            configuration parameter rather than something encoded in the
            frame itself (e.g. CCSDS TM Transfer Frames).
    """
    name: str
    header_bytes: int = 0
    tail_bytes: int = 0
    expected_tail_hex: str | None = None
    inner_frame_length: int | None = None


def load_layers(path: str | Path) -> list[Layer]:
    """
    Load an ordered list of encapsulation layers from a JSON config file.

    Args:
        path: Path to the JSON file describing the layers to strip. Expected
            shape: {"layers": [{"name": ..., "header_bytes": ..., ...}, ...]}.

    Returns:
        A list of Layer objects, in the order they should be applied.
    """
    with open(path) as f:
        raw = json.load(f)
    return [Layer(**layer) for layer in raw["layers"]]


def strip_layer(data: bytes, layer: Layer) -> bytes:
    """
    Remove a layer's header, tail, and any inter-frame padding.

    If `layer.inner_frame_length` is set, only that many bytes right after
    the header are kept as the actual payload — anything beyond that (up
    to the start of the tail) is discarded as padding. Otherwise, the
    result is everything between the header and the tail.

    If `layer.expected_tail_hex` is set, the actual tail bytes are checked
    against it and a warning is printed on mismatch (non-fatal).

    Args:
        data: Raw bytes including this layer's header/tail (and, if
            applicable, trailing padding before the tail).
        layer: The Layer definition specifying how to strip it.

    Returns:
        The remaining bytes: the inner frame, with this layer's header,
        tail, and any padding removed.
    """
    start = layer.header_bytes

    if layer.inner_frame_length is not None:
        end = start + layer.inner_frame_length
    elif layer.tail_bytes:
        end = len(data) - layer.tail_bytes
    else:
        end = len(data)

    if layer.tail_bytes and layer.expected_tail_hex:
        tail_start = len(data) - layer.tail_bytes
        actual_tail = data[tail_start:].hex().upper()
        if actual_tail != layer.expected_tail_hex.upper():
            print(
                f"Warning: {layer.name} trailer mismatch — expected "
                f"{layer.expected_tail_hex.upper()}, got {actual_tail}"
            )

    return data[start:end]


def run_pipeline(data: bytes, layers: list[Layer]) -> bytes:
    """
    Apply a sequence of layers in order, stripping each one's header/tail
    (and padding, where applicable).

    Layers are applied in list order — e.g. [cortex_layer, cadu_layer]
    strips CORTEX first, then CADU, leaving the innermost frame at the end.

    Args:
        data: The full raw byte stream, outermost layer first.
        layers: Ordered list of Layer objects to strip.

    Returns:
        The bytes remaining after all layers have been stripped.
    """
    for layer in layers:
        data = strip_layer(data, layer)
    return data