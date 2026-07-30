from ccsds_tm_decom.pipeline import Layer, run_pipeline


def test_strip_single_layer_with_header_and_tail():
    """Basic case: no inner_frame_length, strip fixed header/tail only."""
    header = bytes([0xAA, 0xAA])
    payload = bytes([0x01, 0x02, 0x03])
    tail = bytes([0xFF])
    data = header + payload + tail

    layer = Layer(name="basic_wrapper", header_bytes=2, tail_bytes=1)
    result = run_pipeline(data, [layer])

    assert result == payload


def test_strip_layer_with_inner_frame_length_and_padding():
    """
    Mirrors the real CORTEX wrapper observed in production telemetry logs:
    a 64-byte header, a fixed-size inner CADU frame (994 bytes, matching
    the real frame size seen in capture logs), 162 bytes of trailing
    padding, and a 4-byte tail with a known expected value.
    """
    header = bytes(range(64))  # 64-byte header, arbitrary content
    inner_frame = bytes([0xAB]) * 994  # simulates the real 994-byte CADU frame
    padding = bytes([0x00]) * 162  # matches padding observed in real captures
    tail = bytes.fromhex("B669FD2E")

    data = header + inner_frame + padding + tail

    layer = Layer(
        name="cortex_wrapper",
        header_bytes=64,
        tail_bytes=4,
        expected_tail_hex="B669FD2E",
        inner_frame_length=994,
    )
    result = run_pipeline(data, [layer])

    assert result == inner_frame
    assert len(result) == 994


def test_strip_layer_tail_mismatch_warns(capsys):
    """A tail that doesn't match expected_tail_hex prints a warning but doesn't raise."""
    header = bytes(range(64))
    inner_frame = bytes([0xAB]) * 994
    padding = bytes([0x00]) * 162
    wrong_tail = bytes([0x00, 0x00, 0x00, 0x00])

    data = header + inner_frame + padding + wrong_tail

    layer = Layer(
        name="cortex_wrapper",
        header_bytes=64,
        tail_bytes=4,
        expected_tail_hex="B669FD2E",
        inner_frame_length=994,
    )
    result = run_pipeline(data, [layer])

    captured = capsys.readouterr()
    assert "mismatch" in captured.out
    assert result == inner_frame