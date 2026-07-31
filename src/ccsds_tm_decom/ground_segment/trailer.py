"""
Handling of the CCSDS TM Transfer Frame trailer: the Operational Control
Field (OCF, optional, 4 bytes) and the Frame Error Control Field (FECF,
optional, 2 bytes), as defined in CCSDS 132.0-B.

Unlike primary header fields, the FECF is not a named value to extract —
it's a checksum that must be recomputed from the frame body and compared
against the received value to detect transmission errors.
"""

FECF_LENGTH_BYTES = 2
OCF_LENGTH_BYTES = 4

# CRC-16/CCITT-FALSE parameters, as conventionally used for the CCSDS FECF
_CRC16_POLY = 0x1021
_CRC16_INIT = 0xFFFF


def compute_fecf(data: bytes) -> int:
    """
    Compute a CRC-16/CCITT-FALSE checksum over the given bytes.

    This is the algorithm conventionally used for the CCSDS Frame Error
    Control Field: polynomial 0x1021, initial value 0xFFFF, no final XOR.

    Args:
        data: Bytes to checksum (the full frame, excluding the FECF itself).

    Returns:
        The computed 16-bit CRC value.
    """
    crc = _CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ _CRC16_POLY
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def verify_trailer(frame: bytes, ocf_present: bool) -> dict:
    """
    Extract the OCF (if present) and validate the FECF of a TM Transfer Frame.

    The FECF is always the last 2 bytes of the frame. If present, the OCF
    sits just before it (4 bytes). The FECF is computed over everything
    preceding it (header + data field + OCF if present).

    Args:
        frame: The complete transfer frame bytes, trailer included.
        ocf_present: Whether the OCF is present, as indicated by the
            "ocf_flag" field already decoded from the frame primary header.

    Returns:
        A dict with:
            - "ocf": the 4 raw OCF bytes, or None if not present
            - "fecf_received": the FECF value read from the frame
            - "fecf_computed": the FECF value recomputed from the frame body
            - "fecf_valid": True if received and computed FECF match
    """
    fecf_received = int.from_bytes(frame[-FECF_LENGTH_BYTES:], byteorder="big")
    fecf_computed = compute_fecf(frame[:-FECF_LENGTH_BYTES])

    ocf = None
    if ocf_present:
        ocf_start = -(FECF_LENGTH_BYTES + OCF_LENGTH_BYTES)
        ocf_end = -FECF_LENGTH_BYTES
        ocf = frame[ocf_start:ocf_end]

    return {
        "ocf": ocf,
        "fecf_received": fecf_received,
        "fecf_computed": fecf_computed,
        "fecf_valid": fecf_received == fecf_computed,
    }