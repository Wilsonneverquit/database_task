"""Allowlisted relational CRUD and atomic CSV import, no dynamic client SQL identifiers."""
import csv
import io
import json
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import request,g
from .db import get_db,query,one,execute,insert,audit,transaction,now

SPECS={
 'areas':('area_info','area_id','区域',['area_id','area_name','area_type','parent_area_id','lng','lat']),
 'places':('place_info','place_id','场所',['place_id','place_name','place_type','area_id','address','is_active']),
 'persons':('person_info','person_id','人员',['person_id','person_name','gender','birth_year','home_area_id','person_type','is_active']),
 'vehicles':('vehicle_owner','vehicle_id','车辆',['vehicle_id','plate_mask','owner_person_id','vehicle_type','is_active']),
 'consumptions':('consume_record','consume_id','消费流水',['consume_id','record_no','person_id','place_id','consume_time','amount','has_alcohol','recorded_at','is_active']),
 'orders':('taxi_order','order_id','出行订单',['order_id','order_no','person_id','order_type','order_time','completed_at','start_area_id','end_area_id','order_status','recorded_at','is_active']),
 'tracks':('vehicle_track','track_id','过车记录',['track_id','record_no','vehicle_id','gate_id','area_id','pass_time','direction','recorded_at','is_active']),
 'cases':('case_info','case_id','历史案件',['case_id','occur_time','area_id','place_id','person_id','vehicle_id','driver_confirmed','case_type','alcohol_value','distance_home','dispose_status','is_active']),
 'rules':('judge_rule','rule_id','研判规则',['rule_id','rule_name','version_id','judge_object','min_sample','min_hit_cnt','low_threshold','high_threshold','counter_block','status','remark','config_json']),
 'versions':('feature_version','version_id','特征版本',['version_id','version_no','remark']),
 'users':('sys_user','user_id','用户',['user_id','username','real_name','status']),
 'roles':('sys_role','role_id','角色',['role_id','role_name','role_desc','status']),
 'coverage':('ingest_window','ingest_id','数据源覆盖窗口',['ingest_id','source_type','window_start','window_end','available_at','coverage']),
}
FEATURE_IDS={'F001','F002','F003','F004','F005','F006','F008'}


def register_resources(app):
    from .app import ok,fail,body,page
    def spec(resource,write=False):
        if resource not in SPECS:fail('资源不存在',404)
        allowed={'R_ADMIN'} if resource in ('users','roles') else {'R_FEATURE'} if resource in ('rules','versions') else {'R_DATA','R_ADMIN'}
        if not write:allowed|={'R_TEACHER'}
        if not allowed.intersection(g.roles):fail('当前角色无权维护此类数据',403)
        return SPECS[resource]

    def metadata(resource):
        table,pk,title,fields=spec(resource)
        cols=query('SELECT COLUMN_NAME name,DATA_TYPE type,IS_NULLABLE nullable,COLUMN_DEFAULT default_value,EXTRA extra,CHARACTER_MAXIMUM_LENGTH max_length FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position',(table,))
        return dict(resource=resource,title=title,primary_key=pk,fields=[c for c in cols if c['name'] in fields],can_write=resource!='roles' and bool(({'R_ADMIN'} if resource in ('users','roles') else {'R_FEATURE'} if resource in ('rules','versions') else {'R_DATA','R_ADMIN'}).intersection(g.roles)))

    @app.get('/api/data')
    def catalog():
        result=[]
        for key in SPECS:
            try:result.append(metadata(key))
            except Exception as e:
                from .app import APIError
                if not isinstance(e,APIError) or e.status!=403:raise
        return ok(result)

    @app.get('/api/data/<resource>')
    def listing(resource):
        table,pk,title,fields=spec(resource)
        terms=[];args=[]
        q=request.args.get('q','').strip()
        if q:
            searchable=[f for f in fields if f.endswith(('_id','_name','_no')) or f in ('username','plate_mask')]
            terms.append('('+' OR '.join('`'+f+'` LIKE %s' for f in searchable)+')');args.extend(['%'+q+'%']*len(searchable))
        sql=f'SELECT {",".join("`"+f+"`" for f in fields)} FROM `{table}`'+(' WHERE '+' AND '.join(terms) if terms else '')+f' ORDER BY `{pk}` DESC'
        result=page(sql,args)
        if resource=='users':
            for u in result['list']:u['roles']=[r['role_id'] for r in query('SELECT role_id FROM sys_user_role WHERE user_id=%s',(u['user_id'],))]
        return ok(result)

    @app.get('/api/data/<resource>/<key>')
    def detail(resource,key):
        table,pk,_,fields=spec(resource)
        row=one(f'SELECT {",".join("`"+f+"`" for f in fields)} FROM `{table}` WHERE `{pk}`=%s',(key,))
        if not row:fail('记录不存在',404)
        return ok(row)

    def locked(table,pk,key,row):
        if table=='sys_user' and key==g.user['user_id'] and row.get('status',1)!=1:fail('不能停用当前登录账号',409)
        if table=='sys_role':fail('课程角色权限由服务端定义，不允许删除或重定义角色',409)
        if table=='feature_version':
            v=one('SELECT publish_status FROM feature_version WHERE version_id=%s',(key,))
            if v and v['publish_status']!=0:fail('已发布或归档版本不可修改',409)
        if table=='judge_rule':
            n=one('SELECT COUNT(*) n FROM judge_batch WHERE rule_id=%s',(key,))['n']
            if n:fail('已执行规则保持冻结；请在草稿版本创建新规则',409)
        source_col={'consume_record':'consume_id','taxi_order':'order_id','vehicle_track':'track_id'}.get(table)
        if source_col and one(f'SELECT node_id FROM chain_node WHERE `{source_col}`=%s LIMIT 1',(key,)):fail('该记录已进入证据快照；请新增更正记录并保留原记录',409)

    def validate(resource,row,creating):
        from .scoring import dt
        table,pk,_,fields=SPECS[resource]
        extra=set(row)-set(fields)-({'password','roles'} if resource=='users' else set())
        if extra:fail('不允许写入字段：'+','.join(sorted(extra)))
        if not creating:row.pop(pk,None)
        row={k:(None if v=='' else v) for k,v in row.items()}
        if resource in ('consumptions','orders','tracks'):
            row.setdefault('recorded_at',now()) if creating else None
            timekey={'consumptions':'consume_time','orders':'order_time','tracks':'pass_time'}[resource]
            if row.get(timekey) and row.get('recorded_at') and dt(row['recorded_at'])<dt(row[timekey]):fail('入库时间不能早于事件时间')
        if resource=='orders' and row.get('order_status') is not None:
            status=int(row['order_status'])
            if status==1 and not row.get('completed_at'):fail('已完成订单必须提供完成时间')
            if status!=1 and row.get('completed_at'):fail('未完成订单不能有完成时间')
        if resource=='cases' and row.get('occur_time'):
            cutoff=one("SELECT param_value FROM param_config WHERE param_key='history_cutoff'")['param_value']
            if dt(row['occur_time'])>=dt(cutoff):fail('案件必须早于历史边界；观察段标签只能用于评估')
        if resource=='rules':
            if row.get('low_threshold') is not None and not 0<=float(row['low_threshold'])<=100:fail('阈值必须在 0–100 内')
            if row.get('high_threshold') is not None and not 0<=float(row['high_threshold'])<=100:fail('阈值必须在 0–100 内')
            if creating:
                version=one('SELECT * FROM feature_version WHERE version_id=%s',(row.get('version_id'),))
                if not version or version['publish_status']!=0:fail('新规则必须属于草稿版本')
            cfg=row.get('config_json')
            if cfg is not None:
                cfg=json.loads(cfg) if isinstance(cfg,str) else cfg
                weights=cfg.get('weights',[])
                if not weights or any(not isinstance(x,list) or len(x)!=2 or x[0] not in FEATURE_IDS or not 0<float(x[1])<=1 for x in weights) or abs(sum(float(x[1]) for x in weights)-1)>.0001 or len({x[0] for x in weights})!=len(weights):fail('因子权重必须为已知因子的唯一列表，正权重之和必须为 1')
                cfg['version_id']=row.get('version_id') or cfg.get('version_id');row['config_json']=json.dumps(cfg)
            elif creating:fail('规则必须提供 config_json，其中 weights 保存因子编号及权重')
        if resource=='users':
            pwd=row.pop('password',None)
            if creating and (not pwd or len(pwd)<6):fail('新增用户需要至少六位口令')
            if pwd:
                if len(pwd)<6:fail('口令至少六位')
                row['password_hash']=generate_password_hash(pwd);row['salt']='managed-hash-v1'
            if creating:row.setdefault('status',1)
        if creating:
            types={c['name']:c for c in metadata(resource)['fields']}
            if pk not in row and 'auto_increment' not in types[pk]['extra']:
                row[pk]=secrets.token_hex(5).upper()
            if resource=='vehicles':row['plate_hash']=__import__('hashlib').sha256(str(row.get('plate_mask','')).encode()).hexdigest()
        return row

    def save(resource,row,key=None):
        table,pk,_,_=spec(resource,True)
        requested_roles=row.pop('roles',None)
        if resource=='roles':fail('角色列表固定；通过用户角色分配进行授权',409)
        if requested_roles is not None:
            if not isinstance(requested_roles,list) or set(requested_roles)-{r['role_id'] for r in query('SELECT role_id FROM sys_role')}:fail('角色编号无效')
            if key==g.user['user_id'] and 'R_ADMIN' not in requested_roles:fail('不能移除自己的管理员角色',409)
        if key is not None:
            if not one(f'SELECT `{pk}` FROM `{table}` WHERE `{pk}`=%s FOR UPDATE',(key,)):fail('记录不存在',404)
            locked(table,pk,key,row)
        row=validate(resource,row,key is None)
        if key is None:
            number=insert(table,row,get_db());key=row.get(pk,number)
        elif row:
            execute(f'UPDATE `{table}` SET '+','.join('`'+k+'`=%s' for k in row)+f' WHERE `{pk}`=%s',(*row.values(),key))
        if resource=='users' and requested_roles is not None:
            execute('DELETE FROM sys_user_role WHERE user_id=%s',(key,))
            for role in set(requested_roles):insert('sys_user_role',dict(user_id=key,role_id=role),get_db())
        if resource=='rules':
            cfg=json.loads(one('SELECT config_json FROM judge_rule WHERE rule_id=%s',(key,))['config_json'])
            execute('DELETE FROM rule_feature WHERE rule_id=%s',(key,))
            for i,(fid,weight) in enumerate(cfg['weights']):insert('rule_feature',dict(rule_id=key,feature_id=fid,sort_no=i),get_db())
        audit(g.user['user_id'],table,key,'新增记录' if request.method=='POST' else '更正记录',3 if request.method=='POST' else 4)
        return key

    @app.post('/api/data/<resource>')
    def create(resource):
        with transaction():key=save(resource,body())
        return ok(dict(id=key),201)

    @app.patch('/api/data/<resource>/<key>')
    def update(resource,key):
        with transaction():save(resource,body(),key)
        return ok(dict(id=key))

    @app.delete('/api/data/<resource>/<key>')
    def delete(resource,key):
        table,pk,_,_=spec(resource,True)
        with transaction():
            locked(table,pk,key,{})
            if resource=='rules':execute('DELETE FROM rule_feature WHERE rule_id=%s',(key,))
            _,n=execute(f'DELETE FROM `{table}` WHERE `{pk}`=%s',(key,))
            if not n:fail('记录不存在',404)
            audit(g.user['user_id'],table,key,'删除未被引用记录',5)
        return ok(dict(id=key))

    @app.post('/api/data/<resource>/imports')
    def import_csv(resource):
        spec(resource,True)
        file=request.files.get('file')
        if not file:fail('请上传 UTF-8 CSV 文件，字段名见资源定义')
        try:
            rows=list(csv.DictReader(io.StringIO(file.read().decode('utf-8-sig'))))
        except UnicodeError:fail('CSV 必须使用 UTF-8 编码')
        if not rows or len(rows)>10000:fail('一次导入应为 1–10000 行')
        with transaction():
            for index,row in enumerate(rows,2):
                try:save(resource,row)
                except ValueError as e:fail(f'CSV 第 {index} 行：{e}')
        return ok(dict(imported=len(rows)),201)
