from pathlib import Path

from ccsds_tm_decom.frame import parse_tf_primary_header
from ccsds_tm_decom.pipeline import load_layers, run_pipeline

_LAYERS_PATH = Path(__file__).parent.parent / "src" / "ccsds_tm_decom" / "schemas" / "ground_segment_layers.json"


def test_pipeline_then_decode():
    """
    Verify the full flow: strip a ground-segment wrapper (SLE) from raw
    bytes, then decode the remaining CCSDS TM Transfer Frame primary header.
    """
    sle_header = bytes([0xAA, 0xAA])
    tf_header = bytes([0x06, 0x40, 0x00, 0x05, 0x18, 0x00])
    sle_tail = bytes([0xFF])

    raw = sle_header + tf_header + sle_tail

    layers = load_layers(_LAYERS_PATH)
    stripped = run_pipeline(raw, layers)

    assert stripped == tf_header

    header = parse_tf_primary_header(stripped)
    assert header["spacecraft_id"] == 100