CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    source TEXT NOT NULL  -- e.g. "tcp:host:port" or "file:path"
);

CREATE INDEX IF NOT EXISTS idx_sessions_name ON sessions (name);

CREATE TABLE IF NOT EXISTS frames (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES sessions (id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    spacecraft_id INTEGER NOT NULL,
    virtual_channel_id INTEGER NOT NULL,
    virtual_channel_frame_count INTEGER NOT NULL,
    fecf_valid BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_frames_session_id ON frames (session_id);
CREATE INDEX IF NOT EXISTS idx_frames_spacecraft_id ON frames (spacecraft_id);
CREATE INDEX IF NOT EXISTS idx_frames_received_at ON frames (received_at);

CREATE TABLE IF NOT EXISTS packets (
    id BIGSERIAL PRIMARY KEY,
    frame_id BIGINT REFERENCES frames (id) ON DELETE CASCADE,
    apid INTEGER NOT NULL,
    sequence_count INTEGER NOT NULL,
    packet_length INTEGER NOT NULL,
    pus_type INTEGER,
    pus_subtype INTEGER,
    raw_bytes BYTEA NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_packets_frame_id ON packets (frame_id);
CREATE INDEX IF NOT EXISTS idx_packets_apid ON packets (apid);
CREATE INDEX IF NOT EXISTS idx_packets_pus_type_subtype ON packets (pus_type, pus_subtype);