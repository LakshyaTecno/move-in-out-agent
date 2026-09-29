"""Persistence. Requests and unit records are stored as JSON documents in
SQLite, which keeps the prototype dependency-free. Everything goes through
this module, so moving to Postgres later touches only this file."""

import json
import os
import sqlite3
from contextlib import contextmanager

from app.core.models import MoveRequest, Status, UnitRecord

DB_PATH = os.getenv("DB_PATH", "data.db")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, community_id TEXT, status TEXT, data TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS units (community_id TEXT, unit TEXT, data TEXT, PRIMARY KEY (community_id, unit))")


def save_request(req: MoveRequest) -> MoveRequest:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO requests (id, community_id, status, data) VALUES (?, ?, ?, ?)",
            (req.id, req.community_id, req.status, req.model_dump_json()),
        )
    return req


def get_request(request_id: str) -> MoveRequest | None:
    with _conn() as c:
        row = c.execute("SELECT data FROM requests WHERE id = ?", (request_id,)).fetchone()
    return MoveRequest.model_validate_json(row[0]) if row else None


def list_requests(community_id: str | None = None, statuses: list[Status] | None = None) -> list[MoveRequest]:
    sql, args = "SELECT data FROM requests WHERE 1=1", []
    if community_id:
        sql += " AND community_id = ?"
        args.append(community_id)
    if statuses:
        sql += f" AND status IN ({','.join('?' * len(statuses))})"
        args += list(statuses)
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
    reqs = [MoveRequest.model_validate_json(r[0]) for r in rows]
    return sorted(reqs, key=lambda r: r.created_at, reverse=True)


def save_unit(community_id: str, unit: UnitRecord) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO units (community_id, unit, data) VALUES (?, ?, ?)",
            (community_id, unit.unit, unit.model_dump_json()),
        )


def get_unit(community_id: str, unit: str) -> UnitRecord | None:
    with _conn() as c:
        row = c.execute(
            "SELECT data FROM units WHERE community_id = ? AND unit = ? COLLATE NOCASE", (community_id, unit.strip())
        ).fetchone()
    return UnitRecord.model_validate_json(row[0]) if row else None


def list_units(community_id: str) -> list[UnitRecord]:
    with _conn() as c:
        rows = c.execute("SELECT data FROM units WHERE community_id = ? ORDER BY unit", (community_id,)).fetchall()
    return [UnitRecord.model_validate_json(r[0]) for r in rows]


def has_units() -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM units LIMIT 1").fetchone() is not None
