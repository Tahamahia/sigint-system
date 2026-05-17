/**
 * Networks API — CRUD, encryption keys, logo upload.
 */
const express = require('express');
const router = express.Router();
const path = require('path');
const fs = require('fs');
const { getPool } = require('../config/db');
const { broadcast } = require('../websocket/liveStream');

// Multer setup for logo uploads
const multer = require('multer');
const UPLOAD_DIR = path.join(__dirname, '..', '..', 'uploads', 'logos');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname) || '.png';
    cb(null, `network-${req.params.id}${ext}`);
  }
});
const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = /\.(jpg|jpeg|png|gif|svg|webp)$/i;
    cb(null, allowed.test(path.extname(file.originalname)));
  }
});

// GET /api/networks — List all networks
router.get('/', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query(
      'SELECT * FROM networks ORDER BY discovered_at DESC'
    );
    res.json({ data: result.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/networks/:id — Single network with details
router.get('/:id', async (req, res) => {
  try {
    const pool = getPool();
    const net = await pool.query('SELECT * FROM networks WHERE id = $1', [req.params.id]);
    if (net.rows.length === 0) return res.status(404).json({ error: 'Not found' });

    const bs = await pool.query(
      'SELECT * FROM base_stations WHERE network_id = $1', [req.params.id]
    );
    res.json({ network: net.rows[0], base_stations: bs.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PUT /api/networks/:id — Update network (name, description, encryption)
router.put('/:id', async (req, res) => {
  try {
    const pool = getPool();
    const { name, description, encryption_type, encryption_key } = req.body;

    const result = await pool.query(
      `UPDATE networks SET
        name = COALESCE($2, name),
        description = COALESCE($3, description),
        encryption_type = COALESCE($4, encryption_type),
        encryption_key = COALESCE($5, encryption_key),
        updated_at = NOW()
       WHERE id = $1 RETURNING *`,
      [req.params.id, name, description, encryption_type, encryption_key]
    );

    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });

    broadcast('network_updated', result.rows[0]);
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/networks/:id/logo — Upload logo image
router.post('/:id/logo', upload.single('logo'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' });

    const pool = getPool();
    const logoUrl = `/uploads/logos/${req.file.filename}`;

    const result = await pool.query(
      'UPDATE networks SET logo_url = $2, updated_at = NOW() WHERE id = $1 RETURNING *',
      [req.params.id, logoUrl]
    );

    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });

    broadcast('network_updated', result.rows[0]);
    res.json({ logo_url: logoUrl, network: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/networks/:id/key — Get decryption key (for middleware)
router.get('/:id/key', async (req, res) => {
  try {
    const pool = getPool();
    const result = await pool.query(
      'SELECT encryption_type, encryption_key FROM networks WHERE id = $1',
      [req.params.id]
    );
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
