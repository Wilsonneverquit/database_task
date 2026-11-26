"""Numbered, checksummed migrations. Never executes the original DROP DATABASE script."""
import hashlib
from .db import ROOT, connect, query, one, execute, database_name


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


def migrate(source='demo'):
    name = database_name(source)
    allowed = ('risk_alert_real',) if source == 'real' else ('risk_alert_demo', 'risk_alert_test')
    if name not in allowed:
        raise ValueError('Migration target is not a managed database')
    conn = connect(False, source=source)
    try:
        if one('SELECT GET_LOCK(%s,30) ok', ('schema_migration:'+name,), conn)['ok'] != 1:
            raise ValueError('Another migration is running')
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
