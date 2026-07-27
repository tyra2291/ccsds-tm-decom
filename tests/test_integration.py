# tests/test_integration.py
from pathlib import Path

from ccsds_tm_decom.frame import parse_primary_header
from ccsds_tm_decom.pipeline import load_layers, run_pipeline

_LAYERS_PATH = Path(__file__).parent.parent / "src" / "ccsds_tm_decom" / "schemas" / "ground_segment_layers.json"


def test_pipeline_then_decode():
    """
    Verify the full flow: strip a ground-segment wrapper (SLE) from raw
    bytes, then decode the remaining CCSDS primary header.

    Simulated input: 2-byte fake SLE header + 6-byte CCSDS header + 1-byte SLE tail.
    """
    sle_header = bytes([0xAA, 0xAA])
    ccsds_header = bytes([0x08, 0x64, 0xC0, 0x00, 0x00, 0x05])
    sle_tail = bytes([0xFF])

    raw = sle_header + ccsds_header + sle_tail

    layers = load_layers(_LAYERS_PATH)
    stripped = run_pipeline(raw, layers)

    assert stripped == ccsds_header  # la couche SLE a bien été retirée

    header = parse_primary_header(stripped)
    assert header["apid"] == 100