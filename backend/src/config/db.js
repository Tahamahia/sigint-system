/**
 * PostgreSQL Connection Pool with retry logic.
 */
const { Pool } = require('pg');

let pool = null;

const DB_CONFIG = {
  host: process.env.DB_HOST || 'db',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'sigint_db',
  user: process.env.DB_USER || 'sigint',
  password: process.env.DB_PASSWORD || 'sigint_secure_2024',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
};

async function initPool(retries = 10, delay = 2000) {
  for (let i = 0; i < retries; i++) {
    try {
      pool = new Pool(DB_CONFIG);
      await pool.query('SELECT 1');
      console.log('[DB] Pool initialized successfully');
      return pool;
    } catch (err) {
      console.log(`[DB] Connection attempt ${i + 1}/${retries} failed: ${err.message}`);
      if (i < retries - 1) {
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }
  throw new Error('Failed to connect to database after retries');
}

function getPool() {
  return pool;
}

function setPool(p) {
  pool = p;
}

module.exports = { initPool, getPool, setPool, DB_CONFIG };
