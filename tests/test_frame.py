# tests/test_frame.py
from ccsds_tm_decom.frame import parse_primary_header


def test_parse_primary_header():
    """
    Verify that a hand-crafted CCSDS primary header byte sequence decodes
    into the expected field values.

    Test frame breakdown (6 bytes):
        0x08, 0x64 -> word1: version=0, packet_type=0, sec_hdr_flag=1, apid=100
        0xC0, 0x00 -> word2: sequence_flags=3, sequence_count=0
        0x00, 0x05 -> packet_length=5
    """
    raw = bytes([0x08, 0x64, 0xC0, 0x00, 0x00, 0x05])
    print(f"\nInput bytes: {raw.hex(sep=' ')}")

    header = parse_primary_header(raw)
    print(f"Decoded header: {header}")

    assert header["version"] == 0, f"Expected version=0, got {header['version']}"
    assert header["apid"] == 100, f"Expected apid=100, got {header['apid']}"
    assert header["sequence_count"] == 0, f"Expected sequence_count=0, got {header['sequence_count']}"

    print("All assertions passed.")

if __name__ == "__main__":
    test_parse_primary_header()