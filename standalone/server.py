"""
SIGINT Standalone Server — No external dependencies required.
Uses built-in Python: sqlite3, http.server, json, threading
"""
import sqlite3
import json
import os
import sys
import time
import random
import threading
import hashlib
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'sigint.db')
STATIC_DIR = os.path.dirname(__file__)
PORT = 3000
API_PREFIX = '/api'

# ============================================================
# DATABASE SETUP
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS networks (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, protocol TEXT NOT NULL,
            freq_low REAL, freq_high REAL, color_code INTEGER,
            discovered_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS base_stations (
            id TEXT PRIMARY KEY, network_id TEXT REFERENCES networks(id),
            site_id INTEGER, site_name TEXT, color_code INTEGER,
            control_channel REAL, location_lat REAL, location_lon REAL,
            discovered_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS talkgroups (
            id TEXT PRIMARY KEY, base_station_id TEXT REFERENCES base_stations(id),
            tg_number INTEGER NOT NULL, label TEXT,
            encryption_status TEXT DEFAULT 'CLEAR',
            discovered_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS radios (
            id TEXT PRIMARY KEY, radio_id_dec INTEGER UNIQUE NOT NULL,
            radio_id_hex TEXT, alias TEXT, gps_capable INTEGER DEFAULT 0,
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            last_lat REAL, last_lon REAL
        );
        CREATE TABLE IF NOT EXISTS radio_talkgroup_assoc (
            id TEXT PRIMARY KEY, radio_id TEXT REFERENCES radios(id),
            talkgroup_id TEXT REFERENCES talkgroups(id),
            interaction_count INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT (datetime('now')),
            UNIQUE(radio_id, talkgroup_id)
        );
        CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY, source_radio_id TEXT REFERENCES radios(id),
            talkgroup_id TEXT REFERENCES talkgroups(id),
            base_station_id TEXT REFERENCES base_stations(id),
            call_type TEXT NOT NULL, time_slot INTEGER,
            protocol TEXT, frequency REAL, duration_ms INTEGER,
            encryption INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS gps_events (
            id TEXT PRIMARY KEY, radio_id TEXT REFERENCES radios(id),
            latitude REAL NOT NULL, longitude REAL NOT NULL,
            altitude REAL, speed_kmh REAL, heading REAL,
            source_protocol TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS signal_logs (
            id TEXT PRIMARY KEY, frequency REAL NOT NULL,
            bandwidth_khz REAL, snr_db REAL, power_dbm REAL,
            protocol_guess TEXT, protocol_confidence REAL,
            decoder_used TEXT, decode_success INTEGER DEFAULT 0,
            raw_metadata TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sdr_devices (
            id TEXT PRIMARY KEY, serial TEXT UNIQUE,
            device_type TEXT NOT NULL, label TEXT,
            mode TEXT DEFAULT 'IDLE', assigned_freq REAL,
            sample_rate INTEGER DEFAULT 2400000,
            gain_db REAL DEFAULT 40.0,
            status TEXT DEFAULT 'ACTIVE',
            last_heartbeat TEXT DEFAULT (datetime('now'))
        );
    ''')
    conn.commit()
    return conn

def seed_db(conn):
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM networks").fetchone()[0] > 0:
        return

    nets = [
        ('net-001','Metro DMR Net','DMR',450,470,1),
        ('net-002','Regional TETRA','TETRA',380,400,None),
        ('net-003','County P25','P25',851,869,None),
    ]
    for n in nets:
        c.execute("INSERT INTO networks(id,name,protocol,freq_low,freq_high,color_code) VALUES(?,?,?,?,?,?)", n)

    bss = [
        ('bs-001','net-001',1,'Downtown Tower',1,460.1,33.8688,-84.388),
        ('bs-002','net-001',2,'Airport Site',1,460.4,33.6407,-84.4277),
        ('bs-003','net-002',1,'TETRA Central',None,390.1,33.749,-84.388),
        ('bs-004','net-002',2,'TETRA North',None,390.3,33.92,-84.35),
        ('bs-005','net-003',1,'P25 Main',None,855.1,33.78,-84.40),
    ]
    for b in bss:
        c.execute("INSERT INTO base_stations(id,network_id,site_id,site_name,color_code,control_channel,location_lat,location_lon) VALUES(?,?,?,?,?,?,?,?)", b)

    tgs = [
        ('tg-001','bs-001',100,'Dispatch','CLEAR'),('tg-002','bs-001',101,'Operations','CLEAR'),
        ('tg-003','bs-001',102,'Tactical-1','ENCRYPTED'),('tg-004','bs-002',100,'Airport Ops','CLEAR'),
        ('tg-005','bs-002',101,'Airport Sec','ENCRYPTED'),('tg-006','bs-003',1000,'TETRA Main','CLEAR'),
        ('tg-007','bs-003',1001,'TETRA Ops','CLEAR'),('tg-008','bs-003',1002,'TETRA Tac','MIXED'),
        ('tg-009','bs-004',2000,'North Patrol','CLEAR'),('tg-010','bs-004',2001,'North Fire','CLEAR'),
        ('tg-011','bs-005',500,'P25 Dispatch','CLEAR'),('tg-012','bs-005',501,'P25 Tac-1','ENCRYPTED'),
        ('tg-013','bs-005',502,'P25 Tac-2','CLEAR'),('tg-014','bs-005',503,'P25 Admin','CLEAR'),
    ]
    for t in tgs:
        c.execute("INSERT INTO talkgroups(id,base_station_id,tg_number,label,encryption_status) VALUES(?,?,?,?,?)", t)

    for i in range(1, 31):
        rid = 3000000 + i
        c.execute("INSERT INTO radios(id,radio_id_dec,radio_id_hex,alias,gps_capable) VALUES(?,?,?,?,?)",
                  (f'radio-{i:03d}', rid, hex(rid)[2:], f'Unit-{i}', 1 if i % 3 == 0 else 0))

    # SDR devices
    c.execute("INSERT INTO sdr_devices(id,serial,device_type,label,mode,status) VALUES(?,?,?,?,?,?)",
              ('sdr-001','MOCK-RTL-001','RTL-SDR','Primary Scanner','SWEEP','ACTIVE'))
    c.execute("INSERT INTO sdr_devices(id,serial,device_type,label,mode,status) VALUES(?,?,?,?,?,?)",
              ('sdr-002','MOCK-HRF-001','HackRF','Secondary Scanner','PINNED','ACTIVE'))

    conn.commit()
    print(f"[DB] Seeded: 3 networks, 5 base stations, 14 talkgroups, 30 radios")

# ============================================================
# MOCK DATA GENERATOR
# ============================================================
class MockGenerator:
    PROTOCOLS = ['DMR','TETRA','P25']
    CALL_TYPES = ['GROUP','GROUP','GROUP','PRIVATE','EMERGENCY']
    TG_IDS = ['tg-001','tg-002','tg-003','tg-004','tg-006','tg-007','tg-009','tg-011','tg-012','tg-013']
    BS_IDS = ['bs-001','bs-002','bs-003','bs-004','bs-005']
    GPS_CENTER = (33.749, -84.388)

    def __init__(self, conn):
        self.conn = conn
        self.running = True
        self.event_log = []

    def uid(self):
        return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]

    def generate_signal(self):
        proto = random.choice(self.PROTOCOLS)
        freq = round(random.choice([460.1,460.2,460.3,390.1,390.2,855.1,855.2]) + random.uniform(-0.01,0.01), 4)
        snr = round(random.uniform(6, 35), 1)
        power = round(random.uniform(-85, -35), 1)
        bw = 12.5 if proto != 'TETRA' else 25.0
        conf = round(random.uniform(0.55, 0.95), 3)

        c = self.conn.cursor()
        sid = self.uid()
        c.execute("INSERT INTO signal_logs(id,frequency,bandwidth_khz,snr_db,power_dbm,protocol_guess,protocol_confidence) VALUES(?,?,?,?,?,?,?)",
                  (sid, freq, bw, snr, power, proto, conf))

        event = {"type":"signal_log","id":sid,"frequency":freq,"bandwidth_khz":bw,"snr_db":snr,
                 "power_dbm":power,"protocol_guess":proto,"confidence":conf,
                 "timestamp":datetime.now().isoformat()}
        self.event_log.append(event)
        return event

    def generate_interaction(self):
        radio_idx = random.randint(1, 30)
        radio_id = f'radio-{radio_idx:03d}'
        rid_dec = 3000000 + radio_idx
        tg_id = random.choice(self.TG_IDS)
        bs_id = random.choice(self.BS_IDS)
        proto = random.choice(self.PROTOCOLS)
        call = random.choice(self.CALL_TYPES)
        ts = random.choice([1, 2])
        freq = round(random.uniform(390, 860), 4)
        enc = 1 if random.random() < 0.12 else 0

        c = self.conn.cursor()
        iid = self.uid()
        c.execute("""INSERT INTO interactions(id,source_radio_id,talkgroup_id,base_station_id,
                     call_type,time_slot,protocol,frequency,encryption) VALUES(?,?,?,?,?,?,?,?,?)""",
                  (iid, radio_id, tg_id, bs_id, call, ts, proto, freq, enc))

        c.execute("UPDATE radios SET last_seen=datetime('now') WHERE id=?", (radio_id,))

        try:
            c.execute("""INSERT INTO radio_talkgroup_assoc(id,radio_id,talkgroup_id,interaction_count)
                         VALUES(?,?,?,1) ON CONFLICT(radio_id,talkgroup_id)
                         DO UPDATE SET interaction_count=interaction_count+1, last_seen=datetime('now')""",
                      (self.uid(), radio_id, tg_id))
        except Exception:
            pass

        tg_info = c.execute("SELECT tg_number,label FROM talkgroups WHERE id=?", (tg_id,)).fetchone()
        tg_num = tg_info[0] if tg_info else 0
        tg_label = tg_info[1] if tg_info else ''

        event = {"type":"metadata","id":iid,"radio_id":rid_dec,"radio_alias":f"Unit-{radio_idx}",
                 "talkgroup":tg_num,"tg_label":tg_label,"call_type":call,"time_slot":ts,
                 "protocol":proto,"frequency":freq,"encrypted":bool(enc),
                 "timestamp":datetime.now().isoformat()}
        self.event_log.append(event)
        return event

    def generate_gps(self):
        # Only GPS-capable radios (every 3rd)
        radio_idx = random.choice([3,6,9,12,15,18,21,24,27,30])
        radio_id = f'radio-{radio_idx:03d}'
        rid_dec = 3000000 + radio_idx
        lat = round(self.GPS_CENTER[0] + random.uniform(-0.25, 0.25), 6)
        lon = round(self.GPS_CENTER[1] + random.uniform(-0.25, 0.25), 6)
        alt = round(random.uniform(200, 500), 1)
        speed = round(random.uniform(0, 100), 1)
        heading = round(random.uniform(0, 360), 1)
        src = random.choice(['LRRP', 'LIP'])

        c = self.conn.cursor()
        gid = self.uid()
        c.execute("INSERT INTO gps_events(id,radio_id,latitude,longitude,altitude,speed_kmh,heading,source_protocol) VALUES(?,?,?,?,?,?,?,?)",
                  (gid, radio_id, lat, lon, alt, speed, heading, src))
        c.execute("UPDATE radios SET last_lat=?, last_lon=?, last_seen=datetime('now') WHERE id=?",
                  (lat, lon, radio_id))

        event = {"type":"gps_event","id":gid,"radio_id":rid_dec,"radio_alias":f"Unit-{radio_idx}",
                 "latitude":lat,"longitude":lon,"altitude":alt,"speed_kmh":speed,
                 "heading":heading,"source_protocol":src,
                 "timestamp":datetime.now().isoformat()}
        self.event_log.append(event)
        return event

    def run_loop(self):
        print("[MOCK] Starting mock data generator...")
        while self.running:
            try:
                self.generate_signal()
                if random.random() < 0.7:
                    self.generate_interaction()
                if random.random() < 0.2:
                    self.generate_gps()
                self.conn.commit()
                # Keep only last 500 events
                if len(self.event_log) > 500:
                    self.event_log = self.event_log[-500:]
                time.sleep(random.uniform(0.5, 2.0))
            except Exception as e:
                print(f"[MOCK] Error: {e}")
                time.sleep(1)

# ============================================================
# HTTP API SERVER
# ============================================================
class SIGINTHandler(SimpleHTTPRequestHandler):
    db_conn = None
    mock_gen = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path.startswith(API_PREFIX):
            self.handle_api(path[len(API_PREFIX):], params)
        elif path == '/' or path == '/index.html':
            self.serve_file('index.html', 'text/html')
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if path == f'{API_PREFIX}/signals':
            self.handle_post_signal(body)
        elif path == f'{API_PREFIX}/signals/metadata':
            self.handle_post_metadata(body)
        elif path == f'{API_PREFIX}/gps':
            self.handle_post_gps(body)
        else:
            self.send_error(404)

    def handle_api(self, path, params):
        try:
            c = self.db_conn.cursor()

            if path == '/signals':
                limit = int(params.get('limit', [50])[0])
                rows = c.execute("SELECT * FROM signal_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
                total = c.execute("SELECT COUNT(*) FROM signal_logs").fetchone()[0]
                self.json_response({"data": [dict(r) for r in rows], "pagination": {"total": total}})

            elif path == '/radios':
                rows = c.execute("SELECT * FROM radios ORDER BY last_seen DESC LIMIT 200").fetchall()
                self.json_response({"data": [dict(r) for r in rows]})

            elif path.startswith('/radios/'):
                rid = path.split('/')[-1]
                radio = c.execute("SELECT * FROM radios WHERE radio_id_dec=?", (int(rid),)).fetchone()
                if radio:
                    gps = c.execute("SELECT * FROM gps_events WHERE radio_id=? ORDER BY timestamp DESC LIMIT 50",
                                    (radio['id'],)).fetchall()
                    inters = c.execute("SELECT i.*,t.tg_number,t.label as tg_label FROM interactions i LEFT JOIN talkgroups t ON t.id=i.talkgroup_id WHERE i.source_radio_id=? ORDER BY i.timestamp DESC LIMIT 50",
                                       (radio['id'],)).fetchall()
                    self.json_response({"radio": dict(radio), "gps_history": [dict(g) for g in gps], "interactions": [dict(x) for x in inters]})
                else:
                    self.json_response({"error": "not found"}, 404)

            elif path == '/gps':
                rows = c.execute("""SELECT g.*,r.radio_id_dec,r.radio_id_hex,r.alias
                    FROM gps_events g JOIN radios r ON r.id=g.radio_id
                    ORDER BY g.timestamp DESC LIMIT 200""").fetchall()
                self.json_response({"data": [dict(r) for r in rows]})

            elif path == '/gps/latest':
                rows = c.execute("""SELECT g.*,r.radio_id_dec,r.radio_id_hex,r.alias
                    FROM gps_events g JOIN radios r ON r.id=g.radio_id
                    WHERE g.timestamp = (SELECT MAX(g2.timestamp) FROM gps_events g2 WHERE g2.radio_id=g.radio_id)
                    ORDER BY g.timestamp DESC""").fetchall()
                self.json_response({"data": [dict(r) for r in rows]})

            elif path.startswith('/gps/radio/'):
                rid = int(path.split('/')[-1])
                radio = c.execute("SELECT id FROM radios WHERE radio_id_dec=?", (rid,)).fetchone()
                if radio:
                    rows = c.execute("SELECT * FROM gps_events WHERE radio_id=? ORDER BY timestamp DESC LIMIT 200",
                                     (radio['id'],)).fetchall()
                    self.json_response({"data": [dict(r) for r in rows]})
                else:
                    self.json_response({"data": []})

            elif path == '/topology':
                self.handle_topology(c)

            elif path == '/sdr':
                rows = c.execute("SELECT * FROM sdr_devices ORDER BY last_heartbeat DESC").fetchall()
                self.json_response({"data": [dict(r) for r in rows]})

            elif path == '/events':
                # Live event stream for polling
                since = int(params.get('since', [0])[0])
                events = self.mock_gen.event_log[since:] if self.mock_gen else []
                self.json_response({"events": events, "cursor": len(self.mock_gen.event_log) if self.mock_gen else 0})

            elif path == '/stats':
                signals = c.execute("SELECT COUNT(*) FROM signal_logs").fetchone()[0]
                radios = c.execute("SELECT COUNT(*) FROM radios").fetchone()[0]
                gps = c.execute("SELECT COUNT(DISTINCT radio_id) FROM gps_events").fetchone()[0]
                inters = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
                self.json_response({"signals": signals, "radios": radios, "gps_fixes": gps, "interactions": inters})

            elif path == '/health':
                self.json_response({"status": "healthy", "timestamp": datetime.now().isoformat()})

            else:
                self.json_response({"error": "unknown endpoint"}, 404)

        except Exception as e:
            self.json_response({"error": str(e)}, 500)

    def handle_topology(self, c):
        nodes = []
        edges = []
        seen = set()

        for n in c.execute("SELECT * FROM networks").fetchall():
            nodes.append({"id":n['id'],"type":"network","label":n['name'],"protocol":n['protocol'],"level":0})

        for bs in c.execute("SELECT * FROM base_stations").fetchall():
            nodes.append({"id":bs['id'],"type":"base_station","label":bs['site_name'],"level":1,
                          "lat":bs['location_lat'],"lon":bs['location_lon']})
            edges.append({"source":bs['network_id'],"target":bs['id'],"type":"network_to_bs","weight":1})

        for tg in c.execute("SELECT * FROM talkgroups").fetchall():
            nodes.append({"id":tg['id'],"type":"talkgroup","label":tg['label'] or f"TG {tg['tg_number']}",
                          "tg_number":tg['tg_number'],"encryption":tg['encryption_status'],"level":2})
            edges.append({"source":tg['base_station_id'],"target":tg['id'],"type":"bs_to_tg","weight":1})

        for rta in c.execute("""SELECT rta.*,r.radio_id_dec,r.alias,r.last_lat,r.last_lon
            FROM radio_talkgroup_assoc rta JOIN radios r ON r.id=rta.radio_id""").fetchall():
            rid = rta['radio_id']
            if rid not in seen:
                seen.add(rid)
                nodes.append({"id":rid,"type":"radio","label":rta['alias'] or f"RID {rta['radio_id_dec']}",
                              "radio_id":rta['radio_id_dec'],"lat":rta['last_lat'],"lon":rta['last_lon'],"level":3})
            edges.append({"source":rta['talkgroup_id'],"target":rid,"type":"tg_to_radio","weight":rta['interaction_count']})

        self.json_response({"nodes": nodes, "edges": edges})

    def handle_post_signal(self, body):
        c = self.db_conn.cursor()
        sid = hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]
        c.execute("INSERT INTO signal_logs(id,frequency,bandwidth_khz,snr_db,power_dbm,protocol_guess,protocol_confidence) VALUES(?,?,?,?,?,?,?)",
                  (sid, body.get('frequency',0), body.get('bandwidth_khz'), body.get('snr_db'),
                   body.get('power_dbm'), body.get('protocol_guess'), body.get('protocol_confidence')))
        self.db_conn.commit()
        self.json_response({"id": sid}, 201)

    def handle_post_metadata(self, body):
        self.json_response({"status": "ok"}, 201)

    def handle_post_gps(self, body):
        self.json_response({"status": "ok"}, 201)

    def serve_file(self, filename, content_type):
        filepath = os.path.join(STATIC_DIR, filename)
        if os.path.exists(filepath):
            self.send_response(200)
            self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def json_response(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        if '/api/events' not in str(args[0]):
            print(f"[HTTP] {args[0]}")

def run_server():
    print("=" * 50)
    print("  SIGINT Dashboard — Standalone Server")
    print("=" * 50)

    # Init database
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db()
    seed_db(conn)
    print(f"[DB] SQLite ready at {DB_PATH}")

    # Start mock generator
    mock = MockGenerator(conn)
    mock_thread = threading.Thread(target=mock.run_loop, daemon=True)
    mock_thread.start()

    # Configure handler
    SIGINTHandler.db_conn = conn
    SIGINTHandler.mock_gen = mock

    # Start HTTP server
    server = HTTPServer(('127.0.0.1', PORT), SIGINTHandler)
    print(f"[HTTP] Server running on http://localhost:{PORT}")
    print(f"[MOCK] Generating live data...")
    print(f"")
    print(f"  ➜ Open http://localhost:{PORT} in your browser")
    print(f"")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
        mock.running = False
        server.shutdown()
        conn.close()

if __name__ == '__main__':
    # Allow custom port
    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    run_server()
