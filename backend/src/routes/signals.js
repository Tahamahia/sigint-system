/**
 * Signals API — Signal log CRUD and metadata ingestion.
 */
const express = require('express');
const router = express.Router();
const { getPool } = require('../config/db');
const { processMetadata } = require('../services/metadataParser');
const { broadcast } = require('../websocket/liveStream');

// GET /api/signals — Paginated signal logs
router.get('/', async (req, res) => {
  try {
    const pool = getPool();
    const page = parseInt(req.query.page) || 1;
    const limit = Math.min(parseInt(req.query.limit) || 50, 200);
    const offset = (page - 1) * limit;
    const protocol = req.query.protocol;

    let query = 'SELECT * FROM signal_logs';
    const params = [];
    if (protocol) {
      query += ' WHERE protocol_guess = $1';
      params.push(protocol);
    }
    query += ' ORDER BY timestamp DESC LIMIT $' + (params.length + 1) + ' OFFSET $' + (params.length + 2);
    params.push(limit, offset);

    const result = await pool.query(query, params);
    const countResult = await pool.query('SELECT COUNT(*) FROM signal_logs');

    res.json({
      data: result.rows,
      pagination: { page, limit, total: parseInt(countResult.rows[0].count) }
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/signals — Log a new signal detection
router.post('/', async (req, res) => {
  try {
    const pool = getPool();
    const { frequency, bandwidth_khz, snr_db, power_dbm, protocol_guess,
            protocol_confidence, decoder_used, decode_success, raw_metadata,
            sdr_device_serial } = req.body;

    // Look up SDR device UUID if serial provided
    let sdrDeviceId = null;
    if (sdr_device_serial) {
      const devResult = await pool.query('SELECT id FROM sdr_devices WHERE serial = $1', [sdr_device_serial]);
      if (devResult.rows.length > 0) sdrDeviceId = devResult.rows[0].id;
    }

    const result = await pool.query(
      `INSERT INTO signal_logs (frequency, bandwidth_khz, snr_db, power_dbm, protocol_guess,
        protocol_confidence, decoder_used, decode_success, raw_metadata, sdr_device_id)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *`,
      [frequency, bandwidth_khz, snr_db, power_dbm, protocol_guess,
       protocol_confidence, decoder_used, decode_success || false,
       raw_metadata ? JSON.stringify(raw_metadata) : null, sdrDeviceId]
    );

    broadcast('signal_log', result.rows[0]);
    res.status(201).json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/signals/metadata — Process decoded metadata
router.post('/metadata', async (req, res) => {
  try {
    const result = await processMetadata(req.body);
    broadcast('metadata', { ...req.body, ...result });
    res.status(201).json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
