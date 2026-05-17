/**
 * Radios API — Radio and talkgroup queries.
 */
const express = require('express');
const router = express.Router();
const { getPool } = require('../config/db');

// GET /api/radios — All radios with last activity
router.get('/', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query(
      `SELECT r.*, 
        (SELECT COUNT(*) FROM radio_talkgroup_assoc rta WHERE rta.radio_id = r.id) AS talkgroup_count,
        (SELECT COUNT(*) FROM interactions i WHERE i.source_radio_id = r.id) AS interaction_count
       FROM radios r ORDER BY r.last_seen DESC LIMIT 500`
    );
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radios/:id — Single radio with full history
router.get('/:id', async (req, res) => {
  try {
    const pool = getPool();
    const { id } = req.params;

    // Try UUID first, then radio_id_dec
    let radioQuery;
    if (id.includes('-')) {
      radioQuery = await pool.query('SELECT * FROM radios WHERE id = $1', [id]);
    } else {
      radioQuery = await pool.query('SELECT * FROM radios WHERE radio_id_dec = $1', [parseInt(id)]);
    }

    if (radioQuery.rows.length === 0) {
      return res.status(404).json({ error: 'Radio not found' });
    }
    const radio = radioQuery.rows[0];

    // Get talkgroup associations
    const tgQuery = await pool.query(
      `SELECT tg.tg_number, tg.label, tg.encryption_status, rta.interaction_count, rta.last_seen
       FROM radio_talkgroup_assoc rta
       JOIN talkgroups tg ON tg.id = rta.talkgroup_id
       WHERE rta.radio_id = $1
       ORDER BY rta.interaction_count DESC`, [radio.id]
    );

    // Get recent interactions
    const interQuery = await pool.query(
      `SELECT i.*, tg.tg_number, tg.label AS tg_label
       FROM interactions i
       LEFT JOIN talkgroups tg ON tg.id = i.talkgroup_id
       WHERE i.source_radio_id = $1
       ORDER BY i.timestamp DESC LIMIT 50`, [radio.id]
    );

    // Get GPS history
    const gpsQuery = await pool.query(
      `SELECT * FROM gps_events WHERE radio_id = $1 ORDER BY timestamp DESC LIMIT 100`,
      [radio.id]
    );

    res.json({
      radio,
      talkgroups: tgQuery.rows,
      interactions: interQuery.rows,
      gps_history: gpsQuery.rows,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/radios/talkgroups — All talkgroups
router.get('/talkgroups/all', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query(
      `SELECT tg.*, bs.site_name, n.name AS network_name, n.protocol,
        (SELECT COUNT(*) FROM radio_talkgroup_assoc rta WHERE rta.talkgroup_id = tg.id) AS radio_count
       FROM talkgroups tg
       JOIN base_stations bs ON bs.id = tg.base_station_id
       JOIN networks n ON n.id = bs.network_id
       ORDER BY tg.tg_number`
    );
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
