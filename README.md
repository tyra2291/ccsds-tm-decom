# ccsds-tm-decom

A CCSDS satellite telemetry frame decommutator, with configurable field
extraction and a layered pipeline for stripping ground segment encapsulation
(CORTEX, CADU, SLE).

## Context

CCSDS (Consultative Committee for Space Data Systems) is the standard used
by most satellite missions to structure telemetry data. Before reaching the
actual telemetry content, raw data streams are typically wrapped in several
layers of ground segment framing (e.g. CORTEX, CADU synchronization markers)
that must be stripped before the CCSDS frame itself can be decoded.

This project implements a generic, schema-driven decoder: instead of
hardcoding field positions and layer sizes in Python, both are described in
JSON configuration files. This makes the decoder reusable across different
missions or ground segment setups without changing code.

Built as a personal learning project to strengthen Python fundamentals
(project structure, testing, packaging) as part of a broader move toward
cloud/platform engineering — this codebase will progressively grow to
include a TCP ingestion layer, database storage, a web UI, containerization,
Kubernetes deployment, and Grafana monitoring.

## Current features

- Generic bitfield decoder: extracts named fields from raw bytes based on a
  JSON schema (field name + bit width), rather than hardcoded parsing logic
- Layered stripping pipeline: removes ground segment header/tail wrappers
  (e.g. CORTEX, CADU) in a configurable, ordered sequence
- Unit and integration tests (pytest) covering both the field decoder and
  the layer-stripping pipeline

## Roadmap

The following are planned but **not yet implemented**:

- Real-world CORTEX/CADU layer schemas validated against actual satellite
  telemetry frames
- Space Packet extraction from the CCSDS Transfer Frame data field
  (including spillover handling across frame boundaries)
- PUS-level packet decoding
- TCP listener for real-time, multi-satellite ingestion
- Persistent storage (PostgreSQL) of decoded frames/packets

## Design notes & current limitations

This decoder is generic within CCSDS/PUS, not protocol-agnostic beyond it.
Concretely:

- `generic_decoder.py` (bitfield extraction) and `pipeline.py` (ground
  segment layer stripping) are truly protocol-agnostic: field sizes,
  names, and wrapper sizes are all schema/config-driven.
- `decoder.py` and `packet.py`, however, assume a fixed protocol stack:
  CCSDS TM Transfer Frame → CCSDS Space Packet → PUS secondary header.
  The decoding logic itself (not just field sizes) is written in Python
  for this specific stack.

In practice, this means:
- Different field sizes, different CORTEX/CADU wrapper configurations, or
  different missions using the same CCSDS/PUS stack are supported purely
  through JSON configuration, with no code changes.
- A mission using CCSDS without PUS (a different or proprietary secondary
  header format), or a non-CCSDS protocol entirely, would require changes
  to `decoder.py` and `packet.py`, not just configuration.

This was a deliberate scope decision: building a fully protocol-agnostic
framework (pluggable handlers for arbitrary secondary header formats and
packet extraction logic) would add significant complexity for a use case
that, so far, only needs to support CCSDS/PUS across different missions
and ground segment configurations.