"""
PUS (Packet Utilization Standard, ECSS-E-ST-70-41) secondary header
parsing. Only decodes the service type/subtype fields — the minimum
needed to identify what kind of telemetry a packet carries. Applies only
to Space Packets whose CCSDS primary header has secondary_header_flag set.
"""
from pathlib import Path

from ccsds_tm_decom.generic_decoder import decode_fields, load_schema

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "pus_secondary_header.json"
_SCHEMA = load_schema(_SCHEMA_PATH)
_HEADER_SIZE_BYTES = sum(f["bits"] for f in _SCHEMA["fields"]) // 8


def parse_pus_header(packet_body: bytes) -> dict:
    """
    Decode the PUS secondary header from the bytes immediately following
    a Space Packet's 6-byte CCSDS primary header.

    Args:
        packet_body: Bytes starting right after the CCSDS primary header
            (i.e. packet.raw_bytes[6:]).

    Returns:
        A dict with pus_version, ack_flags, service_type, service_subtype.
    """
    return decode_fields(packet_body[:_HEADER_SIZE_BYTES], _SCHEMA)