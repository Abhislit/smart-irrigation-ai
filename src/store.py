"""SQLite store for per-minute irrigation readings."""

import sqlite3
from contextlib import contextmanager

COLUMNS = [
    "ts",
    "moisture",
    "temp",
    "humidity",
    "pump",
    "minutes_since_irrigation",
    "source",
]


@contextmanager
def db(db_path: str):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: str) -> None:
    with db(db_path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS readings (
                ts TEXT PRIMARY KEY,
                moisture REAL NOT NULL,
                temp REAL NOT NULL,
                humidity REAL NOT NULL,
                pump INTEGER NOT NULL,
                minutes_since_irrigation REAL NOT NULL,
                source TEXT NOT NULL
            )"""
        )


def insert_reading(db_path: str, row: dict) -> None:
    with db(db_path) as con:
        con.execute(
            "INSERT OR REPLACE INTO readings (ts, moisture, temp, humidity, pump, "
            "minutes_since_irrigation, source) VALUES (?,?,?,?,?,?,?)",
            tuple(row[c] for c in COLUMNS),
        )


def latest(db_path: str) -> dict | None:
    with db(db_path) as con:
        row = con.execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def read_window(db_path: str, n: int) -> list[dict]:
    with db(db_path) as con:
        rows = con.execute(
            "SELECT * FROM (SELECT * FROM readings ORDER BY ts DESC LIMIT ?) ORDER BY ts ASC",
            (n,),
        ).fetchall()
    return [dict(r) for r in rows]


def count(db_path: str) -> int:
    with db(db_path) as con:
        return int(con.execute("SELECT COUNT(*) FROM readings").fetchone()[0])


def appended_since(db_path: str, source: str) -> int:
    with db(db_path) as con:
        return int(
            con.execute("SELECT COUNT(*) FROM readings WHERE source = ?", (source,)).fetchone()[0]
        )
