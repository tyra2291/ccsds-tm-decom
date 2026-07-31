from ccsds_tm_decom.ccsds.packet import extract_space_packets, NO_PACKET_START


def test_extract_single_complete_packet():
    """
    A data field containing exactly one complete Space Packet should be
    fully extracted, with no leftover bytes.
    """
    # Header: version=0, type=0, sec_hdr=0, apid=100, seq_flags=3, seq_count=0, packet_length=2
    header = bytes([0x00, 0x64, 0xC0, 0x00, 0x00, 0x02])
    payload = bytes([0xAA, 0xBB, 0xCC])  # 3 bytes = packet_length(2) + 1
    data_field = header + payload

    packets, leftover = extract_space_packets(data_field, first_header_pointer=0)

    assert len(packets) == 1
    assert packets[0]["apid"] == 100
    assert packets[0]["raw_bytes"] == header + payload
    assert leftover == b""


def test_extract_with_spillover():
    """
    A packet cut short by the frame boundary should be returned as leftover,
    to be prepended to the next frame's data field.
    """
    header = bytes([0x00, 0x64, 0xC0, 0x00, 0x00, 0x02])
    incomplete_payload = bytes([0xAA])  # only 1 of 3 expected bytes present
    data_field = header + incomplete_payload

    packets, leftover = extract_space_packets(data_field, first_header_pointer=0)

    assert packets == []
    assert leftover == data_field  # whole thing carried over


def test_no_packet_start_in_frame():
    """
    A NO_PACKET_START pointer means the whole data field continues a
    packet from a previous frame — nothing new to extract here.
    """
    data_field = bytes([0x11, 0x22, 0x33])

    packets, leftover = extract_space_packets(data_field, NO_PACKET_START)

    assert packets == []
    assert leftover == data_field