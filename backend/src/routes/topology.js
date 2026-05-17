/**
 * Topology API — Network graph construction.
 */
const express = require('express');
const router = express.Router();
const { buildTopology } = require('../services/topologyBuilder');

// GET /api/topology — Full network graph
router.get('/', async (req, res) => {
  try {
    const topology = await buildTopology();
    res.json(topology);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
