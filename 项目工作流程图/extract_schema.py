# -*- coding: utf-8 -*-
"""从 sql/risk_alert_示例库.sql 抽取结构，产出 schema.json（图的数据源，不手抄）。"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SQL = ROOT.parent / "sql" / "risk_alert_示例库.sql"
OUT = ROOT / "schema.json"

text = SQL.read_text(encoding="utf-8")


def split_top(s):
    """按顶层逗号切分（忽略括号内逗号）。"""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


tables = []
for m in re.finditer(r"CREATE TABLE\s+(\w+)\s*\((.*?)\)\s*ENGINE=InnoDB\s*(?:COMMENT='([^']*)')?\s*;",
                     text, re.S):
    name, body, tcomment = m.group(1), m.group(2), m.group(3) or ""
    cols, pk, uniques, indexes, checks, fks = [], [], [], [], [], []
    for item in split_top(body):
        up = item.upper()
        if up.startswith("PRIMARY KEY"):
            pk = re.findall(r"\w+", item[item.index("(") + 1:item.index(")")])
            continue
        if up.startswith("UNIQUE KEY"):
            uniques.append(re.match(r"UNIQUE KEY\s+(\w+)", item).group(1))
            continue
        if up.startswith("KEY "):
            indexes.append(re.match(r"KEY\s+(\w+)", item).group(1))
            continue
        if up.startswith("CONSTRAINT"):
            cm = re.match(r"CONSTRAINT\s+(\w+)", item)
            cname = cm.group(1)
            if "FOREIGN KEY" in up:
                fm = re.search(r"FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)", item, re.I)
                fks.append({"name": cname, "col": fm.group(1), "table": fm.group(2), "to": fm.group(3)})
            else:
                checks.append({"name": cname, "expr": item[item.index("CHECK") + 5:].strip()})
            continue
        if up.startswith("CHECK"):
            checks.append({"name": "", "expr": item[5:].strip()})
            continue
        # 普通列
        cm = re.match(r"(\w+)\s+([A-Za-z][A-Za-z0-9]*(?:\([^)]*\))?(?:\s+UNSIGNED)?)", item)
        if not cm:
            continue
        col, ctype = cm.group(1), cm.group(2)
        ccomment = ""
        qm = re.search(r"COMMENT\s+'([^']*)'", item)
        if qm:
            ccomment = qm.group(1)
        gen = bool(re.search(r"GENERATED ALWAYS AS", item, re.I))
        cols.append({"name": col, "type": ctype, "comment": ccomment,
                     "notnull": "NOT NULL" in up, "auto": "AUTO_INCREMENT" in up,
                     "gen": gen})

    for fk in fks:
        for c in cols:
            if c["name"] == fk["col"]:
                c["fk"] = f"{fk['table']}.{fk['to']}"
    for c in cols:
        c["pk"] = c["name"] in pk
    tables.append({"name": name, "comment": tcomment, "pk": pk, "cols": cols,
                   "fks": fks, "checks": checks, "uniques": uniques, "indexes": indexes})

views = re.findall(r"CREATE OR REPLACE VIEW\s+(\w+)\s+AS(.*?);", text, re.S)
triggers = re.findall(r"CREATE TRIGGER\s+(\w+)\s+(AFTER|BEFORE)\s+(\w+)\s+ON\s+(\w+)", text, re.I)
procs = re.findall(r"CREATE PROCEDURE\s+(\w+)", text)

schema = {
    "db": "risk_alert",
    "tables": tables,
    "views": [{"name": v[0], "body": v[1].strip()} for v in views],
    "triggers": [{"name": t[0], "timing": t[1], "event": t[2], "on": t[3]} for t in triggers],
    "procedures": procs,
    "stats": {
        "tables": len(tables),
        "fks": sum(len(t["fks"]) for t in tables),
        "checks": sum(len(t["checks"]) for t in tables),
        "views": len(views), "triggers": len(triggers), "procedures": len(procs),
    },
}
OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(schema["stats"], ensure_ascii=False))
for t in tables:
    print(f"  {t['name']:<24} cols={len(t['cols']):>2} fk={len(t['fks'])} ck={len(t['checks'])}  {t['comment']}")
print("views:", [v["name"] for v in schema["views"]])
print("triggers:", [(t["name"], t["on"]) for t in schema["triggers"]])
print("procs:", schema["procedures"])
