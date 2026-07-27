# tests/test_pipeline.py
from ccsds_tm_decom.pipeline import Layer, run_pipeline


def test_run_pipeline_strips_multiple_layers():
    """
    Verify that stacking two layers (e.g. SLE then Cortex) strips both
    wrappers in order, leaving only the innermost payload.
    """
    # 2-byte fake SLE header + 3-byte payload + 1-byte SLE tail
    data = bytes([0xAA, 0xAA]) + bytes([0x01, 0x02, 0x03]) + bytes([0xFF])

    layers = [Layer(name="sle_wrapper", header_bytes=2, tail_bytes=1)]
    result = run_pipeline(data, layers)

    assert result == bytes([0x01, 0x02, 0x03])