import json
from pathlib import Path


def load_schema(path: str | Path) -> dict:
    """
    Load a CCSDS field schema from a JSON file.

    The schema defines an ordered list of bit-level fields (name + bit width)
    that describe how to decode a fixed-size binary structure such as a
    CCSDS primary header. This function only handles file I/O and JSON
    parsing; the actual bit decoding happens in `decode_fields`.

    Args:
        path: Path to the JSON schema file (string or Path object).

    Returns:
        A dict representing the parsed JSON schema, expected to contain
        a "fields" key holding a list of {"name": str, "bits": int} entries.
    """
    with open(path) as f:
        return json.load(f)


def decode_fields(data: bytes, schema: dict) -> dict:
    """
    Decode a fixed-size byte sequence into named fields using a bit-level schema.

    This is a generic bitfield parser: it treats the entire input as one
    large integer, then extracts each field by shifting the relevant bits
    down to the least-significant position and masking off everything else.
    This avoids hardcoding field positions in Python code — any structure
    (CCSDS primary header, PUS secondary header, custom ground segment
    wrappers, etc.) can be described purely via the JSON schema.

    Args:
        data: Raw bytes to decode. Must contain at least as many bits as
            the sum of all field widths in the schema.
        schema: A dict with a "fields" key, e.g.:
            {"fields": [{"name": "version", "bits": 3}, ...]}
            Fields are decoded in the order they appear, most-significant
            bit first.

    Returns:
        A dict mapping each field name to its decoded integer value,
        e.g. {"version": 0, "apid": 100, ...}.
    """
    # Treat the whole byte sequence as one big integer for easy bit manipulation
    total_bits = int.from_bytes(data, byteorder="big")
    total_length_bits = len(data) * 8

    result: dict[str, int] = {}
    offset = 0  # how many bits we've already consumed from the start

    for field in schema["fields"]:
        bits = field["bits"]

        # Shift amount needed to bring this field down to bit position 0
        shift = total_length_bits - offset - bits

        # Mask with `bits` ones (e.g. bits=3 -> 0b111) to isolate the field
        mask = (1 << bits) - 1

        # Shift right then mask: extracts exactly this field's value
        result[field["name"]] = (total_bits >> shift) & mask

        offset += bits

    return result