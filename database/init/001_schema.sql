-- SIGINT System Schema (Fixed ordering for FK deps)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE networks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    protocol VARCHAR(50) NOT NULL CHECK (protocol IN ('DMR','TETRA','P25','NXDN','UNKNOWN')),
    frequency_range_low DOUBLE PRECISION,
    frequency_range_high DOUBLE PRECISION,
    color_code INTEGER,
    encryption_type VARCHAR(50) DEFAULT 'NONE' CHECK (encryption_type IN ('NONE','AES-256','DES','RC4','ARC4','HYTERA_BP','UNKNOWN')),
    encryption_key VARCHAR(512),
    description TEXT,
    logo_url VARCHAR(512),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);
CREATE INDEX idx_networks_protocol ON networks(protocol);

CREATE TABLE base_stations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    network_id UUID NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
    site_id INTEGER,
    site_name VARCHAR(255),
    color_code INTEGER,
    frequencies DOUBLE PRECISION[] NOT NULL DEFAULT '{}',
    control_channel DOUBLE PRECISION,
    location_lat DOUBLE PRECISION,
    location_lon DOUBLE PRECISION,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);
CREATE INDEX idx_bs_network ON base_stations(network_id);

CREATE TABLE talkgroups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    base_station_id UUID NOT NULL REFERENCES base_stations(id) ON DELETE CASCADE,
    tg_number INTEGER NOT NULL,
    label VARCHAR(255),
    encryption_status VARCHAR(50) DEFAULT 'CLEAR' CHECK (encryption_status IN ('CLEAR','ENCRYPTED','MIXED','UNKNOWN')),
    priority INTEGER DEFAULT 0,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);
CREATE INDEX idx_tg_bs ON talkgroups(base_station_id);
CREATE UNIQUE INDEX idx_tg_unique ON talkgroups(base_station_id, tg_number);

CREATE TABLE radios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    radio_id_dec INTEGER NOT NULL,
    radio_id_hex VARCHAR(20),
    alias VARCHAR(255),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_lat DOUBLE PRECISION,
    last_lon DOUBLE PRECISION,
    gps_capable BOOLEAN DEFAULT FALSE,
    notes TEXT
);
CREATE UNIQUE INDEX idx_radios_rid ON radios(radio_id_dec);

CREATE TABLE radio_talkgroup_assoc (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    radio_id UUID NOT NULL REFERENCES radios(id) ON DELETE CASCADE,
    talkgroup_id UUID NOT NULL REFERENCES talkgroups(id) ON DELETE CASCADE,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_count INTEGER DEFAULT 1
);
CREATE UNIQUE INDEX idx_rta_unique ON radio_talkgroup_assoc(radio_id, talkgroup_id);

CREATE TABLE sdr_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    serial VARCHAR(100) UNIQUE,
    device_type VARCHAR(50) NOT NULL CHECK (device_type IN ('RTL-SDR','HackRF','USRP','UNKNOWN')),
    label VARCHAR(255),
    mode VARCHAR(50) DEFAULT 'IDLE' CHECK (mode IN ('IDLE','SWEEP','PINNED','DISCOVERY','ERROR')),
    assigned_freq DOUBLE PRECISION,
    sample_rate INTEGER DEFAULT 2400000,
    gain_db DOUBLE PRECISION DEFAULT 40.0,
    status VARCHAR(50) DEFAULT 'DISCONNECTED' CHECK (status IN ('ACTIVE','DISCONNECTED','ERROR','INITIALIZING')),
    last_heartbeat TIMESTAMPTZ,
    connected_at TIMESTAMPTZ,
    notes TEXT
);

CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_radio_id UUID REFERENCES radios(id) ON DELETE SET NULL,
    target_radio_id UUID REFERENCES radios(id) ON DELETE SET NULL,
    talkgroup_id UUID REFERENCES talkgroups(id) ON DELETE SET NULL,
    base_station_id UUID REFERENCES base_stations(id) ON DELETE SET NULL,
    call_type VARCHAR(50) NOT NULL CHECK (call_type IN ('GROUP','PRIVATE','EMERGENCY','DATA','UNKNOWN')),
    time_slot INTEGER CHECK (time_slot IN (1, 2)),
    protocol VARCHAR(50),
    frequency DOUBLE PRECISION,
    duration_ms INTEGER,
    encryption BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_interactions_ts ON interactions(timestamp);

CREATE TABLE gps_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    radio_id UUID NOT NULL REFERENCES radios(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    speed_kmh DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    accuracy_m DOUBLE PRECISION,
    source_protocol VARCHAR(20) CHECK (source_protocol IN ('LRRP','LIP','GPS_REVERT','UNKNOWN')),
    raw_packet BYTEA,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_gps_radio ON gps_events(radio_id);
CREATE INDEX idx_gps_ts ON gps_events(timestamp);

CREATE TABLE signal_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    frequency DOUBLE PRECISION NOT NULL,
    bandwidth_khz DOUBLE PRECISION,
    snr_db DOUBLE PRECISION,
    power_dbm DOUBLE PRECISION,
    protocol_guess VARCHAR(50),
    protocol_confidence DOUBLE PRECISION,
    decoder_used VARCHAR(100),
    decode_success BOOLEAN DEFAULT FALSE,
    raw_metadata JSONB,
    sdr_device_id UUID REFERENCES sdr_devices(id) ON DELETE SET NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_siglogs_freq ON signal_logs(frequency);
CREATE INDEX idx_siglogs_ts ON signal_logs(timestamp);
CREATE INDEX idx_siglogs_metadata ON signal_logs USING GIN (raw_metadata);

CREATE TABLE system_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'INFO',
    title VARCHAR(255) NOT NULL,
    description TEXT,
    related_entity UUID,
    acknowledged BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_alerts_ts ON system_alerts(timestamp);

CREATE TABLE frequency_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    frequency DOUBLE PRECISION NOT NULL,
    bandwidth_khz DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT FALSE,
    last_active TIMESTAMPTZ,
    hit_count INTEGER DEFAULT 0,
    avg_snr_db DOUBLE PRECISION,
    protocol_guess VARCHAR(50),
    priority_score DOUBLE PRECISION DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_freqact_freq ON frequency_activity(frequency);

-- Views
CREATE VIEW v_topology AS
SELECT n.id AS network_id, n.name AS network_name, n.protocol,
    bs.id AS base_station_id, bs.site_name,
    tg.id AS talkgroup_id, tg.tg_number, tg.label AS tg_label, tg.encryption_status,
    r.id AS radio_uuid, r.radio_id_dec, r.radio_id_hex, r.alias AS radio_alias,
    r.last_lat, r.last_lon, rta.interaction_count
FROM networks n
LEFT JOIN base_stations bs ON bs.network_id = n.id
LEFT JOIN talkgroups tg ON tg.base_station_id = bs.id
LEFT JOIN radio_talkgroup_assoc rta ON rta.talkgroup_id = tg.id
LEFT JOIN radios r ON r.id = rta.radio_id;

CREATE VIEW v_latest_gps AS
SELECT DISTINCT ON (g.radio_id)
    g.radio_id, r.radio_id_dec, r.radio_id_hex, r.alias,
    g.latitude, g.longitude, g.altitude, g.speed_kmh, g.heading, g.timestamp
FROM gps_events g JOIN radios r ON r.id = g.radio_id
ORDER BY g.radio_id, g.timestamp DESC;
