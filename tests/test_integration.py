from pathlib import Path

from ccsds_tm_decom.ccsds.frame import parse_tf_primary_header
from ccsds_tm_decom.ground_segment.pipeline import load_layers, run_pipeline

_LAYERS_PATH = Path(__file__).parent.parent / "src" / "ccsds_tm_decom" / "schemas" / "ground_segment_layers.json"


def test_pipeline_then_decode():
    cortex_header = bytes(range(64))
    sync_marker = bytes([0x1A, 0xCF, 0xFC, 0x1D])
    tf_header = bytes([0x06, 0x40, 0x00, 0x05, 0x18, 0x00])
    cadu_body = tf_header + bytes([0x00]) * (994 - len(sync_marker) - len(tf_header))
    inner_frame = sync_marker + cadu_body  # 994 bytes total (matches inner_frame_length)
    padding = bytes([0x00]) * 162
    cortex_tail = bytes.fromhex("B669FD2E")

    raw = cortex_header + inner_frame + padding + cortex_tail

    layers = load_layers(_LAYERS_PATH)
    stripped = run_pipeline(raw, layers)

    assert stripped == cadu_body

    header = parse_tf_primary_header(stripped)
    assert header["spacecraft_id"] == 100