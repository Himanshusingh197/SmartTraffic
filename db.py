import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  source TEXT NOT NULL,
  north_count INTEGER NOT NULL,
  south_count INTEGER NOT NULL,
  east_count INTEGER NOT NULL,
  west_count INTEGER NOT NULL,
  north_green INTEGER NOT NULL,
  south_green INTEGER NOT NULL,
  east_green INTEGER NOT NULL,
  west_green INTEGER NOT NULL,
  total_vehicles INTEGER NOT NULL,
  cycle_total INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cycles_ts ON cycles(ts);
"""


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_cycle(source, counts, timings_obj):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t = timings_obj["timings"]
    row = (
        ts, source,
        counts["north"], counts["south"], counts["east"], counts["west"],
        t["north"]["green"], t["south"]["green"], t["east"]["green"], t["west"]["green"],
        timings_obj["total_vehicles"], timings_obj["cycle_total"],
    )
    with _conn() as conn:
        conn.execute("""
            INSERT INTO cycles
            (ts, source,
             north_count, south_count, east_count, west_count,
             north_green, south_green, east_green, west_green,
             total_vehicles, cycle_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)


def recent_cycles(limit=20):
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def stats():
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) AS n FROM cycles").fetchone()["n"]
        if total == 0:
            return {"total_cycles": 0, "avg_vehicles": 0, "busiest_lane": None, "last_ts": None}
        avg_row = conn.execute("SELECT AVG(total_vehicles) AS a FROM cycles").fetchone()
        last_row = conn.execute("SELECT ts FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
        sums = conn.execute("""
            SELECT SUM(north_count) AS n, SUM(south_count) AS s,
                   SUM(east_count) AS e, SUM(west_count) AS w
            FROM cycles
        """).fetchone()
    lane_sum = {
        "north": sums["n"] or 0, "south": sums["s"] or 0,
        "east": sums["e"] or 0, "west": sums["w"] or 0,
    }
    busiest = max(lane_sum, key=lane_sum.get)
    return {
        "total_cycles": total,
        "avg_vehicles": round(avg_row["a"] or 0, 2),
        "busiest_lane": busiest,
        "last_ts": last_row["ts"],
    }