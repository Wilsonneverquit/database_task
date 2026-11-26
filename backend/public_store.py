"""Install the collected release into the dedicated real database and compare live DDL."""
import argparse
import gzip
import json
import re
import secrets
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta

from .collect_public import OUT, sha
from .db import ROOT, connect, database_name, execute, insert, insert_many, now, one, query, transaction
from .generate import ACCOUNT_NAMES, initialize_accounts, initialize_rules
from .migrate import migrate


def definitions(conn):
    name = one('SELECT DATABASE() db', conn=conn)['db']
    objects = query('SELECT table_name n,table_type t FROM information_schema.tables WHERE table_schema=DATABASE()',conn=conn)
    objects += query('SELECT trigger_name n,"TRIGGER" t FROM information_schema.triggers WHERE trigger_schema=DATABASE()',conn=conn)
    objects += query('SELECT routine_name n,routine_type t FROM information_schema.routines WHERE routine_schema=DATABASE()',conn=conn)
    result = {}
    for obj in objects:
        kind = 'TABLE' if obj['t']=='BASE TABLE' else obj['t']
        key = obj['n']
        row = one(f"SHOW CREATE {kind} `{key.replace(chr(96),chr(96)*2)}`", conn=conn)
        ddl = row['SQL Original Statement' if kind=='TRIGGER' else 'Create '+kind.title()]
        ddl = ddl.replace(f'`{name}`.', '`__current__`.')
        if kind=='TABLE':
            ddl = re.sub(r'(?<=ENGINE=InnoDB) AUTO_INCREMENT=\d+', '', ddl)
        # SHOW CREATE returns per-routine session charset, collation and sql_mode as well.
        settings = {k:v for k,v in row.items() if k in ('sql_mode','character_set_client','collation_connection','Database Collation')}
        result[(kind,key)] = [ddl, settings]
    return result


def verify():
    if database_name('demo')=='risk_alert_real':
        raise ValueError('Reference database cannot be the real target')
    with closing(connect(source='demo')) as original, closing(connect(source='real')) as target:
        left, right = definitions(original), definitions(target)
        changed = sorted(key for key in left.keys() | right.keys() if left.get(key)!=right.get(key))
        if changed:
            raise ValueError(f'Live schema mismatch: {changed}')
        return dict(Counter(k for k,_ in left))


def local_passwords():
    path = ROOT / '.runtime' / 'public-logins.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with path.open('x',encoding='utf-8') as f:
            json.dump({name:secrets.token_urlsafe(18) for name in ACCOUNT_NAMES},f,indent=2)
    passwords = json.loads(path.read_text(encoding='utf-8'))
    if any(not passwords.get(k) for k in ACCOUNT_NAMES):
        raise ValueError('Incomplete local public-data credential file')
    return passwords


def install():
    manifest = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    digest = manifest['snapshot_sha256']
    if manifest['format']!=1 or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('Unsupported release format')
    raw = (OUT/(digest+'.json.gz')).read_bytes()
    if sha(raw)!=digest:
        raise ValueError('Public snapshot checksum mismatch')
    data = json.loads(gzip.decompress(raw))
    if {k:len(v) for k,v in data.items()}!=manifest['counts']:
        raise ValueError('Public snapshot row count mismatch')
    if database_name('demo')=='risk_alert_real':
        raise ValueError('Demo configuration points to the public database')
    migrate('real')
    structure = verify()
    with closing(connect(source='real')) as conn:
        if one("SELECT GET_LOCK('public_snapshot_import',10) ok",conn=conn)['ok']!=1:
            raise ValueError('Public import is busy')
        with transaction(conn):
            prior = one("SELECT param_value FROM param_config WHERE param_key='data_provenance'",conn=conn)
            if prior and prior['param_value']==digest:
                return dict(status='already_installed',structure=structure,sha256=digest)
            # Do not mix versions or attach this label to manually populated data.
            tables = query("SELECT table_name n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE' AND table_name<>'schema_migration'",conn=conn)
            for table in tables:
                if one(f"SELECT 1 FROM `{table['n']}` LIMIT 1",conn=conn):
                    raise ValueError('Target contains data from another release or manual setup')
            initialize_accounts(conn, now(), local_passwords())
            for table in ('area_info','place_info','person_info','taxi_order'):
                insert_many(table,data[table],conn)
            orders=data['taxi_order']
            start=datetime.fromisoformat(min(r['order_time'] for r in orders)).replace(hour=0,minute=0,second=0)
            end=datetime.fromisoformat(max(r['completed_at'] for r in orders)).replace(hour=0,minute=0,second=0)+timedelta(days=1)
            for key,value in [('history_cutoff',str(start)),('dataset_start',str(start)),('dataset_end',str(end)),('data_provenance',digest)]:
                insert('param_config',dict(param_key=key,param_value=value,param_desc='公开订单观察窗口 / 数据快照'),conn)
            initialize_rules(conn,start,'V_PUBLIC_1','V_PUBLIC_DRAFT')
            insert('data_quality_report',dict(source_name='公开数据采集与字段覆盖',report_json=json.dumps(
                dict(kind='public_snapshot',manifest=manifest,receipt_summary=data['receipt_summary']),ensure_ascii=False)),conn)
            for table in ('area_info','place_info','person_info','taxi_order'):
                if one(f'SELECT COUNT(*) n FROM `{table}`',conn=conn)['n']!=len(data[table]):
                    raise ValueError(f'Import count mismatch: {table}')
        return dict(status='installed',structure=structure,counts=manifest['counts'],sha256=digest)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['install','verify'])
    args=parser.parse_args()
    print(json.dumps(install() if args.command=='install' else verify()))
