/**
 * SDR API — Device registration and control.
 */
const express = require('express');
const router = express.Router();
const { getPool } = require('../config/db');
const { broadcast } = require('../websocket/liveStream');

// GET /api/sdr — All SDR devices
router.get('/', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query('SELECT * FROM sdr_devices ORDER BY connected_at DESC');
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/sdr/register — Register/update an SDR device
router.post('/register', async (req, res) => {
  try {
    const pool = getPool();
    const { serial, device_type, sample_rate, gain_db } = req.body;

    const result = await pool.query(
      `INSERT INTO sdr_devices (serial, device_type, sample_rate, gain_db, status, connected_at, last_heartbeat)
       VALUES ($1, $2, $3, $4, 'ACTIVE', NOW(), NOW())
       ON CONFLICT (serial) DO UPDATE SET
         status = 'ACTIVE', last_heartbeat = NOW(), connected_at = NOW(),
         sample_rate = $3, gain_db = $4
       RETURNING *`,
      [serial, device_type || 'UNKNOWN', sample_rate || 2400000, gain_db || 40.0]
    );

    broadcast('sdr_status', result.rows[0]);
    res.status(201).json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/sdr/:serial/status — Update SDR status
router.post('/:serial/status', async (req, res) => {
  try {
    const pool = getPool();
    const { serial } = req.params;
    const { mode, assigned_freq, status } = req.body;

    const result = await pool.query(
      `UPDATE sdr_devices SET
        mode = COALESCE($2, mode),
        assigned_freq = COALESCE($3, assigned_freq),
        status = COALESCE($4, status),
        last_heartbeat = NOW()
       WHERE serial = $1 RETURNING *`,
      [serial, mode, assigned_freq, status]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Device not found' });
    }

    broadcast('sdr_status', result.rows[0]);
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
