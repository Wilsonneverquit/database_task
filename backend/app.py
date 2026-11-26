import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, g, send_from_directory
import pymysql
from werkzeug.security import check_password_hash
from werkzeug.exceptions import HTTPException
from .db import JSONProvider, ROOT, get_db, query, one, execute, insert, transaction, audit, now
from .presentation import describe_score, quality_payload


class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def fail(message, status=400):
    raise APIError(message, status)


def ok(data=None, status=200):
    return jsonify(code=0,message='ok',data=data),status


def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not set(allowed).intersection(g.roles):fail('当前角色无权执行此操作',403)
            return fn(*args,**kwargs)
        return wrapped
    return decorator


def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict):fail('请求体必须为 JSON 对象')
    return value


def page(sql,args=(),count_sql=None):
    try:
        p=max(1,int(request.args.get('page',1)));size=max(1,min(200,int(request.args.get('size',20))))
    except ValueError:fail('分页参数必须为整数')
    total=one(count_sql or f'SELECT COUNT(*) n FROM ({sql}) counted',args)['n']
    rows=query(sql+' LIMIT %s OFFSET %s',(*args,size,(p-1)*size))
    return dict(list=rows,total=total,page=p,size=size)


def filters(mapping):
    terms=[];args=[]
    for param,column in mapping.items():
        value=request.args.get(param)
        if value not in (None,''):terms.append(column+'=%s');args.append(value)
    return (' AND '+' AND '.join(terms)) if terms else '',args


def decode(row,*fields):
    if row:
        for field in fields:
            if isinstance(row.get(field),str):row[field]=json.loads(row[field])
    return row


def create_app():
    app=Flask(__name__,static_folder=None)
    app.json=JSONProvider(app)
    app.config['MAX_CONTENT_LENGTH']=8*1024*1024
    default_source = os.getenv('DATA_SOURCE', 'demo')
    if default_source not in ('demo', 'real'):
        raise ValueError('DATA_SOURCE must be demo or real')

    @app.before_request
    def route_database():
        if request.path.startswith('/api/') and request.method != 'OPTIONS':
            source = request.headers.get('X-Data-Source', default_source)
            if source not in ('demo', 'real'):
                fail('数据源必须为 demo 或 real')
            g.data_source = source

    @app.before_request
    def authenticate():
        if not request.path.startswith('/api/') or request.method=='OPTIONS':return
        if request.path in ('/api/login','/api/auth/sessions') and request.method=='POST':return
        token=request.headers.get('Authorization','').removeprefix('Bearer ')
        g.user=one('SELECT u.user_id,u.username,u.real_name FROM app_session s JOIN sys_user u ON u.user_id=s.user_id WHERE s.token_hash=%s AND s.expires_at>NOW() AND u.status=1',(hashlib.sha256(token.encode()).hexdigest(),)) if token else None
        if not g.user:fail('未登录或登录已过期',401)
        g.roles=[r['role_id'] for r in query('SELECT ur.role_id FROM sys_user_role ur JOIN sys_role r ON r.role_id=ur.role_id WHERE ur.user_id=%s AND r.status=1',(g.user['user_id'],))]
        execute('SET @app_user_id=%s',(g.user['user_id'],))

    @app.after_request
    def headers(response):
        origin=request.headers.get('Origin')
        if origin in ('http://127.0.0.1:5173','http://localhost:5173'):
            response.headers['Access-Control-Allow-Origin']=origin
            response.headers['Vary']='Origin'
        response.headers['Access-Control-Allow-Headers']='Content-Type,Authorization,X-Data-Source'
        if 'data_source' in g:
            response.headers['X-Data-Source']=g.data_source
            response.headers['Access-Control-Expose-Headers']='X-Data-Source'
            response.vary.add('X-Data-Source')
        response.headers['Access-Control-Allow-Methods']='GET,POST,PATCH,DELETE,OPTIONS'
        response.headers['Cache-Control']='no-store' if request.path.startswith('/api/') else 'no-cache'
        return response

    @app.teardown_appcontext
    def close_db(error):
        conn=g.pop('db',None)
        if conn:
            conn.rollback();conn.close()

    @app.errorhandler(APIError)
    def api_error(e):return jsonify(code=e.status*10,message=e.message,data=None),e.status
    @app.errorhandler(pymysql.IntegrityError)
    def integrity(e):
        get_db().rollback()
        return jsonify(code=4090,message='数据违反唯一键、外键或业务约束；被引用记录请停用或更正',data=None),409
    @app.errorhandler(pymysql.OperationalError)
    def unavailable(e):
        if e.args[0] in (3819,1366,1292,1264,1406):
            return jsonify(code=4000,message='数据类型、时间、数值范围或 CHECK 业务约束不合法',data=None),400
        if e.args[0] in (1205,1213):
            return jsonify(code=4090,message='记录正在被其他操作处理，请稍后重试',data=None),409
        app.logger.error('Database operation failed: %s',e)
        return jsonify(code=5030,message='数据库连接或操作失败，请检查本机 MySQL 与后端配置',data=None),503
    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    def invalid(e):return jsonify(code=4000,message=str(e),data=None),400
    @app.errorhandler(Exception)
    def unexpected(e):
        if isinstance(e,HTTPException):return jsonify(code=e.code*10,message=e.description,data=None),e.code
        app.logger.exception('Unhandled request error')
        return jsonify(code=5000,message='服务器内部错误，请查看后端日志',data=None),500

    @app.route('/api/<path:rest>',methods=['OPTIONS'])
    def options(rest):return '',204

    @app.post('/api/login')
    @app.post('/api/auth/sessions')
    def login():
        b=body();u=one('SELECT * FROM sys_user WHERE username=%s',(b.get('username'),))
        if not u or not check_password_hash(u['password_hash'],str(b.get('password',''))):fail('用户名或口令错误',401)
        if u['status']!=1:fail('账号已停用或锁定',403)
        token=secrets.token_urlsafe(32)
        with transaction():
            insert('app_session',dict(token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=u['user_id'],expires_at=now()+timedelta(hours=int(os.getenv('SESSION_HOURS','8')))),get_db())
            audit(u['user_id'],'sys_user',u['user_id'],'用户登录',1)
        r=[x['role_id'] for x in query('SELECT role_id FROM sys_user_role WHERE user_id=%s',(u['user_id'],))]
        return ok(dict(token=token,user={k:u[k] for k in ('user_id','username','real_name')}|{'roles':r}))

    @app.delete('/api/auth/sessions/current')
    def logout():
        with transaction():execute('DELETE FROM app_session WHERE token_hash=%s',(hashlib.sha256(request.headers.get('Authorization','').removeprefix('Bearer ').encode()).hexdigest(),))
        return ok()

    @app.get('/api/dicts')
    def dicts():
        return ok(dict(areas=query('SELECT area_id,area_name,area_type FROM area_info'),rules=query('SELECT rule_id,rule_name,version_id,judge_object,low_threshold,high_threshold FROM judge_rule WHERE status=1'),features=query('SELECT feature_id,feature_name FROM feature_def'),history_cutoff=one("SELECT param_value FROM param_config WHERE param_key='history_cutoff'")['param_value'],dataset_end=one("SELECT param_value FROM param_config WHERE param_key='dataset_end'")['param_value']))

    @app.get('/api/overview')
    def overview():
        counts=one('SELECT COUNT(*) clue_total,COALESCE(SUM(clue_status=0),0) clue_open,COALESCE(SUM(clue_status=1),0) clue_checking,COALESCE(SUM(clue_status=2),0) clue_confirmed,COALESCE(SUM(clue_status=3),0) clue_excluded FROM risk_clue')
        counts['latest_batch']=one('SELECT * FROM judge_batch ORDER BY data_end DESC,batch_id LIMIT 1')
        counts['high_risk_cnt']=one('SELECT COUNT(*) n FROM risk_score WHERE risk_level=3 AND object_type=1')['n']
        counts['eval']=evaluation_summary() if 'R_TEACHER' in g.roles else None
        return ok(counts)

    @app.get('/api/region-risk')
    @roles('R_ANALYST','R_TEACHER')
    def region_risk():
        where,args=filters({'batch_id':'batch_id','area_id':'area_id','risk_level':'risk_level','window_start':'window_start'})
        result=page('SELECT * FROM v_region_risk WHERE 1=1'+where+' ORDER BY total_score DESC,score_id',args)
        result['list']=[describe_score(r) for r in result['list']]
        return ok(result)

    @app.get('/api/scores/<int:sid>/features')
    @roles('R_ANALYST','R_TEACHER')
    def score_features(sid):return ok(score_detail(sid))

    @app.get('/api/clues')
    @roles('R_ANALYST','R_TEACHER')
    def clues():
        where,args=filters({'status':'clue_status','area_id':'area_id','risk_level':'risk_level','person_id':'object_id'})
        return ok(page('SELECT * FROM v_clue_list WHERE 1=1'+where+(' ORDER BY create_at DESC' if request.args.get('order')=='latest' else ' ORDER BY total_score DESC,create_at DESC'),args))

    @app.get('/api/clues/<cid>')
    @roles('R_ANALYST','R_TEACHER')
    def clue(cid):
        c=one('SELECT c.*,u.real_name assignee_name FROM risk_clue c LEFT JOIN sys_user u ON u.user_id=c.assignee_id WHERE clue_id=%s',(cid,))
        if not c:fail('线索不存在',404)
        data=score_detail(c['score_id']);data['clue']=c
        data['feedbacks']=query('SELECT f.*,u.real_name checker_name FROM clue_feedback f JOIN sys_user u ON u.user_id=f.checker_id WHERE clue_id=%s ORDER BY check_time',(cid,))
        for f in data['feedbacks']:f['wrong_features']=[r['feature_id'] for r in query('SELECT feature_id FROM clue_feedback_feature WHERE feedback_id=%s AND is_wrong=1',(f['feedback_id'],))]
        return ok(data)

    @app.patch('/api/clues/<cid>/status')
    @roles('R_ANALYST')
    def clue_status(cid):
        with transaction():
            c=one('SELECT * FROM risk_clue WHERE clue_id=%s FOR UPDATE',(cid,))
            if not c:fail('线索不存在',404)
            if c['clue_status']!=0 or body().get('status')!=1:fail('此接口只用于开始核查；结案请提交核查反馈',409)
            execute('UPDATE risk_clue SET clue_status=1,assignee_id=%s WHERE clue_id=%s',(g.user['user_id'],cid))
        return ok(dict(clue_id=cid,clue_status=1))

    @app.post('/api/clues/<cid>/feedback')
    @roles('R_ANALYST')
    def feedback(cid):
        b=body();result=int(b.get('check_result',0));method=int(b.get('check_method',0));remark=str(b.get('check_remark','')).strip()
        if result not in (1,2,3) or method not in (1,2,3) or not remark or len(remark)>500:fail('请填写有效的核查结论、方式及 1–500 字说明')
        with transaction():
            c=one('SELECT * FROM risk_clue WHERE clue_id=%s FOR UPDATE',(cid,))
            if not c:fail('线索不存在',404)
            if c['clue_status'] in (2,3):fail('线索已经关闭',409)
            wrong=b.get('wrong_feature_ids',[])
            if not isinstance(wrong,list) or any(not isinstance(x,str) for x in wrong):fail('否定特征必须为编号列表')
            allowed={r['feature_id'] for r in query('SELECT feature_id FROM risk_score_feature WHERE score_id=%s AND is_hit=1',(c['score_id'],))}
            if set(wrong)-allowed:fail('只能否定该线索实际命中的特征')
            fid=insert('clue_feedback',dict(clue_id=cid,check_result=result,check_method=method,check_remark=remark,checker_id=g.user['user_id'],check_time=now(),weight_applied=0),get_db())
            for f in set(wrong):insert('clue_feedback_feature',dict(feedback_id=fid,feature_id=f,is_wrong=1),get_db())
            audit(g.user['user_id'],'clue_feedback',fid,'提交核查反馈',3)
        return ok(dict(feedback_id=fid,clue_status=2 if result==1 else 3 if result==2 else c['clue_status']),201)

    @app.get('/api/clues/<cid>/chain')
    @roles('R_ANALYST','R_TEACHER')
    def chain(cid):
        context=one('SELECT c.clue_id,s.object_type,s.area_id,s.person_id,s.window_start,a.area_name FROM risk_clue c JOIN risk_score s USING(score_id) LEFT JOIN area_info a ON a.area_id=s.area_id WHERE c.clue_id=%s',(cid,))
        if not context:fail('线索不存在',404)
        rows=query('SELECT * FROM clue_chain WHERE clue_id=%s ORDER BY chain_id',(cid,))
        for r in rows:
            r['nodes']=query('SELECT * FROM chain_node WHERE chain_id=%s ORDER BY event_at,node_id',(r['chain_id'],))
            for node in r['nodes']:
                if node['track_id'] and node['certainty']=='confirmed':
                    node['driver_record']=one('SELECT * FROM driver_evidence WHERE track_id=%s AND person_id=%s AND recorded_at<%s',(node['track_id'],r['person_id'],r['snapshot_at']))
                for column,table in [('consume_id','consume_record'),('order_id','taxi_order'),('track_id','vehicle_track'),('score_id','risk_score')]:
                    if node.get(column):
                        node['source_record']=one(f'SELECT * FROM {table} WHERE {column}=%s',(node[column],))
                        break
            r['edges']=query('SELECT e.* FROM chain_edge e JOIN chain_node n ON n.node_id=e.from_node WHERE n.chain_id=%s',(r['chain_id'],))
        feedbacks=query('SELECT feedback_id,check_time,check_result,check_remark FROM clue_feedback WHERE clue_id=%s ORDER BY check_time',(cid,))
        return ok(dict(chains=rows,context=context,feedbacks=feedbacks,note='关联车辆不等于确认驾驶人；链路快照仅包含研判时已知记录'))

    @app.get('/api/batches')
    @roles('R_ANALYST','R_FEATURE','R_ADMIN','R_TEACHER')
    def batches():
        where,args=filters({'run_status':'b.run_status'})
        return ok(page('SELECT b.*,r.rule_name,a.area_name,u.real_name operator_name FROM judge_batch b JOIN judge_rule r ON r.rule_id=b.rule_id LEFT JOIN area_info a ON a.area_id=b.area_id LEFT JOIN sys_user u ON u.user_id=b.operator_id WHERE 1=1'+where+' ORDER BY b.data_end DESC,b.batch_id DESC',args))

    @app.post('/api/batches')
    @roles('R_FEATURE','R_ADMIN')
    def create_batch():
        from .scoring import dt
        b=body();rule=one('SELECT * FROM judge_rule WHERE rule_id=%s AND status=1',(b.get('rule_id'),))
        if not rule:fail('规则不存在或已停用')
        start,end=dt(b.get('data_start')),dt(b.get('data_end'))
        cutoff=dt(one("SELECT param_value FROM param_config WHERE param_key='history_cutoff'")['param_value'])
        if not cutoff<=start<end or end-start>timedelta(days=7) or start.minute or start.second or end.minute or end.second:fail('请选择观察段内、整点对齐且不超过七天的数据窗')
        version=b.get('version_id') or rule['version_id']
        if version!=rule['version_id']:fail('批次版本必须与规则冻结版本一致')
        bid=b.get('batch_id') or 'B'+secrets.token_hex(8)
        if not isinstance(bid,str) or len(bid)>24:fail('批次编号过长')
        with transaction():
            insert('judge_batch',dict(batch_id=bid,rule_id=rule['rule_id'],version_id=version,judge_object=rule['judge_object'],data_start=start,data_end=end,area_id=b.get('area_id') or None,operator_id=g.user['user_id']),get_db())
            audit(g.user['user_id'],'judge_batch',bid,'创建研判批次',3)
        return ok(dict(batch_id=bid,run_status=0),201)

    @app.post('/api/batches/<bid>/run')
    @app.post('/api/batches/<bid>/runs')
    @roles('R_FEATURE','R_ADMIN')
    def run(bid):
        from .engine import run_batch
        if not one('SELECT batch_id FROM judge_batch WHERE batch_id=%s',(bid,)):fail('批次不存在',404)
        try:
            with transaction():result=run_batch(get_db(),bid,g.user['user_id'])
        except ValueError as e:
            with transaction():
                execute('UPDATE judge_batch SET run_status=3,error_message=%s WHERE batch_id=%s AND run_status IN (0,3)',(str(e)[:500],bid))
            fail(str(e),409)
        return ok(result,201)

    @app.get('/api/features')
    @roles('R_FEATURE','R_TEACHER')
    def features():
        where,args=filters({'status':'f.status','cat':'f.feature_cat'})
        current=one('SELECT version_id FROM feature_version WHERE publish_status=1')
        vid=current['version_id'] if current else None
        rows=query('SELECT f.*,w.p1,w.p0,w.lift,w.weight,w.is_valid FROM feature_def f LEFT JOIN feature_weight w ON w.feature_id=f.feature_id AND w.version_id=%s WHERE 1=1'+where+' ORDER BY f.feature_id',[vid,*args])
        return ok(dict(version_id=vid,list=rows))

    @app.get('/api/features/<fid>')
    @roles('R_FEATURE','R_TEACHER')
    def feature(fid):
        f=one('SELECT * FROM feature_def WHERE feature_id=%s',(fid,))
        if not f:fail('特征不存在',404)
        return ok(dict(feature=f,weights=query('SELECT w.*,v.version_no,v.publish_status FROM feature_weight w JOIN feature_version v ON v.version_id=w.version_id WHERE feature_id=%s',(fid,)),versions=query('SELECT version_id,version_no,publish_status FROM feature_version'),rules=query('SELECT rf.*,r.rule_name FROM rule_feature rf JOIN judge_rule r ON r.rule_id=rf.rule_id WHERE feature_id=%s',(fid,)),negations=query('SELECT f.* FROM clue_feedback_feature x JOIN clue_feedback f ON f.feedback_id=x.feedback_id WHERE x.feature_id=%s AND x.is_wrong=1',(fid,))))

    @app.patch('/api/features/<fid>/status')
    @roles('R_FEATURE')
    def feature_status(fid):
        # Published configurations are immutable. A disable affects the next draft only.
        fail('请在草稿规则中调整因子；已发布评分版本保持冻结',409)

    @app.get('/api/versions')
    @roles('R_FEATURE','R_ADMIN','R_TEACHER')
    def versions():
        return ok(query('SELECT v.version_id,v.risk_type,v.version_no,v.publish_status,v.based_case_cnt,v.based_ctrl_cnt,v.calc_at,v.remark,v.created_at,v.algorithm_version,u.real_name published_by_name,(SELECT COUNT(*) FROM feature_weight w WHERE w.version_id=v.version_id) weight_cnt FROM feature_version v LEFT JOIN sys_user u ON u.user_id=v.published_by ORDER BY v.created_at DESC'))

    @app.patch('/api/versions/<vid>/publish')
    @roles('R_FEATURE')
    def publish(vid):
        state=int(body().get('publish_status',-1))
        if state not in (1,2):fail('发布状态必须为发布或归档')
        with transaction():
            v=one('SELECT * FROM feature_version WHERE version_id=%s FOR UPDATE',(vid,))
            if not v:fail('版本不存在',404)
            if state==1:
                if not v['baseline_json']:fail('请先计算草稿版本基线')
                execute('UPDATE feature_version SET publish_status=2 WHERE risk_type=%s AND publish_status=1',(v['risk_type'],))
            execute('UPDATE feature_version SET publish_status=%s,published_by=%s WHERE version_id=%s',(state,g.user['user_id'],vid))
            audit(g.user['user_id'],'feature_version',vid,'发布版本' if state==1 else '归档版本')
        return ok(dict(version_id=vid,publish_status=state))

    @app.post('/api/weights/recalc')
    @roles('R_FEATURE')
    def recalc():
        from .learning import recalculate
        with transaction():result=recalculate(get_db(),body().get('version_id'),g.user['user_id'])
        return ok(result)

    @app.get('/api/eval/confusion')
    @roles('R_TEACHER')
    def confusion():return ok(evaluation_summary())

    @app.get('/api/eval/samples')
    @roles('R_TEACHER')
    def eval_samples():
        sql,args=evaluation_sql()
        count_rows=query(sql,args)
        counts={k:sum(r['result']==k for r in count_rows) for k in ('tp','fp','fn','tn')}
        result=request.args.get('result')
        if result and result not in (*counts,'missing'):fail('评估结果筛选无效')
        if result:sql='SELECT * FROM ('+sql+') evaluated WHERE result=%s';args.append(result)
        data=page(sql,args)
        return ok(data|dict(sample_total=len(count_rows),joined_total=len(count_rows),result_counts=counts,missing_count=sum(r['result']=='missing' for r in count_rows)))

    @app.get('/api/eval/labels')
    @roles('R_TEACHER')
    def labels():return ok(query("SELECT sample_type,CASE sample_type WHEN 1 THEN '正样本' WHEN 2 THEN '干扰样本' ELSE '对照样本' END name,COUNT(*) cnt FROM eval_label GROUP BY sample_type"))

    @app.get('/api/audit')
    @roles('R_ADMIN','R_TEACHER')
    def logs():
        where,args=filters({'user_id':'l.user_id','op_type':'l.op_type'})
        for key,op in [('from','>='),('to','<')]:
            if request.args.get(key):where+=f' AND l.op_time {op} %s';args.append(request.args[key])
        return ok(page('SELECT l.*,u.real_name user_name FROM audit_log l LEFT JOIN sys_user u ON u.user_id=l.user_id WHERE 1=1'+where+' ORDER BY l.op_time DESC,l.log_id DESC',args))

    @app.get('/api/users')
    @roles('R_ADMIN','R_TEACHER')
    def users():
        rows=query('SELECT user_id,username,real_name,status FROM sys_user')
        for u in rows:u['roles']=[r['role_id'] for r in query('SELECT role_id FROM sys_user_role WHERE user_id=%s',(u['user_id'],))]
        return ok(rows)

    @app.get('/api/params')
    @roles('R_ADMIN')
    def params():return ok(query('SELECT * FROM param_config ORDER BY param_key'))

    @app.patch('/api/params/<key>')
    @roles('R_ADMIN')
    def param(key):
        if key in ('history_cutoff','dataset_start','dataset_end','dataset_seed','data_provenance','dataset_summary'):fail('数据集边界为版本基线的一部分；请通过新数据集迁移修改',409)
        value=str(body().get('param_value',''))
        if len(value)>200:fail('参数值过长')
        with transaction():
            _,n=execute('UPDATE param_config SET param_value=%s WHERE param_key=%s',(value,key))
            if not n:fail('参数不存在或值未改变',404)
            audit(g.user['user_id'],'param_config',key,'修改参数')
        return ok(one('SELECT * FROM param_config WHERE param_key=%s',(key,)))

    @app.get('/api/cases')
    @roles('R_FEATURE','R_TEACHER')
    def cases():
        where,args=filters({'area_id':'c.area_id'})
        for key,op in [('from','>='),('to','<')]:
            if request.args.get(key):where+=f' AND c.occur_time {op} %s';args.append(request.args[key])
        return ok(page('SELECT c.*,a.area_name FROM v_case_history c JOIN area_info a ON a.area_id=c.area_id WHERE 1=1'+where+' ORDER BY occur_time DESC',args)|dict(history_cutoff=one("SELECT param_value FROM param_config WHERE param_key='history_cutoff'")['param_value'],case_info_total=one('SELECT COUNT(*) n FROM case_info')['n']))

    @app.get('/api/health')
    def health():
        return ok(dict(tables=one('SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type=%s',('BASE TABLE',))['n'],rows=sum(r['n'] for r in query('SELECT COUNT(*) n FROM consume_record UNION ALL SELECT COUNT(*) FROM taxi_order UNION ALL SELECT COUNT(*) FROM vehicle_track')),orphan_person=one('SELECT COUNT(*) n FROM consume_record c LEFT JOIN person_info p ON p.person_id=c.person_id WHERE p.person_id IS NULL')['n'],orphan_area=one('SELECT COUNT(*) n FROM place_info p LEFT JOIN area_info a USING(area_id) WHERE a.area_id IS NULL')['n'],case_after_cutoff=one("SELECT COUNT(*) n FROM case_info WHERE occur_time>=(SELECT CAST(param_value AS DATETIME) FROM param_config WHERE param_key='history_cutoff')")['n'],feature_bad_match_src=one("SELECT COUNT(*) n FROM feature_def WHERE match_src='case_info'")['n'],storage='mysql',score_scale=100))

    @app.get('/api/data-quality')
    @roles('R_DATA','R_ADMIN','R_FEATURE','R_TEACHER')
    def quality():
        rows=query('SELECT * FROM data_quality_report ORDER BY report_id DESC')
        for row in rows:
            decode(row,'report_json')
            row['report_json']=quality_payload(row['report_json'])
        return ok(rows)

    @app.get('/api/risk-map')
    @roles('R_ANALYST','R_TEACHER')
    def risk_map():
        # Canonical latest successful score per area/hour, not per-day peak mixing batches.
        sql='''WITH ranked AS (SELECT s.*,ROW_NUMBER() OVER(PARTITION BY area_id,window_start ORDER BY b.created_at DESC,b.batch_id DESC) rn FROM v_region_risk s JOIN judge_batch b USING(batch_id) WHERE b.run_status=2) SELECT * FROM ranked WHERE rn=1 ORDER BY window_start,area_id'''
        aggregation=request.args.get('aggregation','hour')
        if aggregation not in ('hour','day_peak'):fail('聚合方式必须为 hour 或 day_peak')
        rows=[describe_score(r) for r in query(sql)];groups={}
        for r in rows:
            key=str(r['window_start']) if aggregation=='hour' else str(r['window_start'].date())
            bucket=groups.setdefault(key,{})
            current=bucket.get(r['area_id'])
            if current is None or (r['total_score'] is not None and (current['total_score'] is None or r['total_score']>current['total_score'])):bucket[r['area_id']]=r
        return ok(dict(areas=query("SELECT a.*,CASE area_type WHEN 1 THEN '城市道路' WHEN 2 THEN '商圈' WHEN 3 THEN '乡镇' ELSE '高速出入口' END area_type_name FROM area_info a"),dates=list(groups),risk=[dict(date=k,areas=list(v.values())) for k,v in groups.items()],aggregation=aggregation,score_scale=100))

    @app.get('/api/risk-trends')
    @roles('R_ANALYST','R_TEACHER')
    def trends():
        where,args=filters({'area_id':'s.area_id','person_id':'s.person_id','version_id':'s.version_id'})
        obj=2 if request.args.get('person_id') else 1
        return ok(query('SELECT window_start,area_id,person_id,total_score,risk_level,score_id FROM (SELECT s.*,ROW_NUMBER() OVER(PARTITION BY object_type,object_id,window_start ORDER BY b.created_at DESC,b.batch_id DESC) rn FROM risk_score s JOIN judge_batch b USING(batch_id) WHERE b.run_status=2 AND s.object_type=%s'+where+') ranked WHERE rn=1 ORDER BY window_start LIMIT 2000',[obj,*args]))

    @app.get('/api/persons/<pid>/timeline')
    @roles('R_ANALYST','R_TEACHER')
    def person_timeline(pid):
        if not one('SELECT person_id FROM person_info WHERE person_id=%s',(pid,)):fail('人员不存在',404)
        where='';args=[pid]
        for key,op in [('from','>='),('to','<')]:
            if request.args.get(key):where+=f' AND event_at {op} %s';args.append(request.args[key])
        return ok(page('''SELECT * FROM (
SELECT c.person_id,'consume' kind,c.consume_id source_id,c.consume_time event_at,CONCAT(p.place_name,' · ',IF(c.has_alcohol=1,'含酒水','普通消费'),' · ',c.amount,' 元') description,'record' certainty FROM consume_record c JOIN place_info p USING(place_id) WHERE c.is_active=1
UNION ALL SELECT person_id,'order',order_id,order_time,CONCAT(IF(order_type=2,'代驾','网约车'),' · ',CASE order_status WHEN 1 THEN '已完成' WHEN 2 THEN '已取消' ELSE '进行中' END),'record' FROM taxi_order WHERE is_active=1
UNION ALL SELECT v.owner_person_id,'track',t.track_id,t.pass_time,CONCAT(t.vehicle_id,' · ',t.area_id,' · ',IF(t.direction=2,'驶出','驶入'),'；车辆归属关联，驾驶人待核实'),'association' FROM vehicle_track t JOIN vehicle_owner v USING(vehicle_id) WHERE t.is_active=1
UNION ALL SELECT d.person_id,'driver_observation',t.track_id,t.pass_time,CONCAT(t.vehicle_id,' · ',t.area_id,'；独立驾驶观察，车辆为借用'),'confirmed' FROM driver_evidence d JOIN vehicle_track t USING(track_id) JOIN vehicle_owner v USING(vehicle_id) WHERE d.person_id<>v.owner_person_id AND t.is_active=1
) events WHERE person_id=%s'''+where+' ORDER BY event_at DESC,kind,source_id',args))

    from .resources import register_resources
    register_resources(app)
    from .discovery import register_discovery
    register_discovery(app)

    @app.get('/data-source-config.js')
    def client_config():
        return app.response_class('window.RISK_DEFAULT_SOURCE='+json.dumps(default_source)+';',mimetype='application/javascript')

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        if path.startswith('api/'):fail('接口不存在',404)
        dist=ROOT/'frontend'/'dist'
        if not (dist/'index.html').exists():return 'Frontend: npm run dev or npm run build in frontend/',200
        target=(dist/path).resolve()
        return send_from_directory(dist,path if target.is_relative_to(dist) and target.is_file() else 'index.html')
    return app


def score_detail(sid):
    s=one('SELECT s.*,a.area_name FROM risk_score s LEFT JOIN area_info a USING(area_id) WHERE score_id=%s',(sid,))
    if not s:fail('评分不存在',404)
    fs=query('SELECT x.*,f.feature_name,f.match_expr,f.direction FROM risk_score_feature x JOIN feature_def f USING(feature_id) WHERE score_id=%s ORDER BY feature_id',(sid,))
    for f in fs:decode(f,'evidence_json')
    return dict(score=describe_score(s),features=fs)


def evaluation_sql():
    where='';args=[]
    if request.args.get('batch_id'):where+=' AND s.batch_id=%s';args.append(request.args['batch_id'])
    if request.args.get('version_id'):where+=' AND s.version_id=%s';args.append(request.args['version_id'])
    sql='''WITH ranked AS (SELECT s.*,ROW_NUMBER() OVER(PARTITION BY s.object_type,s.object_id,s.window_start ORDER BY b.created_at DESC,b.batch_id DESC) rn FROM risk_score s JOIN judge_batch b USING(batch_id) WHERE b.run_status=2'''+where+''')
SELECT l.*,CONCAT(l.label_id,'/',COALESCE(s.score_id,'none')) row_id,s.score_id,s.batch_id,s.total_score,s.is_clue prediction,
CASE WHEN s.score_id IS NULL OR s.total_score IS NULL THEN 'missing' WHEN l.label=1 AND s.is_clue=1 THEN 'tp' WHEN l.label=0 AND s.is_clue=1 THEN 'fp' WHEN l.label=1 THEN 'fn' ELSE 'tn' END result
FROM eval_label l LEFT JOIN ranked s ON s.object_type=l.object_type AND s.object_id=l.object_id AND s.window_start=l.window_start AND s.rn=1'''
    return sql,args


def evaluation_summary():
    sql,args=evaluation_sql()
    counts={r['result']:r['n'] for r in query('SELECT result,COUNT(*) n FROM ('+sql+') evaluated GROUP BY result',args)}
    tp,fp,fn,tn=[counts.get(k,0) for k in ('tp','fp','fn','tn')]
    def div(a,b):return round(a/b,4) if b else None
    p,r=div(tp,tp+fp),div(tp,tp+fn)
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=p,recall=r,fpr=div(fp,fp+tn),f1=div(2*tp,2*tp+fp+fn),sample_total=sum(counts.values()),missing_count=counts.get('missing',0),noise_ratio=one('SELECT AVG(sample_type=2) n FROM eval_label')['n'])


if __name__=='__main__':
    create_app().run(host=os.getenv('APP_HOST','127.0.0.1'),port=int(os.getenv('APP_PORT','5000')),debug=False)
