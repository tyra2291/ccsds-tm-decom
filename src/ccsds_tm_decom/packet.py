"""
Extraction of CCSDS Space Packets from a TM Transfer Frame data field.

Per CCSDS 133.0-B (Space Packet Protocol), packets are not guaranteed to
align with Transfer Frame boundaries: a packet may be split across two
consecutive frames. This module handles that "spillover" by returning
any incomplete trailing bytes so they can be prepended to the next
frame's data field before extraction continues.
"""
from pathlib import Path

from ccsds_tm_decom.generic_decoder import decode_fields, load_schema
from ccsds_tm_decom.pus import parse_pus_header

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "space_packet_header.json"
_SCHEMA = load_schema(_SCHEMA_PATH)
_HEADER_SIZE_BYTES = sum(f["bits"] for f in _SCHEMA["fields"]) // 8

# Per CCSDS 132.0-B: an all-ones First Header Pointer means no packet
# starts in this frame (the whole data field is a continuation).
NO_PACKET_START = (1 << 11) - 1  # 2047


def extract_space_packets(data_field: bytes, first_header_pointer: int) -> tuple[list[dict], bytes]:
    """
    Extract complete Space Packets from a single frame's data field.

    Args:
        data_field: Raw bytes of the Transfer Frame data field.
        first_header_pointer: Byte offset of the first new packet header
            within data_field (from the Transfer Frame Data Field Status).
            A value of NO_PACKET_START means no packet starts in this frame.

    Returns:
        A tuple (packets, leftover):
            packets: list of dicts, each containing the decoded Space
                Packet header fields plus a "raw_bytes" key with the full
                packet (header + data).
            leftover: trailing bytes belonging to a packet that is not yet
                complete in this frame. Pass this to the *next* frame's
                extraction call, prepended to its data field, so the
                packet can be completed.
    """
    if first_header_pointer == NO_PACKET_START:
        # Entire data field is a continuation of a packet from a previous frame
        return [], data_field

    packets: list[dict] = []
    offset = first_header_pointer

    while offset < len(data_field):
        header_bytes = data_field[offset:offset + _HEADER_SIZE_BYTES]
        if len(header_bytes) < _HEADER_SIZE_BYTES:
            break  # not enough bytes left for even a full header: leftover

        header = decode_fields(header_bytes, _SCHEMA)

        # Per CCSDS convention, packet_data_length = (data length - 1),
        # so total packet size = header (6) + packet_data_length + 1
        total_packet_length = _HEADER_SIZE_BYTES + header["packet_length"] + 1
        packet_end = offset + total_packet_length

        if packet_end > len(data_field):
            break  # packet continues beyond this frame: leftover

        packet_bytes = data_field[offset:packet_end]
        if header["secondary_header_flag"]:
            pus_header = parse_pus_header(packet_bytes[_HEADER_SIZE_BYTES:])
            packets.append({
                **header,
                "raw_bytes": packet_bytes,
                "pus_type": pus_header["service_type"],
                "pus_subtype": pus_header["service_subtype"],
            })
        else:
            packets.append({**header, "raw_bytes": packet_bytes, "pus_type": None, "pus_subtype": None})

        offset = packet_end

    leftover = data_field[offset:]
    return packets, leftover