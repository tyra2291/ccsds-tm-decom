"""
Prometheus metrics for decode throughput, incremented centrally in
storage.store_frame_result so every ingestion path (TCP live, file
upload, CLI) reports consistently without each caller needing to know
about metrics.
"""
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

frames_decoded_total = Counter(
    "ccsds_frames_decoded_total",
    "Total number of TM Transfer Frames successfully decoded and stored.",
    ["mission_name"],
)

packets_decoded_total = Counter(
    "ccsds_packets_decoded_total",
    "Total number of Space Packets extracted and stored.",
    ["mission_name", "is_idle"],
)


def render_metrics() -> tuple[bytes, str]:
    """
    Render current metrics in Prometheus text exposition format.

    Returns:
        A tuple of (body_bytes, content_type), ready to return directly
        from a FastAPI endpoint.
    """
    return generate_latest(), CONTENT_TYPE_LATEST