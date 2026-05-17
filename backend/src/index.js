/**
 * SIGINT Backend — Express API Server + WebSocket
 */
const express = require('express');
const cors = require('cors');
const http = require('http');
const path = require('path');
const { initPool, getPool } = require('./config/db');
const { initWebSocket } = require('./websocket/liveStream');

const signalsRouter = require('./routes/signals');
const radiosRouter = require('./routes/radios');
const gpsRouter = require('./routes/gps');
const topologyRouter = require('./routes/topology');
const sdrRouter = require('./routes/sdr');
const networksRouter = require('./routes/networks');

const PORT = process.env.PORT || 4000;
const WS_PORT = process.env.WS_PORT || 4001;

const app = express();

// Middleware
app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '10mb' }));

// Static file serving for offline map tiles and uploaded logos
app.use('/tiles', express.static(path.join(__dirname, '..', '..', 'map_tiles')));
app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));

// Health check
app.get('/health', async (req, res) => {
  try {
    const pool = getPool();
    if (pool) {
      await pool.query('SELECT 1');
    }
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
  } catch (err) {
    res.status(503).json({ status: 'unhealthy', error: err.message });
  }
});

// API Routes
app.use('/api/signals', signalsRouter);
app.use('/api/radios', radiosRouter);
app.use('/api/gps', gpsRouter);
app.use('/api/topology', topologyRouter);
app.use('/api/sdr', sdrRouter);
app.use('/api/networks', networksRouter);

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.message);
  res.status(500).json({ error: 'Internal server error', message: err.message });
});

async function start() {
  // Initialize database
  await initPool();
  console.log('[DB] Connected to PostgreSQL');

  // Start HTTP server
  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`[API] Server running on port ${PORT}`);
  });

  // Start WebSocket server on separate port
  const wsServer = http.createServer();
  initWebSocket(wsServer);
  wsServer.listen(WS_PORT, '0.0.0.0', () => {
    console.log(`[WS] WebSocket server running on port ${WS_PORT}`);
  });

  return { server, wsServer };
}

// Only start if run directly (not during testing)
if (require.main === module) {
  start().catch(err => {
    console.error('[FATAL] Failed to start:', err);
    process.exit(1);
  });
}

module.exports = { app, start };
