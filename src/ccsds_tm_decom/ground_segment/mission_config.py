"""
Mission configuration: bundles frame_size, ground segment layers, and
mission-specific security header size into a single JSON file, so a
deployment only needs to reference one config rather than juggling
several separate flags/files.

Note: the layer-parsing logic here (JSON dict -> list[Layer]) mirrors
pipeline.load_layers, but can't simply call it, since load_layers opens
its own file from a path and this module has already parsed the whole
mission JSON (which bundles frame_size/security_header_bytes alongside
the layers in the same file) into memory.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from ccsds_tm_decom.ground_segment.pipeline import Layer


@dataclass
class MissionConfig:
    """
    Complete decoding configuration for one mission/ground segment setup.

    Attributes:
        frame_size: Exact byte size of each raw incoming frame.
        security_header_bytes: Mission-specific security header size (see
            orchestration.decoder.process_frame).
        layers: Ordered list of ground segment layers to strip (see
            ground_segment.pipeline.run_pipeline).
    """
    frame_size: int
    security_header_bytes: int
    layers: list[Layer]


def load_mission_config(path: str | Path) -> MissionConfig:
    """
    Load a mission configuration from a JSON file.

    Expected JSON shape:
        {
          "frame_size": 994,
          "security_header_bytes": 14,
          "layers": [
            {"name": "...", "header_bytes": ..., "tail_bytes": ..., ...}
          ]
        }

    Args:
        path: Path to the mission config JSON file.

    Returns:
        A populated MissionConfig. security_header_bytes defaults to 0
        if omitted from the JSON (missions with no such field).
    """
    with open(path) as f:
        raw = json.load(f)

    layers = [Layer(**layer) for layer in raw["layers"]]

    return MissionConfig(
        frame_size=raw["frame_size"],
        security_header_bytes=raw.get("security_header_bytes", 0),
        layers=layers,
    )