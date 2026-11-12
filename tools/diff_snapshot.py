"""快照比对：保证"新数据只追加、旧数据不改动"。

用法：python tools/diff_snapshot.py <旧SQL快照> [新SQL，默认 sql/risk_alert_示例库.sql]

生成器写 SQL 时一行一条记录（(...),），所以直接按行比对最可靠，
不受 INSERT 语句分组方式影响。
"""
import io
from collections import Counter

import sys

W1 = sys.argv[1] if len(sys.argv) > 1 else 'sql/risk_alert_示例库.sql'
NOW = sys.argv[2] if len(sys.argv) > 2 else 'sql/risk_alert_示例库.sql'

def data_lines(path):
    out = Counter()
    for line in io.open(path, encoding='utf-8'):
        t = line.strip()
        if t.startswith('(') and (t.endswith('),') or t.endswith(');') or t.endswith(')')):
            out[t.rstrip(',;')] += 1
    return out

old, new = data_lines(W1), data_lines(NOW)
print('第一批快照数据行 %d 行；当前脚本数据行 %d 行' % (sum(old.values()), sum(new.values())))
miss = {k: (v, new.get(k, 0)) for k, v in old.items() if new.get(k, 0) < v}
d = sum(v - nb for v, nb in miss.values())
print('第一批中原样存在的行：%d 行' % (sum(old.values()) - d))
print('第一批中缺失或被改动的行：%d 行' % d)
for k, (v, nb) in list(miss.items())[:10]:
    print('   !', k[:110], 'old=%d new=%d' % (v, nb))
