/**
 * Topology Builder — Construct network graph from DB hierarchy.
 */
const { getPool } = require('../config/db');

async function buildTopology() {
  const pool = getPool();
  if (!pool) throw new Error('Database not initialized');

  const result = await pool.query(`SELECT * FROM v_topology`);
  const rows = result.rows;

  const nodes = [];
  const edges = [];
  const seen = new Set();

  for (const row of rows) {
    // Network node
    if (row.network_id && !seen.has(row.network_id)) {
      seen.add(row.network_id);
      nodes.push({
        id: row.network_id, type: 'network',
        label: row.network_name, protocol: row.protocol,
        level: 0
      });
    }

    // Base station node
    if (row.base_station_id && !seen.has(row.base_station_id)) {
      seen.add(row.base_station_id);
      nodes.push({
        id: row.base_station_id, type: 'base_station',
        label: row.site_name || `Site ${row.bs_site_id}`,
        level: 1
      });
      if (row.network_id) {
        edges.push({
          source: row.network_id, target: row.base_station_id,
          type: 'network_to_bs', weight: 1
        });
      }
    }

    // Talkgroup node
    if (row.talkgroup_id && !seen.has(row.talkgroup_id)) {
      seen.add(row.talkgroup_id);
      nodes.push({
        id: row.talkgroup_id, type: 'talkgroup',
        label: row.tg_label || `TG ${row.tg_number}`,
        tg_number: row.tg_number, encryption: row.encryption_status,
        level: 2
      });
      if (row.base_station_id) {
        edges.push({
          source: row.base_station_id, target: row.talkgroup_id,
          type: 'bs_to_tg', weight: 1
        });
      }
    }

    // Radio node
    if (row.radio_uuid && !seen.has(row.radio_uuid)) {
      seen.add(row.radio_uuid);
      nodes.push({
        id: row.radio_uuid, type: 'radio',
        label: row.radio_alias || `RID ${row.radio_id_dec}`,
        radio_id: row.radio_id_dec, hex: row.radio_id_hex,
        lat: row.last_lat, lon: row.last_lon,
        level: 3
      });
    }

    // Radio-to-talkgroup edge
    if (row.radio_uuid && row.talkgroup_id) {
      const edgeKey = `${row.radio_uuid}-${row.talkgroup_id}`;
      if (!seen.has(edgeKey)) {
        seen.add(edgeKey);
        edges.push({
          source: row.talkgroup_id, target: row.radio_uuid,
          type: 'tg_to_radio', weight: row.interaction_count || 1
        });
      }
    }
  }

  return { nodes, edges };
}

module.exports = { buildTopology };
