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
    total_length_bits = len(data) * 8
    required_bits = sum(f["bits"] for f in schema["fields"])

    if required_bits > total_length_bits:
        raise ValueError(
            f"Not enough data to decode schema '{schema.get('name', '?')}': "
            f"needs {required_bits} bits ({required_bits // 8} bytes), "
            f"got only {total_length_bits} bits ({len(data)} bytes). "
            f"This usually means the wrong ground segment layers/mission "
            f"config was used for this data."
        )

    total_bits = int.from_bytes(data, byteorder="big")
    result: dict[str, int] = {}
    offset = 0
    for field in schema["fields"]:
        bits = field["bits"]
        shift = total_length_bits - offset - bits
        mask = (1 << bits) - 1
        result[field["name"]] = (total_bits >> shift) & mask
        offset += bits
    return result