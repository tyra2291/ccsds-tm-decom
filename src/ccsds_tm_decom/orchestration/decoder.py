"""
End-to-end orchestration: strip ground segment layers, decode the TM
Transfer Frame primary header (and secondary header, if present), verify
the trailer, and extract Space Packets — handling packet spillover
across successive frames.
"""
from dataclasses import dataclass, field

from ccsds_tm_decom.ccsds.frame import parse_tf_primary_header
from ccsds_tm_decom.ccsds.packet import NO_PACKET_START, extract_space_packets
from ccsds_tm_decom.ground_segment.pipeline import Layer, run_pipeline
from ccsds_tm_decom.ccsds.secondary_header import parse_secondary_header_length
from ccsds_tm_decom.ground_segment.trailer import FECF_LENGTH_BYTES, OCF_LENGTH_BYTES, verify_trailer

_TF_HEADER_SIZE_BYTES = 6


@dataclass
class FrameResult:
    """
    Result of decoding a single TM Transfer Frame.
    """
    tf_header: dict
    trailer: dict
    packets: list = field(default_factory=list)
    leftover: bytes = b""


def process_frame(
    raw_bytes: bytes,
    layers: list[Layer],
    leftover: bytes = b"",
    security_header_bytes: int = 0,
) -> FrameResult:
    """
    Decode a single raw ground-segment-wrapped TM Transfer Frame end to end.

    Args:
        raw_bytes: The full raw frame as received, ground segment
            encapsulation included.
        layers: Ordered list of Layer objects for ground segment stripping.
        leftover: Incomplete packet bytes carried over from the previous
            frame's `FrameResult.leftover`. Pass b"" for the first frame.
        security_header_bytes: Size, in bytes, of a mission-specific
            security header immediately following the (variable-length)
            standard TF Secondary Header, when secondary_header_flag is
            set. This is not part of the CCSDS standard itself — it's a
            per-mission configuration value, similar to ground segment
            layer sizes. Pass 0 if no such field is used.

    Returns:
        A FrameResult with the decoded header, trailer verification,
        any complete packets found, and leftover bytes to pass into the
        next call to process_frame.
    """
    tf_frame = run_pipeline(raw_bytes, layers)

    tf_header = parse_tf_primary_header(tf_frame)
    ocf_present = bool(tf_header["ocf_flag"])

    offset = _TF_HEADER_SIZE_BYTES
    if tf_header["secondary_header_flag"]:
        sec_hdr_len = parse_secondary_header_length(tf_frame[offset:])
        offset += sec_hdr_len + security_header_bytes

    trailer_size = FECF_LENGTH_BYTES + (OCF_LENGTH_BYTES if ocf_present else 0)
    trailer_result = verify_trailer(tf_frame, ocf_present)

    data_field = tf_frame[offset: len(tf_frame) - trailer_size]
    combined_data = leftover + data_field

    first_header_pointer = tf_header["first_header_pointer"]

    if first_header_pointer == NO_PACKET_START:
        return FrameResult(
            tf_header=tf_header,
            trailer=trailer_result,
            packets=[],
            leftover=combined_data,
        )

    adjusted_pointer = len(leftover) + first_header_pointer
    packets, new_leftover = extract_space_packets(combined_data, adjusted_pointer)

    return FrameResult(
        tf_header=tf_header,
        trailer=trailer_result,
        packets=packets,
        leftover=new_leftover,
    )