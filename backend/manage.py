import argparse
import json
import os
from .db import connect, query, execute, ROOT
from .migrate import migrate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['migrate','seed','reset-demo','audit-original','check'])
    parser.add_argument('--light',action='store_true')
    parser.add_argument('--confirm-database')
    args=parser.parse_args()
    if args.command=='audit-original':
        from .generate import audit_original
        print(json.dumps(audit_original(),ensure_ascii=False,indent=2));return
    if args.command=='reset-demo':
        name=os.getenv('DB_NAME','risk_alert_demo')
        if name not in ('risk_alert_demo','risk_alert_test') or args.confirm_database!=name:
            parser.error('Reset requires --confirm-database with the exact managed demo/test database name')
        conn=connect(False)
        execute(f'DROP DATABASE IF EXISTS `{name}`',conn=conn)
        conn.close()
        migrate()
    elif args.command=='migrate':
        migrate();return
    conn=connect()
    try:
        if args.command in ('seed','reset-demo'):
            from .generate import generate
            print(json.dumps(generate(conn,light=args.light),ensure_ascii=False))
        else:
            from .validation import validate
            report=validate(conn)
            print(json.dumps(report,ensure_ascii=False,default=str,indent=2))
            if report['errors']:raise SystemExit(1)
    except Exception:
        conn.rollback();raise
    finally:conn.close()


if __name__=='__main__':main()
