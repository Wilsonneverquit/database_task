import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import g
from flask.json.provider import DefaultJSONProvider

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / 'backend' / '.env')


def now():
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


class JSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return DefaultJSONProvider.default(value)


def connect(database=True):
    return pymysql.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'), port=int(os.getenv('DB_PORT', '3307')),
        user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'risk_alert_demo') if database else None,
        charset='utf8mb4', collation='utf8mb4_0900_as_cs', cursorclass=pymysql.cursors.DictCursor,
        autocommit=False, connect_timeout=5, read_timeout=120, write_timeout=120,
        init_command="SET time_zone = '+08:00'",
    )


def get_db():
    if 'db' not in g:
        g.db = connect()
    return g.db


def query(sql, args=(), conn=None):
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def one(sql, args=(), conn=None):
    rows = query(sql, args, conn)
    return rows[0] if rows else None


def execute(sql, args=(), conn=None):
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, args)
        return cur.lastrowid, cur.rowcount


def insert(table, row, conn):
    # Only application-owned constant table/column names reach this function.
    cols = ','.join('`' + k + '`' for k in row)
    with conn.cursor() as cur:
        cur.execute(f'INSERT INTO `{table}` ({cols}) VALUES ({",".join(["%s"] * len(row))})', list(row.values()))
        return cur.lastrowid


def insert_many(table, rows, conn):
    if not rows:
        return
    keys = list(rows[0])
    with conn.cursor() as cur:
        sql = f'INSERT INTO `{table}` ({",".join("`" + k + "`" for k in keys)}) VALUES ({",".join(["%s"] * len(keys))})'
        for start in range(0, len(rows), 1000):
            cur.executemany(sql, [[r[k] for k in keys] for r in rows[start:start + 1000]])


@contextmanager
def transaction(conn=None):
    conn = conn or get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def audit(user, table, pk, description, op=4, conn=None):
    execute('INSERT INTO audit_log (user_id,operator_tag,op_type,table_name,record_pk,op_desc) VALUES (%s,%s,%s,%s,%s,%s)',
            (user, user or 'system', op, table, str(pk), description[:255]), conn)
