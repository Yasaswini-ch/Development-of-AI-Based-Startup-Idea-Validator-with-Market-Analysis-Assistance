"""One-off: copy every Affinity table from one Postgres database to another.

Used to move the old Render Postgres into Neon without pg_dump/psql. Reads
the two connection strings from env vars (so passwords never land in shell
history or the repo):

    SOURCE_DATABASE_URL   old database (Render External Database URL)
    DEST_DATABASE_URL     new database (Neon pooled connection string)

    python scripts/copy_database.py            # copy, refuses non-empty tables
    python scripts/copy_database.py --dry-run  # only print row counts

Run from the backend/ folder. The source is only ever read.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from agent import db  # noqa: E402

BATCH = 500


def _normalize(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print source row counts and exit")
    args = parser.parse_args()

    source_url = os.environ.get("SOURCE_DATABASE_URL", "").strip()
    dest_url = os.environ.get("DEST_DATABASE_URL", "").strip()
    if not source_url or (not dest_url and not args.dry_run):
        print("Set SOURCE_DATABASE_URL and DEST_DATABASE_URL first.", file=sys.stderr)
        return 2

    source = create_engine(_normalize(source_url), pool_pre_ping=True)
    tables = list(db.metadata.sorted_tables)

    with source.connect() as conn:
        counts = {t.name: conn.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}
    print("Source rows:", ", ".join(f"{name}={n}" for name, n in counts.items()))
    if args.dry_run:
        return 0

    # Creates any missing tables and applies db.py's column migrations, the
    # same as the app does on startup.
    os.environ["DATABASE_URL"] = dest_url
    dest = db.get_engine()

    with dest.connect() as conn:
        for t in tables:
            existing = conn.execute(select(func.count()).select_from(t)).scalar_one()
            if existing:
                print(f"Refusing: destination table '{t.name}' already has {existing} rows.", file=sys.stderr)
                return 1

    with source.connect() as src, dest.begin() as dst:
        for t in tables:
            copied = 0
            result = src.execute(select(t)).mappings()
            while True:
                rows = result.fetchmany(BATCH)
                if not rows:
                    break
                dst.execute(t.insert(), [dict(r) for r in rows])
                copied += len(rows)
            print(f"Copied {t.name}: {copied} rows")

        if dest.dialect.name == "postgresql":
            dst.execute(
                text("SELECT setval(pg_get_serial_sequence('events', 'id'), COALESCE((SELECT MAX(id) FROM events), 1))")
            )

    with dest.connect() as conn:
        for t in tables:
            after = conn.execute(select(func.count()).select_from(t)).scalar_one()
            status = "OK" if after == counts[t.name] else "MISMATCH"
            print(f"{status}: {t.name} source={counts[t.name]} dest={after}")
            if after != counts[t.name]:
                return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
