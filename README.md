# ccsds-tm-decom

A CCSDS/PUS satellite telemetry decommutator — a Python system that receives, decodes, stores, and visualizes satellite telemetry, from raw ground-segment-encapsulated bytes down to individual PUS packets.

## Why this project exists

This is a personal learning project, built with the help of Claude (Anthropic's AI assistant) as a hands-on way to strengthen Python fundamentals — project structure, testing, packaging, asynchronous programming.

The project was built incrementally, file by file and feature by feature: each new piece of functionality was implemented, then explained line by line before moving on to the next, with the explicit goal of actually understanding the code rather than just having it work. Every design choice — from the generic bitfield decoder to the layered pipeline architecture — was walked through and justified before being adopted. Claude wrote the code under this direction, including the web UI's layout and styling.

## Current features

- **Generic bitfield decoder**: extracts named fields from raw bytes based on a JSON schema (field name + bit width), rather than hardcoded parsing logic.
- **Layered ground-segment stripping**: removes header/tail wrappers (e.g. CORTEX, CADU sync markers) in a configurable, ordered sequence, including support for inter-frame padding.
- **Full CCSDS TM decode chain**: TM Transfer Frame primary header (modular schema-chain decoding), variable-length TM Secondary Header, a mission-specific Security Header, FECF (CRC-16) verification, OCF extraction, and Space Packet extraction with correct handling of spillover (packets split across consecutive frames).
- **PUS secondary header decoding**: service type/subtype extracted for every packet with a secondary header present.
- **Multiple ingestion modes**: a raw binary file reader (`io/batch.py`) and a real-time TCP client (`io/tcp_client.py`) that connects out to a telemetry front-end and decodes frames as they arrive.
- **PostgreSQL storage**: decoded frames and packets are persisted under named, metadata-rich acquisition sessions (connection type, host/port or file path, mission used), with cascading deletes.
- **CLI entry point** (`ccsds-tm-decom`): decode from a file or a live TCP stream, with storage optional.
- **Web UI + API** (FastAPI + vanilla JS): browse and filter existing sessions; create new sessions from a file upload or a live TCP connection (started as a background task); a "byte inspector" that decodes a pasted raw frame and visually color-codes which layer/field consumed which bytes; full mission config CRUD (create, edit, delete custom missions — the two default missions are protected from deletion); multi-value packet filtering (APID, PUS type/subtype, spacecraft, several values at once); PUS-based row highlighting (green for command acceptance/execution success, red for failure, orange for event anomalies); a live throughput indicator (frames/sec) for ongoing TCP sessions with automatic table refresh.
- **Containerized**: multi-stage Dockerfile and a `docker-compose.yml` with a `demo` profile separating the permanent stack (PostgreSQL + API) from optional demo services (a fake telemetry server + a decoder client pointed at it).
- **Test suite**: unit tests for every decoding module, integration tests validated against captured telemetry frames (including genuine Space Packet spillover across consecutive frames), and self-contained database tests using `testcontainers` (no pre-existing PostgreSQL instance required to run the test suite).

## Known limitations

- **Generic within CCSDS/PUS, not protocol-agnostic beyond it.** `generic_decoder.py` and `pipeline.py` are truly schema/config-driven — field sizes, names, and wrapper sizes require no code changes. `decoder.py` and `packet.py`, however, assume a fixed protocol stack (CCSDS TM Transfer Frame → CCSDS Space Packet → PUS secondary header) written directly in Python. A mission using CCSDS without PUS, or a non-CCSDS protocol entirely, would require code changes, not just configuration.
- **No connection handshake with the telemetry front-end.** `run_tcp_client` assumes the server starts pushing frames immediately upon connection. Real front-end systems (e.g. Safran's CORTEX) typically require a request/acknowledgment handshake before streaming telemetry — this would need to be added for use against a real front-end, but the exact message format is defined in vendor-proprietary interface specifications not implemented here.
- **The web UI's mission layer editor writes directly to the JSON config files on disk** — there's no versioning or audit trail for these edits beyond git history, and concurrent edits from two browser tabs could race.
- **Test data is synthetic/anonymized.** Fixture frames used in tests and demos have had spacecraft ID and APIDs remapped to random values (with FECF recomputed to keep frames valid) to avoid exposing any real mission-specific identifiers.

## Architecture

```
src/ccsds_tm_decom/
├── ccsds/                      # decoding of the CCSDS/PUS protocol itself
│   ├── generic_decoder.py      # generic engine: bits -> named fields, driven by a JSON schema
│   ├── frame.py                # TM Transfer Frame primary header (schema-chain decoding)
│   ├── secondary_header.py     # reads the (variable) length of the TF Secondary Header
│   ├── packet.py               # extracts Space Packets from a data field, handles spillover
│   └── pus.py                  # decodes PUS service type/subtype
│
├── ground_segment/             # everything specific to the ground segment, not CCSDS standard
│   ├── pipeline.py             # strips CORTEX/CADU-style layers (configurable via JSON)
│   ├── trailer.py              # verifies FECF (CRC-16), extracts OCF
│   └── mission_config.py       # bundles frame_size + layers + security_header_bytes into one config
│
├── orchestration/
│   └── decoder.py              # process_frame(): assembles everything above to decode ONE frame,
│                                #   tracking Space Packet spillover leftover between calls
│
├── io/                         # entry/exit points: where frames come from, where results go
│   ├── batch.py                # reads a FILE of frames, loops over process_frame
│   ├── tcp_client.py           # connects to a telemetry server, loops over process_frame in real time
│   └── storage.py              # writes FrameResult objects to PostgreSQL, under a named session
│
├── inspector.py                # annotated decode for the UI's byte inspector: same pipeline,
│                                #   but records byte ranges instead of only values
│
├── api/
│   ├── app.py                  # FastAPI backend: sessions, packets, missions CRUD, inspector, uploads
│   └── static/index.html       # single-page web UI (vanilla JS, no build step)
│
├── main.py                     # CLI entry point: wires mission config + storage (optional) +
│                                #   chosen input source (tcp/file) together
│
└── schemas/                    # all JSON configs: field schemas, ground segment layers, missions
```

### How the pieces call each other

`main.py` (CLI) or `api/app.py` (web) are the only places that decide *where frames come from* and *where results go* — every module below them is agnostic to both:

```
[CLI or API] ──creates──> pool, session, on_frame callback
      │
      ├──> io.tcp_client.run_tcp_client(..., on_frame)     [real-time]
      │         loop: read exact-size frame → orchestration.decoder.process_frame() → on_frame(result)
      │
      └──> io.batch.process_file(...)                      [file]
                loop: read exact-size frame → orchestration.decoder.process_frame() → results list

orchestration.decoder.process_frame() calls, in order:
   ground_segment.pipeline.run_pipeline()       → strip CORTEX/CADU layers
   ccsds.frame.parse_tf_primary_header()        → TF header fields
   ccsds.secondary_header.parse_secondary_header_length()
   ground_segment.trailer.verify_trailer()      → FECF/OCF
   ccsds.packet.extract_space_packets()         → Space Packets (calls ccsds.pus.parse_pus_header()
                                                    internally when a secondary header is present)

on_frame(result), when storage is enabled, is io.storage.store_frame_result
(pool and session_id pre-bound via functools.partial in make_storage_callback) —
tcp_client.py and batch.py never import storage.py directly; the CLI/API wires them together.
```

`inspector.py` mirrors the same decoding sequence as `process_frame`, but records the byte range consumed by each step instead of discarding that information — it exists purely to power the UI's visual byte breakdown, and shares the same underlying schema/layer logic rather than duplicating it.

## Tests

Run with:
```bash
poetry run pytest -v
```

- Unit tests for each decoding module (`ccsds/`, `ground_segment/`) using hand-crafted byte sequences.
- Integration tests using captured telemetry frames, including a test that validates genuine Space Packet spillover across two consecutive frames.
- Database tests (`test_storage.py`, `test_integration_tcp_storage.py`) use `testcontainers` to spin up an ephemeral PostgreSQL container automatically — no pre-existing database instance is required to run the full suite, which also means these tests work unmodified in CI.

## Tech stack

Python 3.14, Poetry, pytest, testcontainers, asyncpg, FastAPI, Docker/docker-compose, PostgreSQL.

## Installation & usage

```bash
git clone git@github.com:YOUR_USERNAME/ccsds-tm-decom.git
cd ccsds-tm-decom
poetry install
poetry run pytest -v
```

**Run everything via Docker** (recommended):
```bash
docker compose up --build              # PostgreSQL + API/UI only
docker compose --profile demo up --build  # + a fake telemetry server + a decoder connected to it
```
Then open `http://localhost:8000`.

## Roadmap / not yet implemented

- **CI/CD**: GitHub Actions to run the test suite and build/push the Docker image automatically on push.
- **Kubernetes**: deployment manifests (Deployments, Services, ConfigMaps, Secrets) to run the stack on a cluster, pulling the image built by CI.
- **Grafana/Prometheus**: metrics export and dashboards for monitoring decode throughput and error rates.