/**
 * Metadata Parser — Normalize incoming metadata and upsert entities.
 */
const { getPool } = require('../config/db');

/**
 * Parse and store a metadata event from the middleware.
 * Creates new radios/talkgroups on first sight, updates last_seen.
 */
async function processMetadata(meta) {
  const pool = getPool();
  if (!pool) throw new Error('Database not initialized');

  const {
    radio_id, talkgroup, time_slot, call_type,
    color_code, protocol, frequency, encrypted, source_decoder
  } = meta;

  if (!radio_id) throw new Error('radio_id is required');

  // Upsert radio
  const radioResult = await pool.query(
    `INSERT INTO radios (radio_id_dec, radio_id_hex, last_seen)
     VALUES ($1, $2, NOW())
     ON CONFLICT (radio_id_dec) DO UPDATE SET last_seen = NOW()
     RETURNING id`,
    [radio_id, radio_id.toString(16).padStart(6, '0')]
  );
  const radioUuid = radioResult.rows[0].id;

  // Find or create association with talkgroup if provided
  let tgUuid = null;
  if (talkgroup) {
    // Find matching talkgroup (by tg_number, any base station)
    const tgResult = await pool.query(
      `SELECT id FROM talkgroups WHERE tg_number = $1 LIMIT 1`,
      [talkgroup]
    );
    if (tgResult.rows.length > 0) {
      tgUuid = tgResult.rows[0].id;

      // Upsert radio-talkgroup association
      await pool.query(
        `INSERT INTO radio_talkgroup_assoc (radio_id, talkgroup_id, last_seen, interaction_count)
         VALUES ($1, $2, NOW(), 1)
         ON CONFLICT (radio_id, talkgroup_id)
         DO UPDATE SET last_seen = NOW(), interaction_count = radio_talkgroup_assoc.interaction_count + 1`,
        [radioUuid, tgUuid]
      );
    }
  }

  // Log interaction
  const interResult = await pool.query(
    `INSERT INTO interactions (source_radio_id, talkgroup_id, call_type, time_slot, protocol, frequency, encryption, timestamp)
     VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
     RETURNING id`,
    [radioUuid, tgUuid, call_type || 'UNKNOWN', time_slot, protocol, frequency, encrypted || false]
  );

  return {
    radio_uuid: radioUuid,
    talkgroup_uuid: tgUuid,
    interaction_id: interResult.rows[0].id,
  };
}

/**
 * Store a GPS fix and update radio location.
 */
async function processGPS(gpsData) {
  const pool = getPool();
  if (!pool) throw new Error('Database not initialized');

  const { radio_id, latitude, longitude, altitude, speed_kmh, heading, accuracy_m, source_protocol } = gpsData;

  if (!radio_id || latitude == null || longitude == null) {
    throw new Error('radio_id, latitude, longitude are required');
  }

  // Upsert radio with GPS capability
  const radioResult = await pool.query(
    `INSERT INTO radios (radio_id_dec, radio_id_hex, last_seen, last_lat, last_lon, gps_capable)
     VALUES ($1, $2, NOW(), $3, $4, TRUE)
     ON CONFLICT (radio_id_dec) DO UPDATE SET
       last_seen = NOW(), last_lat = $3, last_lon = $4, gps_capable = TRUE
     RETURNING id`,
    [radio_id, radio_id.toString(16).padStart(6, '0'), latitude, longitude]
  );
  const radioUuid = radioResult.rows[0].id;

  // Insert GPS event
  const gpsResult = await pool.query(
    `INSERT INTO gps_events (radio_id, latitude, longitude, altitude, speed_kmh, heading, accuracy_m, source_protocol)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING id`,
    [radioUuid, latitude, longitude, altitude, speed_kmh, heading, accuracy_m, source_protocol || 'UNKNOWN']
  );

  return { gps_event_id: gpsResult.rows[0].id, radio_uuid: radioUuid };
}

module.exports = { processMetadata, processGPS };
