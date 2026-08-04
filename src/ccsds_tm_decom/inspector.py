"""
Byte-range annotation for a single raw frame: walks the same decoding
pipeline as orchestration.decoder.process_frame, but instead of only
returning decoded values, records which byte range each layer/field
consumed. Used to power a visual "byte inspector" in the web UI.
"""
from pathlib import Path

from ccsds_tm_decom.ccsds.generic_decoder import decode_fields, load_schema
from ccsds_tm_decom.ccsds.packet import NO_PACKET_START, decode_packet_header_only
from ccsds_tm_decom.ccsds.pus import parse_pus_header
from ccsds_tm_decom.ccsds.secondary_header import parse_secondary_header_length
from ccsds_tm_decom.ground_segment.mission_config import MissionConfig
from ccsds_tm_decom.ground_segment.trailer import (
    FECF_LENGTH_BYTES,
    OCF_LENGTH_BYTES,
    compute_fecf,
)


def _region(start: int, end: int, label: str, category: str, detail: dict | None = None) -> dict:
    """Build one annotated byte-range region for the inspector output."""
    return {"start": start, "end": end, "label": label, "category": category, "detail": detail}


def inspect_frame(raw: bytes, mission: MissionConfig) -> list[dict]:
    """
    Decode a single raw frame, recording the byte range consumed by each
    ground segment layer, TF header field group, and extracted Space
    Packet, for visual display in the UI.

    Args:
        raw: The full raw frame bytes, ground segment encapsulation included.
        mission: The mission config (layers, security_header_bytes) to
            apply, same as used by orchestration.decoder.process_frame.

    Returns:
        A list of region dicts, in byte order, each with start/end
        offsets (relative to `raw`), a human-readable label, a category
        (for color-coding in the UI), and optional decoded detail.
    """
    regions: list[dict] = []
    cursor = 0
    remaining = raw

    # --- 1. Ground segment layers ---
    for layer in mission.layers:
        abs_start = cursor

        if layer.header_bytes:
            regions.append(_region(
                abs_start, abs_start + layer.header_bytes,
                f"{layer.name} — header", "layer-header",
            ))

        content_start = abs_start + layer.header_bytes

        if layer.inner_frame_length is not None:
            content_end = content_start + layer.inner_frame_length
        elif layer.tail_bytes:
            content_end = abs_start + len(remaining) - layer.tail_bytes
        else:
            content_end = abs_start + len(remaining)

        tail_start = abs_start + len(remaining) - layer.tail_bytes if layer.tail_bytes else content_end

        if tail_start > content_end:
            regions.append(_region(
                content_end, tail_start, f"{layer.name} — padding", "layer-padding",
            ))

        if layer.tail_bytes:
            tail_bytes_actual = raw[tail_start:tail_start + layer.tail_bytes]
            detail = {"hex": tail_bytes_actual.hex().upper()}
            if layer.expected_tail_hex:
                detail["expected"] = layer.expected_tail_hex.upper()
                detail["valid"] = tail_bytes_actual.hex().upper() == layer.expected_tail_hex.upper()
            regions.append(_region(
                tail_start, tail_start + layer.tail_bytes,
                f"{layer.name} — tail", "layer-tail", detail,
            ))

        remaining = raw[content_start:content_end]
        cursor = content_start

    tf_frame_start = cursor
    tf_frame = remaining

    # --- 2. TF primary header (two schema blocks) ---
    schema_dir_fields = [
        ("tf_frame_primary_header.json", "TF Frame Primary Header"),
        ("tf_data_field_status.json", "TF Data Field Status"),
    ]
    schemas_dir = Path(__file__).parent / "schemas"
    offset = 0
    tf_header_fields: dict = {}
    for filename, label in schema_dir_fields:
        schema = load_schema(schemas_dir / filename)
        size_bytes = sum(f["bits"] for f in schema["fields"]) // 8
        chunk = tf_frame[offset:offset + size_bytes]
        decoded = decode_fields(chunk, schema)
        tf_header_fields.update(decoded)
        regions.append(_region(
            tf_frame_start + offset, tf_frame_start + offset + size_bytes,
            label, "tf-header", decoded,
        ))
        offset += size_bytes

    # --- 3. TF Secondary Header + Security Header (if present) ---
    if tf_header_fields.get("secondary_header_flag"):
        sec_len = parse_secondary_header_length(tf_frame[offset:])
        regions.append(_region(
            tf_frame_start + offset, tf_frame_start + offset + sec_len,
            "TF Secondary Header", "tf-secondary",
        ))
        offset += sec_len

        if mission.security_header_bytes:
            regions.append(_region(
                tf_frame_start + offset, tf_frame_start + offset + mission.security_header_bytes,
                "Security Header (mission-specific)", "security-header",
            ))
            offset += mission.security_header_bytes

    # --- 4. Trailer boundaries ---
    ocf_present = bool(tf_header_fields.get("ocf_flag"))
    trailer_size = FECF_LENGTH_BYTES + (OCF_LENGTH_BYTES if ocf_present else 0)
    data_field_end = len(tf_frame) - trailer_size
    data_field = tf_frame[offset:data_field_end]
    data_field_start = tf_frame_start + offset

    # --- 5. Space Packets within the data field ---
    fhp = tf_header_fields.get("first_header_pointer", NO_PACKET_START)
    if fhp != NO_PACKET_START:
        pos = fhp
        if pos > 0:
            regions.append(_region(
                data_field_start, data_field_start + pos,
                "Spillover (continuation of previous packet)", "spillover",
            ))
        while pos < len(data_field):
            header_info = decode_packet_header_only(data_field[pos:pos + 6])
            if header_info is None:
                break
            total_len = 6 + header_info["packet_length"] + 1
            if pos + total_len > len(data_field):
                break

            packet_body = data_field[pos:pos + total_len]
            pus_label = ""
            pus_detail = dict(header_info)
            if header_info["secondary_header_flag"]:
                try:
                    pus = parse_pus_header(packet_body[6:])
                    pus_detail.update(pus)
                    pus_label = f" — PUS {pus['service_type']}/{pus['service_subtype']}"
                except ValueError:
                    pass

            is_idle = header_info["apid"] == 2047
            apid_label = "IDLE" if is_idle else f"APID {header_info['apid']}"
            category = "packet-idle" if is_idle else "packet-real"
            regions.append(_region(
                data_field_start + pos, data_field_start + pos + total_len,
                f"Packet — {apid_label}{pus_label}", category, pus_detail,
            ))
            pos += total_len

        if pos < len(data_field):
            regions.append(_region(
                data_field_start + pos, data_field_start + len(data_field),
                "Unparsed remainder (decode stopped here — possibly truncated or malformed)",
                "unparsed",
            ))
    else:
        regions.append(_region(
            data_field_start, data_field_start + len(data_field),
            "Data field (continuation, no new packet)", "spillover",
        ))

    # --- 6. OCF / FECF ---
    trailer_start = tf_frame_start + data_field_end
    if ocf_present:
        regions.append(_region(
            trailer_start, trailer_start + OCF_LENGTH_BYTES,
            "OCF (Operational Control Field)", "ocf",
        ))
        trailer_start += OCF_LENGTH_BYTES

    fecf_received = int.from_bytes(tf_frame[-FECF_LENGTH_BYTES:], "big")
    fecf_computed = compute_fecf(tf_frame[:-FECF_LENGTH_BYTES])
    regions.append(_region(
        trailer_start, trailer_start + FECF_LENGTH_BYTES,
        "FECF (CRC)", "fecf",
        {"received": f"{fecf_received:04X}", "computed": f"{fecf_computed:04X}", "valid": fecf_received == fecf_computed},
    ))

    return regions