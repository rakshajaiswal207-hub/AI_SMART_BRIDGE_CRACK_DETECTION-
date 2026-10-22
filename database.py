"""Inspection records.

The table matches Table 9.2: one row per captured image, with the date,
time, file locations, detection status and region count stored separately.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

import config

try:
    import mysql.connector
except ImportError:  # pragma: no cover - optional until MySQL is used
    mysql = None
else:
    mysql = mysql.connector

ENGINE = "sqlite"
ENGINE_DETAIL = "SQLite (data/inspections.db)"

_COLUMNS = (
    "id",
    "captured_date",
    "captured_time",
    "original_path",
    "result_path",
    "status",
    "region_count",
)


def init_db() -> str:
    """Create the inspections table and return a short description of the engine."""
    global ENGINE, ENGINE_DETAIL

    requested = config.DB_ENGINE
    if requested not in {"auto", "mysql", "sqlite"}:
        raise ValueError("DB_ENGINE must be auto, mysql or sqlite")

    if requested in {"auto", "mysql"}:
        try:
            _init_mysql()
            ENGINE = "mysql"
            ENGINE_DETAIL = f"MySQL ({config.MYSQL_DATABASE} on {config.MYSQL_HOST})"
            return ENGINE_DETAIL
        except Exception as exc:
            if requested == "mysql":
                raise
            print(f"MySQL is not reachable ({exc}). Inspection records will use SQLite.")

    _init_sqlite()
    ENGINE = "sqlite"
    ENGINE_DETAIL = "SQLite (data/inspections.db)"
    return ENGINE_DETAIL


def insert_inspection(
    captured_date: str,
    captured_time: str,
    original_path: str,
    result_path: str,
    status: str,
    region_count: int,
) -> int:
    sql = """
        INSERT INTO inspections (
            captured_date, captured_time, original_path, result_path, status, region_count
        ) VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        captured_date,
        captured_time,
        original_path,
        result_path,
        status,
        region_count,
    )
    with _cursor() as cursor:
        if ENGINE == "mysql":
            cursor.execute(sql.replace("?", "%s"), params)
            return int(cursor.lastrowid)
        cursor.execute(sql, params)
        return int(cursor.lastrowid)


def list_inspections(limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT id, captured_date, captured_time, original_path, result_path,
               status, region_count
        FROM inspections
        ORDER BY id DESC
        LIMIT ?
    """
    with _cursor() as cursor:
        if ENGINE == "mysql":
            cursor.execute(sql.replace("?", "%s"), (limit,))
        else:
            cursor.execute(sql, (limit,))
        return [_row_dict(row) for row in cursor.fetchall()]


def get_inspection(inspection_id: int) -> dict[str, Any] | None:
    sql = """
        SELECT id, captured_date, captured_time, original_path, result_path,
               status, region_count
        FROM inspections
        WHERE id = ?
    """
    with _cursor() as cursor:
        if ENGINE == "mysql":
            cursor.execute(sql.replace("?", "%s"), (inspection_id,))
        else:
            cursor.execute(sql, (inspection_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return _row_dict(row)


def _init_mysql() -> None:
    if mysql is None:
        raise RuntimeError("mysql-connector-python is not installed")

    bootstrap = mysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        connection_timeout=3,
    )
    try:
        cursor = bootstrap.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
    finally:
        bootstrap.close()

    with _mysql_cursor(commit=True) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id INT PRIMARY KEY AUTO_INCREMENT,
                captured_date DATE NOT NULL,
                captured_time TIME NOT NULL,
                original_path VARCHAR(255) NOT NULL,
                result_path VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                region_count INT NOT NULL
            )
            """
        )


def _init_sqlite() -> None:
    config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _sqlite_cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_date TEXT NOT NULL,
                captured_time TEXT NOT NULL,
                original_path TEXT NOT NULL,
                result_path TEXT NOT NULL,
                status TEXT NOT NULL,
                region_count INTEGER NOT NULL
            )
            """
        )


def _mysql_cursor(commit: bool = False):
    return _Cursor(kind="mysql", commit=commit)


def _sqlite_cursor():
    return _Cursor(kind="sqlite", commit=True)


def _cursor():
    if ENGINE == "mysql":
        return _mysql_cursor(commit=True)
    return _sqlite_cursor()


class _Cursor:
    def __init__(self, kind: str, commit: bool) -> None:
        self.kind = kind
        self.commit = commit
        self.connection = None
        self.cursor = None

    def __enter__(self):
        if self.kind == "mysql":
            self.connection = mysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                connection_timeout=3,
            )
        else:
            self.connection = sqlite3.connect(config.SQLITE_PATH, timeout=10)
        self.cursor = self.connection.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is None and self.commit:
                self.connection.commit()
            elif exc_type is not None:
                self.connection.rollback()
        finally:
            self.cursor.close()
            self.connection.close()


def _row_dict(row: tuple) -> dict[str, Any]:
    raw = dict(zip(_COLUMNS, row, strict=True))
    raw["captured_date"] = _format_date(raw["captured_date"])
    raw["captured_time"] = _format_time(raw["captured_time"])
    raw["region_count"] = int(raw["region_count"])
    raw["id"] = int(raw["id"])
    return raw


def _format_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_time(value: Any) -> str:
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    text = str(value)
    return text[:8] if len(text) >= 8 else text
