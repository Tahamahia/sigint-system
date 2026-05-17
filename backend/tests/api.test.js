/**
 * Backend Tests — API endpoints and metadata parser.
 */
const { processMetadata, processGPS } = require('../src/services/metadataParser');
const { buildTopology } = require('../src/services/topologyBuilder');

// Mock the database pool
const mockPool = {
  query: jest.fn(),
};

jest.mock('../src/config/db', () => ({
  getPool: () => mockPool,
  initPool: jest.fn(),
  setPool: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();
});

describe('MetadataParser', () => {
  test('processMetadata creates radio and interaction', async () => {
    // Mock radio upsert
    mockPool.query
      .mockResolvedValueOnce({ rows: [{ id: 'radio-uuid-1' }] })  // radio upsert
      .mockResolvedValueOnce({ rows: [{ id: 'tg-uuid-1' }] })      // talkgroup lookup
      .mockResolvedValueOnce({ rows: [] })                          // radio-tg assoc
      .mockResolvedValueOnce({ rows: [{ id: 'inter-uuid-1' }] });  // interaction insert

    const result = await processMetadata({
      radio_id: 3000001,
      talkgroup: 100,
      call_type: 'GROUP',
      time_slot: 1,
      protocol: 'DMR',
      frequency: 460.1,
      encrypted: false,
    });

    expect(result.radio_uuid).toBe('radio-uuid-1');
    expect(result.interaction_id).toBe('inter-uuid-1');
    expect(mockPool.query).toHaveBeenCalledTimes(4);
  });

  test('processMetadata requires radio_id', async () => {
    await expect(processMetadata({ talkgroup: 100 })).rejects.toThrow('radio_id is required');
  });

  test('processMetadata handles missing talkgroup', async () => {
    mockPool.query
      .mockResolvedValueOnce({ rows: [{ id: 'radio-uuid-2' }] })
      .mockResolvedValueOnce({ rows: [{ id: 'inter-uuid-2' }] });

    const result = await processMetadata({
      radio_id: 3000002,
      call_type: 'PRIVATE',
      protocol: 'DMR',
    });

    expect(result.radio_uuid).toBe('radio-uuid-2');
    expect(result.talkgroup_uuid).toBeNull();
  });

  test('processGPS stores GPS event and updates radio', async () => {
    mockPool.query
      .mockResolvedValueOnce({ rows: [{ id: 'radio-uuid-3' }] })
      .mockResolvedValueOnce({ rows: [{ id: 'gps-uuid-1' }] });

    const result = await processGPS({
      radio_id: 3000003,
      latitude: 33.749,
      longitude: -84.388,
      altitude: 300,
      speed_kmh: 45,
      heading: 180,
      source_protocol: 'LRRP',
    });

    expect(result.gps_event_id).toBe('gps-uuid-1');
    expect(result.radio_uuid).toBe('radio-uuid-3');
  });

  test('processGPS requires coordinates', async () => {
    await expect(processGPS({ radio_id: 1 })).rejects.toThrow();
  });
});

describe('TopologyBuilder', () => {
  test('buildTopology returns nodes and edges', async () => {
    mockPool.query.mockResolvedValueOnce({
      rows: [
        {
          network_id: 'net-1', network_name: 'Test Net', protocol: 'DMR',
          base_station_id: 'bs-1', site_name: 'Tower 1', bs_site_id: 1,
          talkgroup_id: 'tg-1', tg_number: 100, tg_label: 'Dispatch', encryption_status: 'CLEAR',
          radio_uuid: 'radio-1', radio_id_dec: 3000001, radio_id_hex: '2dc6c1',
          radio_alias: 'Unit-1', last_lat: 33.749, last_lon: -84.388, interaction_count: 5,
        }
      ]
    });

    const result = await buildTopology();
    expect(result.nodes).toBeDefined();
    expect(result.edges).toBeDefined();
    expect(result.nodes.length).toBe(4); // network, bs, tg, radio
    expect(result.edges.length).toBe(3); // net->bs, bs->tg, tg->radio
  });

  test('buildTopology handles empty database', async () => {
    mockPool.query.mockResolvedValueOnce({ rows: [] });
    const result = await buildTopology();
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
  });
});

describe('Validators', () => {
  const { signalSchema, metadataSchema, gpsSchema } = require('../src/utils/validators');

  test('signalSchema validates correct data', () => {
    const { error } = signalSchema.validate({ frequency: 460.1 });
    expect(error).toBeUndefined();
  });

  test('signalSchema rejects missing frequency', () => {
    const { error } = signalSchema.validate({});
    expect(error).toBeDefined();
  });

  test('metadataSchema validates correct data', () => {
    const { error } = metadataSchema.validate({ radio_id: 3000001, call_type: 'GROUP' });
    expect(error).toBeUndefined();
  });

  test('gpsSchema validates correct data', () => {
    const { error } = gpsSchema.validate({
      radio_id: 1, latitude: 33.749, longitude: -84.388
    });
    expect(error).toBeUndefined();
  });

  test('gpsSchema rejects out-of-range coords', () => {
    const { error } = gpsSchema.validate({
      radio_id: 1, latitude: 999, longitude: -84.388
    });
    expect(error).toBeDefined();
  });
});
