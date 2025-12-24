"""
Inspect parsed resumes in the database.

输入命令:
1. python inspect_parsed_db.py --db parsed_data.db --table parsed_resumes --limit 10 --offset 0 --show-content --pretty
输出:
- 显示数据库中的前10条记录
- 包含id, hash, parsed_data, timestamp字段
- --show-content参数, 显示parsed_data字段的内容
- --pretty参数, 对JSON内容进行格式化输出

2. python inspect_parsed_db.py --db parsed_data.db --table parsed_resumes --id 123 --show-content --pretty
输出:
- 输出id为123的记录
"""

import argparse
import json
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path


def _safe_pickle_load(blob: bytes):
    try:
        return pickle.loads(blob)
    except Exception:
        return None


def _to_iso(ts):
    try:
        return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="parsed_data.db")
    parser.add_argument("--table", default="parsed_resumes")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--id", dest="row_id", default=None)
    parser.add_argument("--show-content", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path.resolve()}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables:", tables)

        if args.table not in tables:
            raise SystemExit(f"Table not found: {args.table}")

        cur.execute(f"PRAGMA table_info({args.table})")
        cols = [r[1] for r in cur.fetchall()]
        print("Columns:", cols)

        cur.execute(f"SELECT COUNT(*) FROM {args.table}")
        total = int(cur.fetchone()[0])
        print("Rows:", total)

        if args.row_id:
            cur.execute(
                f"SELECT id, hash, parsed_data, timestamp FROM {args.table} WHERE id = ?",
                (args.row_id,),
            )
        else:
            cur.execute(
                f"SELECT id, hash, parsed_data, timestamp FROM {args.table} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (args.limit, args.offset),
            )

        rows = cur.fetchall()
        out = []
        for rid, h, blob, ts in rows:
            decoded = _safe_pickle_load(blob) if blob is not None else None
            content = None
            wrapper_keys = None
            if isinstance(decoded, dict):
                wrapper_keys = sorted(decoded.keys())
                content = decoded.get("content", decoded)
            item = {
                "id": rid,
                "hash": h,
                "timestamp": ts,
                "timestamp_iso": _to_iso(ts),
                "blob_bytes": len(blob) if blob is not None else 0,
                "wrapper_keys": wrapper_keys,
            }
            if args.show_content:
                item["content"] = content
            out.append(item)

        if args.pretty:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(out, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

# python inspect_parsed_db.py --db parsed_data.db --limit 10 --pretty
# python inspect_parsed_db.py --id "9ff9759d-792f-5fdc-9a0d-6ebf6736faff" --show-content --pretty