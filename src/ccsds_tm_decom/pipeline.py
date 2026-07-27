# src/ccsds_tm_decom/pipeline.py
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Layer:
    """
    Represents one encapsulation layer to strip before reaching the payload.

    A layer is either:
    - A simple wrapper with a fixed-size header/tail to discard
      (e.g. SLE, Cortex ground segment framing), or
    - A field-decoding layer with a JSON schema (e.g. CCSDS primary header),
      handled separately by `decode_fields` once stripping is done.

    Attributes:
        name: Human-readable identifier for this layer (used in logs/debugging).
        header_bytes: Number of bytes to discard from the start of the data.
        tail_bytes: Number of bytes to discard from the end of the data.
    """
    name: str
    header_bytes: int = 0
    tail_bytes: int = 0


def strip_layer(data: bytes, layer: Layer) -> bytes:
    """
    Remove a layer's header and tail bytes from the given data.

    Args:
        data: Raw bytes including this layer's header/tail.
        layer: The Layer definition specifying how many bytes to strip.

    Returns:
        The remaining bytes, with this layer's header and tail removed.
    """
    start = layer.header_bytes
    end = len(data) - layer.tail_bytes if layer.tail_bytes else len(data)
    return data[start:end]


def run_pipeline(data: bytes, layers: list[Layer]) -> bytes:
    """
    Apply a sequence of layers in order, stripping each one's header/tail.

    Layers are applied in list order — e.g. [sle_layer, cortex_layer] strips
    SLE first, then Cortex, leaving the raw CCSDS frame at the end.

    Args:
        data: The full raw byte stream, outermost layer first.
        layers: Ordered list of Layer objects to strip.

    Returns:
        The bytes remaining after all layers have been stripped.
    """
    for layer in layers:
        data = strip_layer(data, layer)
    return data

def load_layers(path: str | Path) -> list[Layer]:
    """
    Load an ordered list of encapsulation layers from a JSON config file.

    Args:
        path: Path to the JSON file describing the layers to strip.

    Returns:
        A list of Layer objects, in the order they should be applied.
    """
    with open(path) as f:
        raw = json.load(f)
    return [Layer(**layer) for layer in raw["layers"]]