# ccsds-tm-decom

A CCSDS/PUS satellite telemetry decommutator — a Python system that receives, decodes, stores, and visualizes satellite telemetry, from raw ground-segment-encapsulated bytes down to individual PUS packets.

## Why this project exists

This is a personal learning project, built with the help of Claude (Anthropic's AI assistant) as a hands-on way to strengthen Python fundamentals — project structure, testing, packaging, asynchronous programming — and to get hands-on experience with the platform engineering tools that surround an application: containerization, CI/CD, and Kubernetes.

The project was built incrementally, file by file and feature by feature: each new piece of functionality was implemented, then explained line by line before moving on to the next, with the explicit goal of actually understanding the code rather than just having it work. Every design choice — from the generic bitfield decoder to the layered pipeline architecture to the Kubernetes deployment topology — was walked through and justified before being adopted. Claude wrote the code under this direction, including the web UI's layout and styling.

## Quick start

First, set up your local secrets (never committed to git):
```bash
cp .env.example .env
```
Then edit `.env` and set a real value for `POSTGRES_PASSWORD`.

### Option A — Docker Compose (simplest)

```bash
git clone git@github.com:tyra2291/ccsds-tm-decom.git
cd ccsds-tm-decom
cp .env.example .env   # edit POSTGRES_PASSWORD before continuing
docker compose up --build
```
Open `http://localhost:8000`.

Add `--profile demo` to also start a fake telemetry server and a decoder client connected to it, for an automatic live demo:
```bash
docker compose --profile demo up --build
```

### Option B — Kubernetes (local, via Minikube)

```bash
git clone git@github.com:tyra2291/ccsds-tm-decom.git
cd ccsds-tm-decom
cp .env.example .env   # edit POSTGRES_PASSWORD before continuing
minikube start
./k8s/deploy.sh
```
Open `http://localhost:8000`. `deploy.sh` applies all manifests, generates the PostgreSQL Secret and the API's ConfigMap directly in the cluster from `.env` (neither is ever written to a committed YAML file), waits for both Deployments to be ready, and finishes by running `kubectl port-forward` in the foreground — press Ctrl+C to stop.

### Running the test suite

```bash
poetry install
poetry run pytest -v
```

## Current features

- **Generic bitfield decoder**: extracts named fields from raw bytes based on a JSON schema (field name + bit width), rather than hardcoded parsing logic.
- **Layered ground-segment stripping**: removes header/tail wrappers (e.g. CORTEX, CADU sync markers) in a configurable, ordered sequence, including support for inter-frame padding.
- **Full CCSDS TM decode chain**: TM Transfer Frame primary header (modular schema-chain decoding), variable-length TM Secondary Header, a mission-specific Security Header, FECF (CRC-16) verification, OCF extraction, and Space Packet extraction with correct handling of spillover (packets split across consecutive frames).
- **PUS secondary header decoding**: service type/subtype extracted for every packet with a secondary header present.
- **Multiple ingestion modes**: a raw binary file reader (`io/batch.py`) and a real-time TCP client (`io/tcp_client.py`) that connects out to a telemetry front-end and decodes frames as they arrive.
- **PostgreSQL storage**: decoded frames and packets are persisted under named, metadata-rich acquisition sessions (connection type, host/port or file path, mission used), with cascading deletes.
- **CLI entry point** (`ccsds-tm-decom`): decode from a file or a live TCP stream, with storage optional.
- **Web UI + API** (FastAPI + vanilla JS): browse and filter existing sessions; create new sessions from a file upload or a live TCP connection (started as a background task); a "byte inspector" that decodes a pasted raw frame and visually color-codes which layer/field consumed which bytes, with an example frame available at a click; full mission config CRUD (create, edit, delete custom missions — the two default missions are protected from deletion); multi-value packet filtering (APID, PUS type/subtype, spacecraft, several values at once, applied instantly on checkbox toggle); PUS-based row highlighting (green for command acceptance/execution success, red for failure, orange for event anomalies); a live throughput indicator (frames/sec) for ongoing TCP sessions with automatic table refresh.
- **Containerized**: multi-stage Dockerfile and a `docker-compose.yml` with a `demo` profile separating the permanent stack (PostgreSQL + API) from optional demo services (a fake telemetry server + a decoder client pointed at it).
- **CI/CD** (GitHub Actions): the test suite runs on every push and pull request. Pushing a version tag (`v*.*.*`) additionally builds a multi-architecture (amd64/arm64) Docker image and publishes it to GitHub Container Registry.
- **Kubernetes deployment**: manifests for a local Minikube cluster — a PostgreSQL Deployment with persistent storage and automatic schema initialization, and an API Deployment pulling the image built by CI, wired together with Services; `deploy.sh` applies everything, waits for readiness, and opens the port-forward.
- **Secrets kept out of git**: a local, gitignored `.env` file (with `.env.example` as a template) supplies the database password to both Docker Compose and the Kubernetes deployment script — no credentials are ever committed to a YAML or Compose file.
- **Test suite**: unit tests for every decoding module, integration tests validated against captured telemetry frames (including genuine Space Packet spillover across consecutive frames), and self-contained database tests using `testcontainers` (no pre-existing PostgreSQL instance required to run the test suite).

## Known limitations

- **Generic within CCSDS/PUS, not protocol-agnostic beyond it.** `generic_decoder.py` and `pipeline.py` are truly schema/config-driven — field sizes, names, and wrapper sizes require no code changes. `decoder.py` and `packet.py`, however, assume a fixed protocol stack (CCSDS TM Transfer Frame → CCSDS Space Packet → PUS secondary header) written directly in Python. A mission using CCSDS without PUS, or a non-CCSDS protocol entirely, would require code changes, not just configuration.
- **No connection handshake with the telemetry front-end.** `run_tcp_client` assumes the server starts pushing frames immediately upon connection. Real front-end systems (e.g. Safran's CORTEX) typically require a request/acknowledgment handshake before streaming telemetry — this would need to be added for use against a real front-end, but the exact message format is defined in vendor-proprietary interface specifications not implemented here.
- **The web UI's mission layer editor writes directly to the JSON config files on disk** — there's no versioning or audit trail for these edits beyond git history, and concurrent edits from two browser tabs could race.
- **Test data is synthetic/anonymized.** Fixture frames used in tests and demos have had spacecraft ID and APIDs remapped to random values (with FECF recomputed to keep frames valid) to avoid exposing any real mission-specific identifiers.
- **Secrets are kept out of git via a local `.env` file** (see `.env.example`), never committed. For Kubernetes, the Secret and ConfigMap carrying the database credentials are generated on the fly by `deploy.sh` rather than stored as static YAML — but the underlying K8s `Secret` mechanism still only base64-encodes values rather than encrypting them, which is adequate for local learning but not for a real deployment (which would need a tool like Vault or Sealed Secrets).
- **No Ingress or LoadBalancer.** The API is reached via `kubectl port-forward` in local Minikube; a real cluster deployment would use an Ingress controller or a cloud LoadBalancer instead.

## How this project was worked on

Each feature was built through the same loop: implement a small piece, run it, fix whatever broke, then explain every new line of code before moving to the next piece. This applied equally to the Python decoding logic, the Docker/Compose setup, the GitHub Actions workflow, and the Kubernetes manifests — the goal throughout was understanding *why* each piece works the way it does, not just accumulating working code. Real captured satellite telemetry (from an actual ground-segment simulator log) was used from early on to validate the decoder against genuine data rather than only hand-crafted test bytes, and several real bugs (a missing bit in a header offset, a silently-shadowed route definition, a stale ground-segment layer config, a hardcoded password later removed from every committed file) were found and fixed this way.

## Architecture: the code (`src/ccsds_tm_decom/`)

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

### How the source files call each other

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

## Architecture: Docker

```
Dockerfile (multi-stage)
  Stage "builder": installs Poetry + dependencies into a venv
  Stage "runtime": copies only that venv + the source code — no Poetry,
                    no build cache, no dev dependencies in the final image

docker-compose.yml (reads secrets from .env, never hardcoded)
  postgres        (always started)  — official postgres:16 image, with a healthcheck
  api             (always started)  — built from the Dockerfile, runs uvicorn
  fake-server     (profile: demo)   — same image, runs a script that emulates a telemetry front-end
  decoder         (profile: demo)   — same image, runs the CLI against fake-server
```

Every non-`postgres` service shares the **same built image** — only the `command:` differs. Services talk to each other by name (`postgres`, `fake-server`) via Docker Compose's internal DNS, never by hardcoded IP.

## Architecture: CI/CD (GitHub Actions)

```
.github/workflows/ci.yml

  on: push (any branch), pull_request (main), tags matching v*.*.*

  job "test"            — always runs: installs dependencies, runs pytest
                           (including tests that spin up their own ephemeral
                           PostgreSQL container via testcontainers)

  job "build-and-push"  — needs: test (only runs if tests pass)
                           if: only on a pushed tag (refs/tags/v*)
                           builds the image for linux/amd64 AND linux/arm64
                           (via QEMU + Buildx), pushes to
                           ghcr.io/tyra2291/ccsds-tm-decom, tagged with
                           the version and "latest"
```

A normal `git push` only ever runs the tests. Publishing a new image is a deliberate, separate action:
```bash
git tag v0.3.0
git push origin v0.3.0
```

## Architecture: Kubernetes (local, via Minikube)

```
k8s/
├── postgres-pvc.yaml               # PersistentVolumeClaim: 1Gi, survives Pod restarts
├── postgres-schema-configmap.yaml  # ConfigMap generated from db/schema.sql
├── postgres-deployment.yaml        # Deployment (1 replica): postgres:16, mounts the Secret
│                                    #   (env vars, generated at deploy time — see below), the
│                                    #   PVC (data dir), and the ConfigMap at
│                                    #   /docker-entrypoint-initdb.d/ (auto-runs schema.sql on
│                                    #   first boot only, when the data volume is empty)
├── postgres-service.yaml           # Service (ClusterIP): "postgres", reachable only inside
│                                    #   the cluster — same as Compose's service-name DNS
├── api-deployment.yaml             # Deployment (1 replica): pulls the image built by CI
│                                    #   from GHCR, HTTP readiness probe on /api/sessions
├── api-service.yaml                # Service (NodePort): exposes the API outside the cluster
└── deploy.sh                       # reads .env, generates the postgres-secret Secret and the
                                       api-config ConfigMap directly in the cluster (never
                                       written as committed YAML), applies every manifest above
                                       in order, waits for both Deployments to be ready, and
                                       finishes by running kubectl port-forward in the foreground
```

```
┌─────────────────────────────┐
│ Deployment "postgres"         │
│   Pod (postgres:16)           │
│    ├── Secret (env vars,      │
│    │   generated by deploy.sh │
│    │   from .env)             │
│    ├── PVC (data persistence) │
│    └── ConfigMap (schema.sql, │
│        auto-applied on first  │
│        boot)                  │
└─────────────────────────────┘
              ▲
              │ Service "postgres" (ClusterIP — internal only)
              │
┌─────────────────────────────┐
│ Deployment "api"               │
│   Pod (image from GHCR)       │
│    └── ConfigMap (DATABASE_URL,│
│        generated by deploy.sh)│
└─────────────────────────────┘
              ▲
              │ Service "api" (NodePort)
              │
     kubectl port-forward
       (run automatically
        by deploy.sh)
              │
        localhost:8000
```

Access is via `kubectl port-forward` rather than the NodePort directly: Minikube's Docker driver on macOS doesn't expose node IPs directly to the host, so port-forwarding is the practical way to reach the API locally. On a real multi-node cluster, the NodePort (or, more commonly, a LoadBalancer/Ingress) would be reachable directly.

## Tests

```bash
poetry run pytest -v
```

- Unit tests for each decoding module (`ccsds/`, `ground_segment/`) using hand-crafted byte sequences.
- Integration tests using captured telemetry frames, including a test that validates genuine Space Packet spillover across two consecutive frames.
- Database tests (`test_storage.py`, `test_integration_tcp_storage.py`) use `testcontainers` to spin up an ephemeral PostgreSQL container automatically — no pre-existing database instance is required to run the full suite, which also means these tests work unmodified in CI.

## Tech stack

Python 3.14, Poetry, pytest, testcontainers, asyncpg, FastAPI, Docker/docker-compose, PostgreSQL, GitHub Actions, Kubernetes (Minikube).

## Roadmap / not yet implemented

- **Grafana/Prometheus**: metrics export and dashboards for monitoring decode throughput and error rates.
- **Ingress**: a real HTTP routing layer instead of `kubectl port-forward`, for a more production-like local setup.