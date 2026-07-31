"""
CCSDS TM Transfer Frame Secondary Header parsing.

Per CCSDS 132.0-B, the Transfer Frame Secondary Header is variable-length:
its first byte encodes a 2-bit version number and a 6-bit length field.
The length field holds (actual_length_in_bytes - 1), so the true header
length must be read from the data itself rather than assumed fixed.
"""


def parse_secondary_header_length(data: bytes) -> int:
    """
    Determine the actual byte length of the TM Transfer Frame Secondary
    Header from its first byte.

    Args:
        data: Bytes starting at the first byte of the secondary header.

    Returns:
        The actual length in bytes of the secondary header (including its
        own length byte), per CCSDS 132.0-B: (length_field + 1).
    """
    first_byte = data[0]
    length_field = first_byte & 0b00111111  # low 6 bits
    return length_field + 1