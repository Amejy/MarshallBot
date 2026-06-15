from __future__ import annotations

from pathlib import Path

from app.db.connection import get_connection


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        buffer.append(raw_line)
        if line.endswith(";"):
            statement = "\n".join(buffer).strip()
            buffer = []
            if statement:
                statements.append(statement)
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def apply_schema() -> int:
    schema_path = Path(__file__).resolve().with_name("schema.sql")
    sql_text = schema_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql_text)
    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
    return len(statements)


def main() -> int:
    count = apply_schema()
    print(f"Applied {count} schema statements.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
