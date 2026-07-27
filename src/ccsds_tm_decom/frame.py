# src/ccsds_tm_decom/frame.py
from pathlib import Path

from ccsds_tm_decom.generic_decoder import decode_fields, load_schema

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "ccsds_primary_header.json"
_SCHEMA = load_schema(_SCHEMA_PATH)


def parse_primary_header(data: bytes) -> dict:
    """
    Decode the CCSDS primary header from raw bytes using the default schema.

    Args:
        data: Raw bytes, at least as long as the schema requires.

    Returns:
        A dict mapping field names (as defined in the schema) to their
        decoded integer values. The exact keys depend entirely on the
        loaded schema, not on any fixed Python structure.
    """
    header_size_bytes = sum(f["bits"] for f in _SCHEMA["fields"]) // 8
    if len(data) < header_size_bytes:
        raise ValueError(f"Header CCSDS incomplet ({header_size_bytes} bytes minimum requis)")

    return decode_fields(data[:header_size_bytes], _SCHEMA)