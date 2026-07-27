from ccsds_tm_decom.trailer import compute_fecf, verify_trailer


def test_verify_trailer_valid_fecf():
    """
    Verify that a correctly computed FECF is recognized as valid, and that
    a corrupted FECF is correctly flagged as invalid.
    """
    body = bytes([0x08, 0x64, 0xC0, 0x00, 0x00, 0x05])  # simulated frame content
    fecf = compute_fecf(body)
    frame = body + fecf.to_bytes(2, byteorder="big")

    result = verify_trailer(frame, ocf_present=False)

    assert result["ocf"] is None
    assert result["fecf_valid"] is True


def test_verify_trailer_invalid_fecf():
    """A tampered FECF must be detected as invalid."""
    body = bytes([0x08, 0x64, 0xC0, 0x00, 0x00, 0x05])
    frame = body + bytes([0x00, 0x00])  # deliberately wrong FECF

    result = verify_trailer(frame, ocf_present=False)

    assert result["fecf_valid"] is False