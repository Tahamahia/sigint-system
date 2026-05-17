/**
 * GPS API — GPS event queries and ingestion.
 */
const express = require('express');
const router = express.Router();
const { getPool } = require('../config/db');
const { processGPS } = require('../services/metadataParser');
const { broadcast } = require('../websocket/liveStream');

// GET /api/gps — All GPS events (paginated)
router.get('/', async (req, res) => {
  try {
    const pool = getPool();
    const limit = Math.min(parseInt(req.query.limit) || 100, 500);
    const result = await pool.query(
      `SELECT g.*, r.radio_id_dec, r.radio_id_hex, r.alias
       FROM gps_events g
       JOIN radios r ON r.id = g.radio_id
       ORDER BY g.timestamp DESC LIMIT $1`, [limit]
    );
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/gps/latest — Latest position per radio
router.get('/latest', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query('SELECT * FROM v_latest_gps');
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/gps/radio/:radioId — GPS history for a specific radio
router.get('/radio/:radioId', async (req, res) => {
  try {
    const pool = getPool();
    const radioId = parseInt(req.params.radioId);
    const result = await pool.query(
      `SELECT g.* FROM gps_events g
       JOIN radios r ON r.id = g.radio_id
       WHERE r.radio_id_dec = $1
       ORDER BY g.timestamp DESC LIMIT 200`, [radioId]
    );
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/gps — Ingest GPS fix from middleware
router.post('/', async (req, res) => {
  try {
    const result = await processGPS(req.body);
    broadcast('gps_event', { ...req.body, ...result });
    res.status(201).json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
