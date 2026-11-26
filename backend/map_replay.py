"""Read-only spatial replay of stored evidence snapshots; no inferred GPS tracks."""
from flask import request
from .db import query, one
from .scoring import dt


def locate_node(node, source, places):
    """Only source-backed event locations are mapped. Context/gaps never move a marker."""
    kind = node['node_type']
    if kind == 'consume' and source:
        place = places.get(source['place_id'])
        return (place['area_id'], place['place_name']) if place else (None, '场所位置缺失')
    if kind == 'track' and source:
        return source['area_id'], source['gate_id'] + (' · 驶入' if source['direction'] == 1 else ' · 驶出')
    if kind == 'order' and source:
        return source.get('end_area_id'), '出行完成 · 终点区域'
    return None, '信息节点，无地理落点'


def register_map_replay(app):
    from .app import roles, ok, page, fail

    @app.get('/api/map-replay/events')
    @roles('R_ANALYST', 'R_TEACHER')
    def map_replay_events():
        where = ''; args = []
        start = request.args.get('from'); end = request.args.get('to')
        if start and end and dt(start) >= dt(end): fail('结束时间必须晚于开始时间')
        for value, op in [(start, '>='), (end, '<')]:
            if value:
                dt(value); where += f' AND event_at {op} %s'; args.append(value)
        for key in ('area_id', 'person_id'):
            value = request.args.get(key)
            if value:
                if len(value) > 64: fail('筛选条件过长')
                where += f' AND {key}=%s'; args.append(value)
        as_of = request.args.get('as_of')
        if as_of:
            dt(as_of); where += ' AND snapshot_at<=%s'; args.append(as_of)
        # Resolve location from the immutable consume reference, including person clues.
        sql = '''WITH first_consume AS (
 SELECT n.chain_id,n.event_at,n.consume_id,c.place_id,p.area_id,p.place_name,
 ROW_NUMBER() OVER(PARTITION BY n.chain_id ORDER BY n.event_at,n.node_id) source_rn
 FROM chain_node n JOIN consume_record c USING(consume_id) JOIN place_info p USING(place_id)
 WHERE n.node_type='consume'), candidates AS (
 SELECT c.chain_id,c.clue_id,c.person_id,c.episode_key,c.snapshot_at,s.score_id,s.object_type,
 s.total_score,s.risk_level,rc.clue_status,b.created_at batch_created,
 f.event_at,f.consume_id,f.place_id,f.place_name,f.area_id,a.area_name
 FROM clue_chain c JOIN risk_clue rc USING(clue_id) JOIN risk_score s ON s.score_id=rc.score_id
 JOIN judge_batch b ON b.batch_id=s.batch_id JOIN first_consume f ON f.chain_id=c.chain_id AND f.source_rn=1
 JOIN area_info a ON a.area_id=f.area_id WHERE b.run_status=2), ranked AS (
 SELECT c.*,COUNT(*) OVER(PARTITION BY person_id,episode_key) snapshot_count,
 ROW_NUMBER() OVER(PARTITION BY person_id,episode_key ORDER BY snapshot_at DESC,object_type DESC,batch_created DESC,chain_id DESC) event_rn
 FROM candidates c WHERE 1=1''' + where + ''')
 SELECT * FROM ranked WHERE event_rn=1 ORDER BY event_at,person_id,episode_key,chain_id'''
        return ok(page(sql, args) | dict(location_precision='area', note='按事件发生时间回放；跨事件连线仅表示浏览顺序。'))

    @app.get('/api/map-replay/chains/<int:chain_id>')
    @roles('R_ANALYST', 'R_TEACHER')
    def map_replay_chain(chain_id):
        chain = one('''SELECT c.*,s.total_score,s.risk_level,s.score_id,s.object_type,rc.clue_status
 FROM clue_chain c JOIN risk_clue rc USING(clue_id) JOIN risk_score s ON s.score_id=rc.score_id
 WHERE c.chain_id=%s''', (chain_id,))
        if not chain: fail('事件链不存在', 404)
        areas = {a['area_id']: a for a in query('SELECT area_id,area_name,lng,lat FROM area_info')}
        places = {p['place_id']: p for p in query('SELECT place_id,place_name,area_id FROM place_info')}
        nodes = query('SELECT * FROM chain_node WHERE chain_id=%s ORDER BY event_at,node_id', (chain_id,))
        result = []
        for node in nodes:
            source = None; source_table = None
            for key, table in [('consume_id', 'consume_record'), ('track_id', 'vehicle_track'), ('order_id', 'taxi_order'), ('score_id', 'risk_score')]:
                if node.get(key):
                    source = one(f'SELECT * FROM {table} WHERE {key}=%s', (node[key],))
                    source_table = table; break
            area_id, label = locate_node(node, source, places)
            base = dict(node, source_record=source, source_table=source_table, location_precision='area')
            if source and source_table in ('consume_record', 'vehicle_track', 'taxi_order') and source.get('recorded_at') and source['recorded_at'] >= chain['snapshot_at']:
                # Never expose a source recorded after the frozen evidence snapshot.
                continue
            if node['node_type'] == 'order' and source:
                if source.get('order_time') and source['order_time'] <= node['event_at']:
                    result.append(base | dict(event_id=f"{node['node_id']}:start", event_at=source['order_time'], title='出行起点（订单记录）', area_id=source.get('start_area_id'), location_label='订单起点区域'))
            result.append(base | dict(event_id=str(node['node_id']), area_id=area_id, location_label=label))
        result.sort(key=lambda n: (n['event_at'], n['node_id'], 0 if n['event_id'].endswith(':start') else 1))
        for node in result:
            area = areas.get(node['area_id'])
            node['area_name'] = area['area_name'] if area else None
            node['lng'] = area['lng'] if area else None; node['lat'] = area['lat'] if area else None
            node['located'] = bool(area)
        feedbacks = query('SELECT feedback_id,check_time,check_result,check_remark FROM clue_feedback WHERE clue_id=%s ORDER BY check_time,feedback_id', (chain['clue_id'],))
        return ok(dict(chain=chain, nodes=result, feedbacks=feedbacks, note='区域级定位；时间先后与车辆关联不等于确认行驶轨迹。'))
