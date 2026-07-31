# src/ccsds_tm_decom/frame.py
from pathlib import Path

from ccsds_tm_decom.ccsds.generic_decoder import decode_fields, load_schema

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def decode_schema_chain(data: bytes, schema_filenames: list[str]) -> dict:
    """
    Decode a sequence of contiguous binary structures, each described by
    its own JSON schema, and merge the results into a single dict.

    Each schema in the chain consumes exactly as many bytes as its fields
    require (sum of bit widths / 8), then the next schema starts right
    after. This models CCSDS structures composed of multiple standalone
    sub-structures placed back to back (e.g. Frame Primary Header followed
    by Transfer Frame Data Field Status).

    Args:
        data: Raw bytes containing all structures in the chain, back to back.
        schema_filenames: Ordered list of JSON schema filenames (relative to
            the schemas/ directory) to apply in sequence.

    Returns:
        A single dict merging all decoded fields from every schema in the
        chain, in order. Field names are expected to be unique across
        schemas — a name collision will silently overwrite a prior value.
    """
    result: dict = {}
    offset_bytes = 0

    for filename in schema_filenames:
        schema = load_schema(_SCHEMAS_DIR / filename)
        size_bytes = sum(f["bits"] for f in schema["fields"]) // 8

        chunk = data[offset_bytes:offset_bytes + size_bytes]
        result.update(decode_fields(chunk, schema))

        offset_bytes += size_bytes

    return result


def parse_tf_primary_header(data: bytes) -> dict:
    """
    Decode the full CCSDS TM Transfer Frame primary header, composed of
    the Frame Primary Header (4 bytes) followed by the Transfer Frame
    Data Field Status (2 bytes) — 6 bytes total, per CCSDS 132.0-B.

    Args:
        data: Raw bytes, at least 6 bytes long.

    Returns:
        A dict with all fields from both sub-structures merged together
        (e.g. "spacecraft_id", "first_header_pointer", etc.).
    """
    return decode_schema_chain(
        data,
        ["tf_frame_primary_header.json", "tf_data_field_status.json"],
    )