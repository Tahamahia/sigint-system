/**
 * WebSocket Live Stream — Broadcasts events to connected frontend clients.
 */
const WebSocket = require('ws');

let wss = null;

function initWebSocket(server) {
  wss = new WebSocket.Server({ server });

  wss.on('connection', (ws, req) => {
    console.log(`[WS] Client connected (${wss.clients.size} total)`);
    ws.isAlive = true;

    ws.on('pong', () => { ws.isAlive = true; });
    ws.on('close', () => {
      console.log(`[WS] Client disconnected (${wss.clients.size} total)`);
    });
    ws.on('error', (err) => {
      console.error('[WS] Client error:', err.message);
    });

    // Send welcome
    ws.send(JSON.stringify({ type: 'connected', timestamp: new Date().toISOString() }));
  });

  // Heartbeat
  const interval = setInterval(() => {
    wss.clients.forEach(ws => {
      if (!ws.isAlive) return ws.terminate();
      ws.isAlive = false;
      ws.ping();
    });
  }, 30000);

  wss.on('close', () => clearInterval(interval));
  return wss;
}

function broadcast(type, data) {
  if (!wss) return;
  const message = JSON.stringify({ type, data, timestamp: new Date().toISOString() });
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

function getWSS() { return wss; }

module.exports = { initWebSocket, broadcast, getWSS };
