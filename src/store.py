"""SQLite store for per-minute irrigation readings."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from statistics import median

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


def parse_ts(ts: str) -> datetime | None:
    """Naive local datetime, or None when the value is not a usable timestamp."""
    try:
        return datetime.fromisoformat(ts).astimezone().replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def active_source(
    db_path: str, now: datetime | None = None, live_minutes: float = 5.0
) -> tuple[str, bool]:
    """ESP32 if its newest reading is fresh, otherwise the simulated fallback."""
    now = now or datetime.now()
    with db(db_path) as con:
        rows = con.execute(
            "SELECT ts FROM readings WHERE source = 'esp32' ORDER BY ts DESC LIMIT 20"
        ).fetchall()
    newest = None
    for (ts,) in rows:
        newest = parse_ts(ts)
        if newest:
            break
    if newest and (now - newest).total_seconds() / 60.0 <= live_minutes:
        return "esp32", True
    return "simulated", False


def read_source_window(db_path: str, source: str, n: int) -> list[dict]:
    """Newest n rows for one source, returned oldest first."""
    with db(db_path) as con:
        rows = con.execute(
            "SELECT * FROM (SELECT * FROM readings WHERE source = ? ORDER BY ts DESC LIMIT ?) "
            "ORDER BY ts ASC",
            (source, n),
        ).fetchall()
    return [dict(r) for r in rows]


def analytics(
    db_path: str,
    now: datetime | None = None,
    live_minutes: float = 5.0,
    series_n: int = 120,
) -> dict:
    """Stats, series, histogram and pump events for the active source."""
    now = now or datetime.now()
    source, live = active_source(db_path, now=now, live_minutes=live_minutes)
    with db(db_path) as con:
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM readings WHERE source = ? ORDER BY ts ASC", (source,)
            ).fetchall()
        ]

    moistures = [float(r["moisture"]) for r in rows]
    stats = {
        "count": len(rows),
        "min": round(min(moistures), 2) if moistures else None,
        "max": round(max(moistures), 2) if moistures else None,
        "avg": round(sum(moistures) / len(moistures), 2) if moistures else None,
        "first": rows[0]["ts"] if rows else None,
        "last": rows[-1]["ts"] if rows else None,
        "interval_s": None,
        "gaps": 0,
    }

    diffs = []
    for a, b in zip(rows, rows[1:]):
        start, end = parse_ts(a["ts"]), parse_ts(b["ts"])
        if start and end:
            diffs.append((end - start).total_seconds())
    interval = median(diffs) if diffs else None
    if interval is not None:
        stats["interval_s"] = round(interval)
        stats["gaps"] = sum(1 for d in diffs if d > interval * 2.5)

    buckets = [0] * 10
    for m in moistures:
        buckets[max(0, min(9, int(m // 10)))] += 1
    histogram = [
        {"bucket": f"{i * 10}-{(i + 1) * 10}", "rows": buckets[i]} for i in range(10)
    ]

    window = rows[-series_n:]
    pump_events = []
    start = None
    for r in window:
        if r["pump"] and start is None:
            start = r["ts"]
        elif not r["pump"] and start is not None:
            begin, end = parse_ts(start), parse_ts(r["ts"])
            pump_events.append(
                {
                    "start": start,
                    "end": r["ts"],
                    "duration_s": round((end - begin).total_seconds())
                    if begin and end
                    else None,
                }
            )
            start = None
    if start is not None:
        pump_events.append({"start": start, "end": None, "duration_s": None})

    series = [
        {"ts": r["ts"], "moisture": round(float(r["moisture"]), 2), "pump": int(r["pump"])}
        for r in window
    ]

    return {
        "live": live,
        "source": source,
        "stats": stats,
        "series": series,
        "histogram": histogram,
        "pump_events": pump_events,
    }
