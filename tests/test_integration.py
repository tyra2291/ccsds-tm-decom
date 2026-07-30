from pathlib import Path

from ccsds_tm_decom.frame import parse_tf_primary_header
from ccsds_tm_decom.pipeline import load_layers, run_pipeline

_LAYERS_PATH = Path(__file__).parent.parent / "src" / "ccsds_tm_decom" / "schemas" / "ground_segment_layers.json"


def test_pipeline_then_decode():
    """
    Verify the full flow using real CORTEX wrapper sizes: strip a 64-byte
    CORTEX header, a 994-byte inner CADU frame, 162 bytes of padding, and
    a 4-byte tail, then decode the TM Transfer Frame primary header from
    the remaining bytes.
    """
    cortex_header = bytes(range(64))
    tf_header = bytes([0x06, 0x40, 0x00, 0x05, 0x18, 0x00])
    cadu_frame = tf_header + bytes([0x00]) * (994 - len(tf_header))
    padding = bytes([0x00]) * 162
    cortex_tail = bytes.fromhex("B669FD2E")

    raw = cortex_header + cadu_frame + padding + cortex_tail

    layers = load_layers(_LAYERS_PATH)
    stripped = run_pipeline(raw, layers)

    assert stripped == cadu_frame

    header = parse_tf_primary_header(stripped)
    assert header["spacecraft_id"] == 100