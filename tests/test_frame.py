from ccsds_tm_decom.frame import parse_tf_primary_header


def test_parse_tf_primary_header():
    """
    Verify decoding of a hand-crafted 6-byte TM Transfer Frame primary
    header (Frame Primary Header + Data Field Status combined).

    Encodes: version=0, spacecraft_id=100, virtual_channel_id=0,
    ocf_flag=0, master_channel_frame_count=0, virtual_channel_frame_count=5,
    segment_length_id=3 (0b11), first_header_pointer=0.
    """
    raw = bytes([0x06, 0x40, 0x00, 0x05, 0x18, 0x00])
    header = parse_tf_primary_header(raw)

    assert header["spacecraft_id"] == 100
    assert header["virtual_channel_id"] == 0
    assert header["virtual_channel_frame_count"] == 5