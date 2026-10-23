"""SQLite storage, password hashing, seed data."""
import hashlib
import json
import os
import secrets
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("BS_DB", os.path.join(ROOT, "data", "brandsentinel.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT,
  team TEXT, salt TEXT, pw_hash TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
CREATE TABLE IF NOT EXISTS brandkit(version INTEGER PRIMARY KEY, json TEXT, created_by INTEGER, ts REAL, note TEXT);
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, title TEXT, kind TEXT, owner_id INTEGER, status TEXT,
  created REAL, updated REAL, extra_json TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY, item_id INTEGER, n INTEGER, content TEXT,
  meta_json TEXT, findings_json TEXT, claims_json TEXT, kit_version INTEGER, created_by INTEGER, ts REAL,
  note TEXT, ai_used INTEGER DEFAULT 0, blob BLOB);
CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, item_id INTEGER, rev_n INTEGER, fid TEXT,
  user_id INTEGER, body TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, item_id INTEGER, rev_n INTEGER, key TEXT,
  rule_id TEXT, source_id TEXT, action TEXT, reason TEXT, user_id INTEGER, ts REAL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts REAL, user_id INTEGER, action TEXT,
  item_id INTEGER, detail TEXT);
"""

DEMO_USERS = [
    ("ana", "Ana Rao", "creator", "Marketing"),
    ("ben", "Ben Okafor", "creator", "Regional"),
    ("mira", "Mira Das", "reviewer", "Brand"),
    ("raj", "Raj Menon", "manager", "Brand"),
    ("root", "Admin", "admin", "IT"),
]
DEMO_PASSWORD = os.environ.get("BS_DEMO_PASSWORD", "demo123")


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()


def init(seed=True):
    c = connect()
    c.executescript(SCHEMA)
    if seed and c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for u, n, r, t in DEMO_USERS:
            salt = secrets.token_hex(16)
            c.execute("INSERT INTO users(username,name,role,team,salt,pw_hash) VALUES(?,?,?,?,?,?)",
                      (u, n, r, t, salt, hash_pw(DEMO_PASSWORD, salt)))
    if c.execute("SELECT COUNT(*) FROM brandkit").fetchone()[0] == 0:
        with open(os.path.join(ROOT, "data", "brandkit.json"), encoding="utf8") as f:
            kit = f.read()
        c.execute("INSERT INTO brandkit(version,json,created_by,ts,note) VALUES(1,?,NULL,?,?)",
                  (kit, time.time(), "Initial sample brand kit"))
    c.commit()
    c.close()


def latest_kit(c):
    row = c.execute("SELECT version,json FROM brandkit ORDER BY version DESC LIMIT 1").fetchone()
    return row["version"], json.loads(row["json"])
