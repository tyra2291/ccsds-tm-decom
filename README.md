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
