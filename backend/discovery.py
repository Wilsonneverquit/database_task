"""Read-only discovery of people and immutable evidence episodes."""
from flask import request
from .db import query
from .scoring import dt


CHAIN_ROWS = '''SELECT c.chain_id,c.clue_id,c.person_id,c.episode_key,c.snapshot_at,
 s.score_id,s.object_type,s.area_id,a.area_name,s.total_score,s.risk_level,s.window_start,
 rc.clue_status,b.created_at batch_created,
 (SELECT MIN(n.event_at) FROM chain_node n WHERE n.chain_id=c.chain_id AND n.node_type='consume') event_at,
 (SELECT COUNT(*) FROM chain_node n WHERE n.chain_id=c.chain_id) node_count
 FROM clue_chain c JOIN risk_clue rc ON rc.clue_id=c.clue_id
 JOIN risk_score s ON s.score_id=rc.score_id JOIN judge_batch b ON b.batch_id=s.batch_id
 LEFT JOIN area_info a ON a.area_id=s.area_id WHERE b.run_status=2'''


def register_discovery(app):
    from .app import roles, ok, page, fail, filters

    def time_filter(column):
        terms='';args=[]
        start=request.args.get('from');end=request.args.get('to')
        if start and end and dt(start)>=dt(end):fail('结束时间必须晚于开始时间')
        for value,op in [(start,'>='),(end,'<')]:
            if value:
                dt(value)
                terms+=f' AND {column}{op}%s';args.append(value)
        return terms,args

    def chain_scope():
        scope=request.args.get('scope','area')
        if scope not in ('area','person'):fail('浏览范围必须为 area 或 person')
        # Region mode shows branches belonging to regional alerts; person mode also
        # retains regional evidence involving that person, labeled by source type.
        return scope, ' AND object_type=1' if scope=='area' else ''

    @app.get('/api/person-risks')
    @roles('R_ANALYST','R_TEACHER')
    def person_risks():
        mode=request.args.get('mode','peak')
        if mode not in ('peak','latest'):fail('排序口径必须为 peak 或 latest')
        where,args=filters({'person_id':'s.person_id','area_id':'s.area_id'})
        time_where,time_args=time_filter('s.window_start');where+=time_where;args+=time_args
        keyword=request.args.get('q','').strip()
        if len(keyword)>64:fail('搜索关键词过长')
        if keyword:where+=' AND s.person_id LIKE %s';args.append('%'+keyword+'%')
        order='total_score DESC,window_start DESC' if mode=='peak' else 'window_start DESC,total_score DESC'
        sql='''WITH canonical AS (
 SELECT s.*,b.created_at batch_created,ROW_NUMBER() OVER(PARTITION BY s.person_id,s.window_start ORDER BY b.created_at DESC,b.batch_id DESC) time_rn
 FROM risk_score s JOIN judge_batch b USING(batch_id) WHERE s.object_type=2 AND b.run_status=2'''+where+'''), ranked AS (
 SELECT c.*,MAX(window_start) OVER(PARTITION BY person_id) latest_window,
 ROW_NUMBER() OVER(PARTITION BY person_id ORDER BY '''+order+''',score_id DESC) person_rn
 FROM canonical c WHERE time_rn=1)
 SELECT s.*,a.area_name FROM ranked s LEFT JOIN area_info a ON a.area_id=s.area_id WHERE person_rn=1'''
        if request.args.get('risk_level'):
            sql+=' AND risk_level=%s';args.append(request.args['risk_level'])
        result=page(sql+' ORDER BY total_score DESC,s.person_id',args)
        return ok(result|dict(mode=mode,scope_label='观察期峰值' if mode=='peak' else '每人最近时段'))

    @app.get('/api/evidence/subjects')
    @roles('R_ANALYST','R_TEACHER')
    def subjects():
        scope,where=chain_scope()
        time_where,args=time_filter('event_at');where+=time_where
        col='area_id' if scope=='area' else 'person_id'
        keyword=request.args.get('q','').strip()
        if len(keyword)>64:fail('搜索关键词过长')
        if keyword:
            where+=f' AND ({col} LIKE %s'+(' OR area_name LIKE %s)' if scope=='area' else ')')
            args.extend(['%'+keyword+'%']*(2 if scope=='area' else 1))
        sql=f'''WITH candidates AS ({CHAIN_ROWS})
 SELECT {col} subject_id,{('MAX(area_name)' if scope=='area' else 'person_id')} label,
 COUNT(DISTINCT episode_key) event_count,MAX(total_score) peak_score,MAX(event_at) latest_event
 FROM candidates WHERE event_at IS NOT NULL'''+where+f' GROUP BY {col} ORDER BY peak_score DESC,latest_event DESC,{col}'
        return ok(page(sql,args)|dict(scope=scope))

    @app.get('/api/evidence/events')
    @roles('R_ANALYST','R_TEACHER')
    def events():
        scope,where=chain_scope()
        key='area_id' if scope=='area' else 'person_id'
        value=request.args.get(key)
        if not value:fail('请选择区域或人员')
        where+=f' AND {key}=%s';args=[value]
        time_where,time_args=time_filter('event_at');where+=time_where;args+=time_args
        sql='''WITH candidates AS ('''+CHAIN_ROWS+'''), ranked AS (
 SELECT c.*,COUNT(*) OVER(PARTITION BY person_id,episode_key) snapshot_count,
 MAX(total_score) OVER(PARTITION BY person_id,episode_key) episode_peak_score,
 ROW_NUMBER() OVER(PARTITION BY person_id,episode_key ORDER BY snapshot_at DESC,object_type DESC,batch_created DESC,chain_id DESC) event_rn
 FROM candidates c WHERE event_at IS NOT NULL'''+where+''')
 SELECT * FROM ranked WHERE event_rn=1 ORDER BY event_at DESC,person_id,episode_key'''
        return ok(page(sql,args)|dict(scope=scope,note='同一消费事件合并重复研判快照，列表展示最新快照；分数属于对应来源线索。'))
