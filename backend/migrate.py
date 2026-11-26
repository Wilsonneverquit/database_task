"""Numbered, checksummed migrations. Never executes the original DROP DATABASE script."""
import hashlib
import re
from .db import ROOT, connect, query, execute
import os


def statements(source):
    delimiter = ';'
    buffer = []
    for line in source.splitlines():
        if line.strip().startswith('--') or not line.strip():
            continue
        if line.strip().upper().startswith('DELIMITER '):
            delimiter = line.strip().split()[1]
            continue
        buffer.append(line)
        if line.rstrip().endswith(delimiter):
            yield '\n'.join(buffer).rstrip()[:-len(delimiter)]
            buffer = []
    if ''.join(buffer).strip():
        raise ValueError('Unterminated SQL statement')


def migrate():
    name = os.getenv('DB_NAME', 'risk_alert_demo')
    if not re.fullmatch(r'risk_alert_(demo|test)', name):
        raise ValueError('Migrations only target risk_alert_demo or risk_alert_test; original risk_alert is protected')
    conn = connect(False)
    try:
        execute(f'CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs', conn=conn)
        conn.select_db(name)
        execute('CREATE TABLE IF NOT EXISTS schema_migration (version VARCHAR(100) PRIMARY KEY, checksum CHAR(64) NOT NULL, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)', conn=conn)
        applied = {r['version']: r['checksum'] for r in query('SELECT * FROM schema_migration', conn=conn)}
        for path in sorted((ROOT / 'sql' / 'migrations').glob('*.sql')):
            source = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(source.encode()).hexdigest()
            if path.name in applied:
                if applied[path.name] != checksum:
                    raise ValueError(f'Migration checksum changed: {path.name}')
                continue
            for statement in statements(source):
                execute(statement, conn=conn)
            execute('INSERT INTO schema_migration(version,checksum) VALUES (%s,%s)', (path.name, checksum), conn)
            conn.commit()
            print('Applied', path.name)
    finally:
        conn.close()
