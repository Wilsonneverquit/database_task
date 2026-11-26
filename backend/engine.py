import json
import time
from collections import defaultdict
from datetime import timedelta
from .db import query, one, execute, insert, insert_many, audit
from .scoring import REGION, PERSON, dt, decay, index_score, match_episode, episodes, percentile95


def load_events(conn, start, end):
    cons = query('SELECT c.*,p.area_id FROM consume_record c JOIN place_info p ON p.place_id=c.place_id WHERE c.is_active=1 AND p.is_active=1 AND c.consume_time >= %s AND c.consume_time < %s AND c.recorded_at < %s ORDER BY c.consume_time', (start, end, end), conn)
    tracks = query('SELECT t.*,v.owner_person_id FROM vehicle_track t JOIN vehicle_owner v ON v.vehicle_id=t.vehicle_id WHERE t.is_active=1 AND v.is_active=1 AND t.pass_time >= %s AND t.pass_time < %s AND t.recorded_at < %s', (start, end, end), conn)
    orders = query('SELECT * FROM taxi_order WHERE is_active=1 AND order_time >= %s AND order_time < %s AND recorded_at < %s', (start, end, end), conn)
    evidence = {r['track_id']: r for r in query('SELECT * FROM driver_evidence WHERE observed_at < %s AND recorded_at < %s', (end, end), conn)}
    return cons, tracks, orders, evidence


def build_baseline(conn, cutoff):
    rows = query('SELECT p.area_id,HOUR(c.consume_time) hour_slot,c.consume_time,c.has_alcohol,c.amount FROM consume_record c JOIN place_info p ON p.place_id=c.place_id WHERE c.consume_time<%s AND c.recorded_at<%s AND c.is_active=1', (cutoff, cutoff), conn)
    buckets = defaultdict(lambda: [0, 0, 0.])
    for r in rows:
        k = (r['area_id'], r['consume_time'].date().isoformat(), r['hour_slot'])
        b = buckets[k]
        b[0] += r['has_alcohol']; b[1] += 1; b[2] += float(r['amount']) if r['has_alcohol'] else 0
    global_p95 = max(1, percentile95(b[0] for b in buckets.values()))
    areas = {}
    meta = {r['area_id']: r['area_type'] for r in query('SELECT area_id,area_type FROM area_info', conn=conn)}
    for aid, typ in meta.items():
        for hour in range(24):
            samples = [b[0] for (a, _, h), b in buckets.items() if a == aid and h == hour]
            source = 'area'
            if len(samples) < 5:
                samples = [b[0] for (a, _, h), b in buckets.items() if meta[a] == typ and h == hour]
                source = 'area_type'
            if len(samples) < 5:
                value = global_p95; source = 'global'
            else:
                value = max(1, percentile95(samples))
            areas[f'{aid}:{hour}'] = {'p95': value, 'source': source}
    history = query('SELECT area_id,COUNT(*) cnt FROM v_case_history WHERE created_at<%s GROUP BY area_id', (cutoff,), conn)
    max_cases = max([r['cnt'] for r in history] or [1])
    return {'cutoff': str(cutoff), 'areas': areas, 'global_p95': global_p95,
            'history': {r['area_id']: r['cnt'] / max_cases for r in history},
            'region_denominators': {'F001': 4, 'F002': global_p95, 'F004': .5, 'F003': 1, 'F008': 1},
            'person_denominators': {'F002': 2, 'F004': 1, 'F003': 1, 'F008': 2, 'F005': 1}}


def calculate(conn, batch):
    start, end = dt(batch['data_start']), dt(batch['data_end'])
    version = one('SELECT * FROM feature_version WHERE version_id=%s', (batch['version_id'],), conn)
    rule = one('SELECT * FROM judge_rule WHERE rule_id=%s', (batch['rule_id'],), conn)
    if not version or not version['baseline_json']:
        raise ValueError('该版本没有已冻结的历史基线，请先计算草稿版本')
    baseline = json.loads(version['baseline_json'])
    config = json.loads(rule['config_json'])
    if config.get('version_id') != batch['version_id']:
        raise ValueError('规则与权重版本不一致')
    cons, tracks, orders, evidence = load_events(conn, start - timedelta(hours=3), end)
    by_hour = defaultdict(list)
    for c in cons:
        by_hour[c['consume_time'].replace(minute=0, second=0, microsecond=0)].append(c)
    orders_by_person, tracks_by_person = defaultdict(list), defaultdict(list)
    for o in orders: orders_by_person[o['person_id']].append(o)
    for t in tracks: tracks_by_person[t['owner_person_id']].append(t)
    for t in tracks:
        observed=evidence.get(t['track_id'])
        if observed and observed['person_id']!=t['owner_person_id']:
            tracks_by_person[observed['person_id']].append(t)
    areas = query('SELECT area_id FROM area_info WHERE (%s IS NULL OR area_id=%s)', (batch['area_id'], batch['area_id']), conn)
    past_cases = query('SELECT * FROM v_case_history WHERE occur_time < %s AND created_at<%s', (end,end), conn)
    coverage_rows = query('SELECT * FROM ingest_window WHERE window_end>%s AND window_start<%s', (start-timedelta(hours=3), end), conn)
    def missing_at(t):
        absent = set()
        for source, fids in [('consume', ['F001','F002']), ('track', ['F004','F005']), ('order', ['F003'])]:
            present = any(r['source_type'] == source and r['window_start'] <= t-timedelta(hours=1) and r['window_end'] >= t and r['available_at'] < t and float(r['coverage']) >= .7 for r in coverage_rows)
            if not present: absent.update(fids)
        return absent
    cursor = start
    while cursor < end:
        until = min(cursor + timedelta(hours=1), end)
        recent = []
        for offset in range(-2, 1): recent.extend(by_hour.get(cursor + timedelta(hours=offset), []))
        recent = [c for c in recent if cursor-timedelta(hours=2) <= c['consume_time'] < until and c['recorded_at'] < until]
        eps = [match_episode(e, tracks_by_person[e[0]['person_id']], orders_by_person[e[0]['person_id']], evidence, until) for e in episodes(recent)]
        missing = missing_at(until)
        if batch['judge_object'] == 1:
            for a in areas:
                aid = a['area_id']
                mine = [c for c in recent if c['area_id'] == aid]
                alcohol = [c for c in mine if c['has_alcohol']]
                relevant = [e for e in eps if e['area_id'] == aid and any(c['has_alcohol'] for c in e['consumes'])]
                alcohol_now = [c for c in alcohol if c['consume_time'] >= cursor]
                activity = sum(decay((until-c['consume_time']).total_seconds()/60) for c in alcohol)
                raw = {'F001': len({c['place_id'] for c in alcohol_now}), 'F002': activity,
                       'F004': sum((1 if e['confirmed'] else .4) * decay((until-e['track']['pass_time']).total_seconds()/60) for e in relevant if e['track'] and not e['safe']) / max(1, len(relevant)),
                       'F003': sum(not e['safe'] for e in relevant)/max(1,len(relevant)) if relevant else 0,
                       'F008': baseline['history'].get(aid, 0)}
                den = dict(baseline['region_denominators']); den['F002'] = baseline['areas'][f'{aid}:{cursor.hour}']['p95']
                result = index_score(raw, config['weights'], den, missing, sample_size=len(mine), min_sample=rule['min_sample'])
                yield dict(result, object_type=1, area_id=aid, day_type=2 if cursor.weekday()>=5 else 1, hour_slot=cursor.hour, person_id=None,
                           window_start=cursor, window_end=until, sample_size=len(mine), episode_key=None, episodes=relevant,
                           low=rule['low_threshold'], high=rule['high_threshold'], min_hit=rule['min_hit_cnt'])
        else:
            # Latest episode per person for this hour; chain keeps the episode identity.
            latest = {}
            for e in eps:
                if batch['area_id'] and e['area_id'] != batch['area_id']: continue
                if e['person_id'] not in latest or e['first_at'] > latest[e['person_id']]['first_at']: latest[e['person_id']] = e
            for pid, e in latest.items():
                alcohol = [c for c in e['consumes'] if c['has_alcohol']]
                age = (until-e['track']['pass_time']).total_seconds()/60 if e['track'] else 0
                case_count = sum(1 for c in past_cases if c['person_id'] == pid and cursor-timedelta(days=90) <= c['occur_time'] < until and c['created_at']<until)
                raw = {'F002': sum(decay((until-c['consume_time']).total_seconds()/60) for c in alcohol),
                       'F004': (1 if e['confirmed'] else .4)*decay(age) if e['track'] else 0,
                       'F003': int(bool(alcohol) and not e['safe']), 'F008': case_count,
                       'F005': decay((e['track']['pass_time']-e['consumes'][-1]['consume_time']).total_seconds()/60) if e['track'] and alcohol else 0}
                result = index_score(raw, config['weights'], baseline['person_denominators'], missing, safe_ride=e['safe'], sample_size=len(e['consumes']), min_sample=rule['min_sample'])
                yield dict(result, object_type=2, area_id=e['area_id'], day_type=2 if cursor.weekday()>=5 else 1, hour_slot=cursor.hour, person_id=pid,
                           window_start=cursor, window_end=until, sample_size=len(e['consumes']), episode_key=e['key'], episodes=[e],
                           low=rule['low_threshold'], high=rule['high_threshold'], min_hit=rule['min_hit_cnt'])
        cursor = until


def save_chain(conn, clue_id, score_id, result):
    # Region chains branch by person; no arbitrary top-N truncation of underlying evidence.
    for e in result['episodes']:
        chain = insert('clue_chain', dict(clue_id=clue_id, person_id=e['person_id'], episode_key=e['key'], algorithm_version='continuous-v1', snapshot_at=result['window_end']), conn)
        nodes = []
        def node(kind, when, title, explanation, certainty='record', **refs):
            n = insert('chain_node', dict(chain_id=chain, node_type=kind, event_at=when, title=title, explanation=explanation, certainty=certainty, **refs), conn)
            nodes.append((when, n))
        context=one('SELECT score_id,window_end,total_score FROM risk_score WHERE object_type=1 AND area_id=%s AND window_end<=%s ORDER BY window_end DESC,score_id DESC LIMIT 1',(e['area_id'],e['first_at']),conn)
        if context:
            node('area_context',context['window_end'],'区域酒水活动背景',f"区域 {e['area_id']} 在消费前最近一个观察时段的指数为 {context['total_score']}；区域背景不等于个人行为认定",'association',score_id=context['score_id'])
        for c in e['consumes']:
            node('consume', c['consume_time'], '含酒水消费' if c['has_alcohol'] else '普通消费', f"人员 {e['person_id']}，场所 {c['place_id']}，金额 {c['amount']} 元", consume_id=c['consume_id'])
        if e['track']:
            t = e['track']
            node('track', t['pass_time'], '关联车辆驶出', '与该人员关联的车辆在消费后由同区域驶出；'+('有独立驾驶观察记录，车辆也可能借用' if e['confirmed'] else '仅车主归属，驾驶人待核实'), 'confirmed' if e['confirmed'] else 'association', track_id=t['track_id'])
        else:
            node('gap', result['window_end'], '车辆环节待核实', '截至研判时刻，未关联到符合时间和区域条件的驶出记录', 'missing')
        for o in e['orders']:
            node('order', o['completed_at'], '同次行程安全出行', '已完成的代驾或网约车订单，是风险判断的反例', 'counterexample', order_id=o['order_id'])
        node('score', result['window_end'], '风险指数快照', f"当前评分 {result['total_score']} / 100；风险提示不是行为认定", score_id=score_id)
        nodes.sort()
        for (_, left), (_, right) in zip(nodes, nodes[1:]):
            insert('chain_edge', dict(from_node=left, to_node=right, relation_type='time_sequence', reason='同人员同事件，按发生时间排序；关联不等于因果确认'), conn)


def run_batch(conn, batch_id, user=None):
    batch = one('SELECT * FROM judge_batch WHERE batch_id=%s FOR UPDATE', (batch_id,), conn)
    if not batch: raise ValueError('批次不存在')
    if batch['run_status'] not in (0, 3): raise ValueError('仅待执行或失败批次可执行')
    execute('UPDATE judge_batch SET run_status=1,started_at=NOW(),run_no=run_no+1,error_message=NULL WHERE batch_id=%s', (batch_id,), conn)
    started = time.perf_counter()
    count = clues = skipped = 0
    for r in calculate(conn, batch):
        count += 1
        old = one('SELECT s.score_id,c.clue_status,c.clue_id FROM risk_score s LEFT JOIN risk_clue c ON c.score_id=s.score_id WHERE s.batch_id=%s AND s.object_type=%s AND s.window_start=%s AND s.area_id=%s AND (s.person_id<=>%s)', (batch_id,r['object_type'],r['window_start'],r['area_id'],r['person_id']), conn)
        if old:
            # Never destroy snapshots already presented as a clue, including pending review.
            if old['clue_id'] or one('SELECT node_id FROM chain_node WHERE score_id=%s LIMIT 1',(old['score_id'],),conn):
                skipped += 1; continue
            execute('DELETE FROM risk_score_feature WHERE score_id=%s', (old['score_id'],), conn)
            execute('DELETE FROM risk_score WHERE score_id=%s', (old['score_id'],), conn)
        total = r['total_score']
        level = None if total is None else (1 if total<float(r['low']) else 2 if total<float(r['high']) else 3)
        hit = sum(f['is_hit'] for f in r['features'] if f['feature_id']!='F006')
        eligible = int(level is not None and level>=2 and hit>=r['min_hit'] and not r['blocked'])
        data = {k:r[k] for k in ['object_type','area_id','day_type','hour_slot','person_id','window_start','window_end','sample_size','episode_key','data_coverage','blocked']}
        score_id = insert('risk_score', dict(data,batch_id=batch_id,rule_id=batch['rule_id'],version_id=batch['version_id'],total_score=total,risk_level=level,is_clue=eligible,algorithm_version='continuous-v1',created_at=r['window_end']),conn)
        insert_many('risk_score_feature', [dict(f,score_id=score_id,evidence_json=json.dumps({'episode_keys':[e['key'] for e in r['episodes']]})) for f in r['features']], conn)
        # Total and level are finalized in MySQL from the stored contribution rows.
        execute('CALL sp_finalize_score(%s)', (score_id,), conn)
        if eligible:
            clue_id = f'CL{score_id:014d}'
            insert('risk_clue',dict(clue_id=clue_id,batch_id=batch_id,score_id=score_id,version_id=batch['version_id'],clue_status=0,assignee_id=None,create_at=r['window_end'],close_at=None),conn)
            save_chain(conn,clue_id,score_id,r)
            clues += 1
    duration = max(1,round((time.perf_counter()-started)*1000))
    actual = one('SELECT COUNT(*) n FROM risk_clue WHERE batch_id=%s',(batch_id,),conn)['n']
    execute('UPDATE judge_batch SET run_status=2,object_cnt=%s,clue_cnt=%s,duration_ms=%s WHERE batch_id=%s',(count,actual,duration,batch_id),conn)
    audit(user,'judge_batch',batch_id,f'真实研判完成：对象 {count}，新增线索 {clues}，保留快照 {skipped}',7,conn)
    return dict(batch_id=batch_id,run_status=2,object_cnt=count,clue_cnt=actual,skipped_cnt=skipped,duration_ms=duration)
