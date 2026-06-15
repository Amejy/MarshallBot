from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+psycopg://")
    return database_url


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(_normalize_database_url(settings.database_url), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
