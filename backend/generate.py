"""Event-first, reproducible fictional data. No target scores or score profiles."""
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from .db import ROOT, query, execute, insert_many, insert
from .scoring import REGION, PERSON, NAMES
from .engine import build_baseline, run_batch

CUTOFF = datetime(2026,11,1)
START = datetime(2026,9,26)
END = datetime(2026,11,25)


def audit_original():
    """Inspect existing seed without importing its old precomputed scores."""
    import subprocess
    output = subprocess.check_output(['node','--input-type=module','-e',
        'import {createSeed} from "./frontend/src/api/mock/seed.js";console.log(JSON.stringify(createSeed()))'],cwd=ROOT)
    old = json.loads(output)
    ids = {k:len(v) for k,v in old.items()}
    scores = old['risk_score']
    areas = {p['place_id']:p['area_id'] for p in old['place_info']}
    owners = {v['vehicle_id']:v['owner_person_id'] for v in old['vehicle_owner']}
    impossible = sum(1 for o in old['taxi_order'] if o['order_status']==1 and not o.get('completed_at'))
    return {'source':'frontend/src/api/mock/seed.js','rows':sum(ids.values()),'tables':ids,
            'distinct_region_scores':len({s['total_score'] for s in scores if s['object_type']==1}),
            'completed_orders_without_completion_time':impossible,
            'region_scores_without_calendar_window':sum(s['object_type']==1 and not s.get('window_start') for s in scores),
            'policy':'Original files preserved; derived scores not imported. Demo source events rebuilt with chronological validation.'}


ACCOUNT_NAMES = ('admin','analyst1','analyst2','featop','teacher','dataop')


def initialize_accounts(conn, created, passwords):
    roles = [('R_ANALYST','研判员'),('R_DATA','数据管理员'),('R_FEATURE','特征管理员'),('R_ADMIN','系统管理员'),('R_TEACHER','教师/评审')]
    insert_many('sys_role',[dict(role_id=k,role_name=v,role_desc=v+'业务权限',status=1) for k,v in roles],conn)
    users=[('admin',['R_ADMIN']),('analyst1',['R_ANALYST','R_TEACHER']),('analyst2',['R_ANALYST']),('featop',['R_FEATURE']),('teacher',['R_TEACHER']),('dataop',['R_DATA'])]
    for i,(name,rs) in enumerate(users,1):
        uid=f'U{i:04d}'
        insert('sys_user',dict(user_id=uid,username=name,password_hash=generate_password_hash(passwords[name]),salt='managed-hash-v1',real_name=dict(admin='系统管理员',analyst1='研判员甲',analyst2='研判员乙',featop='特征管理员',teacher='课程评审',dataop='数据管理员')[name],status=1,created_at=created),conn)
        insert_many('sys_user_role',[dict(user_id=uid,role_id=r) for r in rs],conn)


def initialize_rules(conn, cutoff, vid, draft, case_count=0, control_count=0):
    for fid,name in NAMES.items():
        source={'F001':'consume_record','F002':'consume_record','F003':'taxi_order','F004':'vehicle_track','F005':'vehicle_track','F006':'taxi_order','F008':'v_case_history'}[fid]
        insert('feature_def',dict(feature_id=fid,feature_code='DYNAMIC_'+fid,feature_name=name,risk_type=1,feature_cat=5 if fid=='F006' else 4,direction=2 if fid=='F006' else 1,object_scope=3,value_type=2,src_table='case_info',match_src=source,match_expr='连续因子；原始值 / 历史冻结基线，截断到 0–1；近三小时按 90 分钟时间常数衰减',time_window_min=180,min_sample=1,status=1,description='风险指数贡献与统计对数优势比分开保存；驾驶人身份不能由车辆归属推断'),conn)
    baseline=build_baseline(conn,cutoff)
    insert('feature_version',dict(version_id=vid,risk_type=1,version_no='3.0',publish_status=0,based_case_cnt=case_count,based_ctrl_cnt=control_count,calc_at=cutoff,published_by='U0004',remark='连续因子风险指数；固定历史基线',created_at=cutoff,algorithm_version='continuous-v1',baseline_json=json.dumps(baseline)),conn)
    insert('feature_version',dict(version_id=draft,risk_type=1,version_no='3.1',publish_status=0,based_case_cnt=0,based_ctrl_cnt=0,remark='供反馈修订与版本实验使用的草稿',created_at=cutoff,algorithm_version='continuous-v1'),conn)
    for rid,obj,weights in [('R001',1,REGION),('R002',2,PERSON)]:
        insert('judge_rule',dict(rule_id=rid,rule_name='区域逐小时风险指数' if obj==1 else '人员事件风险指数',risk_type=1,version_id=vid,judge_object=obj,min_sample=1,min_hit_cnt=2,low_threshold=40,high_threshold=70,counter_block=1,status=1,remark='0–100 指数，不是发生概率',created_at=cutoff,config_json=json.dumps({'weights':weights,'version_id':vid})),conn)
        insert_many('rule_feature',[dict(rule_id=rid,feature_id=f,is_required=0,sort_no=i) for i,(f,w) in enumerate(weights)],conn)
    from .learning import recalculate
    recalculate(conn,vid,'U0004')
    execute('UPDATE feature_version SET publish_status=1 WHERE version_id=%s',(vid,),conn)


def generate(conn, seed=20261125, light=False):
    if query('SELECT user_id FROM sys_user LIMIT 1',conn=conn):
        raise ValueError('演示库已有数据；为避免覆盖，请使用显式 reset-demo 命令')
    rng = random.Random(seed)
    original_report=audit_original()
    insert('data_quality_report',dict(source_name='原始演示种子审计',report_json=json.dumps(original_report,ensure_ascii=False)),conn)
    initialize_accounts(conn, START, dict.fromkeys(ACCOUNT_NAMES,'123456'))
    params=[('history_cutoff','2026-11-01 00:00:00'),('dataset_start',str(START)),('dataset_end',str(END)),('dataset_seed',str(seed)),('data_provenance','fictional_event_simulation')]
    insert_many('param_config',[dict(param_key=k,param_value=v,param_type=3,param_desc='课程演示配置',updated_at=START) for k,v in params],conn)
    names=['中心商务区','老城餐饮街','东门居住区','南站交通区','大学生活区','滨河休闲区','西城工业区','北高速出入口','城南社区','东城商业街','夜市步行街','近郊乡镇']
    # Fictional ring topology; each hop requires >=15 minutes.
    areas=[dict(area_id=f'A{i+1:02d}',area_name=name,area_type=[2,2,1,1,2,2,1,4,1,2,2,3][i],parent_area_id=None,lng=round(118.85+.045*math.cos(i*math.pi/6),6),lat=round(31.60+.035*math.sin(i*math.pi/6),6),created_at=START) for i,name in enumerate(names)]
    insert_many('area_info',areas,conn)
    places=[]
    for i,a in enumerate(areas):
        for j in range(4):
            places.append(dict(place_id=f'PL{i*4+j+1:04d}',place_name=a['area_name']+['家常餐厅','夜间餐饮店','休闲酒吧','便民餐厅'][j],place_type=[1,1,3,1][j],area_id=a['area_id'],address=a['area_name']+f'示例街{j+1}号',is_active=1))
    insert_many('place_info',places,conn)
    npeople=500 if light else 1500
    nvehicles=120 if light else 350
    people=[dict(person_id=f'P{i+1:04d}',person_name=f'示例人员{i+1:04d}',gender=1+i%2,birth_year=rng.randint(1968,2005),phone_hash=hashlib.sha256(f'synthetic-phone-{i}'.encode()).hexdigest(),home_area_id=areas[i%12]['area_id'],person_type=3,created_at=START,is_active=1) for i in range(npeople)]
    insert_many('person_info',people,conn)
    vehicles=[dict(vehicle_id=f'V{i+1:04d}',plate_hash=hashlib.sha256(f'synthetic-plate-{i}'.encode()).hexdigest(),plate_mask=f'示A·***{i:03d}',owner_person_id=people[i]['person_id'],vehicle_type=1,is_active=1) for i in range(nvehicles)]
    insert_many('vehicle_owner',vehicles,conn)
    owner_vehicle={v['owner_person_id']:v['vehicle_id'] for v in vehicles}
    all_cons,all_orders,all_tracks,driver_rows,cases,controls=[],[],[],[],[],[]
    truths=[]
    last_area={v['vehicle_id']:i%12 for i,v in enumerate(vehicles)}
    def track(vid,area,t,direction,driver=None):
        row=dict(track_id=len(all_tracks)+1,record_no=f'VT{len(all_tracks)+1:09d}',vehicle_id=vid,gate_id=f'A{area+1:02d}-G01',area_id=f'A{area+1:02d}',pass_time=t,direction=direction,recorded_at=t+timedelta(seconds=20),is_active=1)
        all_tracks.append(row)
        if driver:
            driver_rows.append(dict(track_id=row['track_id'],person_id=driver,source_type='synthetic_observation',observed_at=t,recorded_at=t+timedelta(seconds=40)))
        return row
    def move(vid,a,b,t,driver=None):
        # Ring route with 18-minute hops, never teleport across distant regions.
        while a!=b:
            step=1 if (b-a)%12 <= (a-b)%12 else -1
            track(vid,a,t,2,driver); t+=timedelta(minutes=18); a=(a+step)%12; track(vid,a,t,1,driver)
        last_area[vid]=b
        return t
    for day in range(60):
        base=START+timedelta(days=day)
        selected=rng.sample(people,100 if light else 420)
        selected_people={p['person_id'] for p in selected}
        borrow_pool=[v['vehicle_id'] for v in vehicles if v['owner_person_id'] not in selected_people]
        borrowed_today=set()
        for p in selected:
            pid=p['person_id']; region=rng.choices(range(12),weights=[1.2,2.5,.7,.9,1.5,1.6,.5,.4,.6,1.7,2.1,.7])[0]
            weekend=base.weekday()>=5
            hour=rng.choices([11,12,17,18,19,20,21,22],weights=[1,1,1,2,3,4 if weekend else 2,4 if weekend else 2,2])[0]
            minute=rng.randint(0,44)
            t=base+timedelta(hours=hour,minutes=minute)
            alcohol=int(rng.random()<([.50,.68,.15,.16,.40,.55,.12,.13,.18,.48,.72,.22][region])*(1.15 if weekend else .85) and hour>=17)
            place=places[region*4+(rng.choice([0,1,2]) if hour>=17 else rng.choice([0,3]))]
            cid=len(all_cons)+1
            all_cons.append(dict(consume_id=cid,record_no=f'CR{cid:09d}',person_id=pid,place_id=place['place_id'],consume_time=t,amount=round(min(2200,max(12,rng.lognormvariate(4.9 if alcohol else 3.9,.55))),2),has_alcohol=alcohol,recorded_at=t+timedelta(seconds=15),is_active=1))
            departure=t+timedelta(minutes=rng.randint(20,75))
            vid=owner_vehicle.get(pid)
            borrowed=False
            if not vid and borrow_pool and rng.random()<.01:
                vid=borrow_pool.pop();borrowed_today.add(vid);borrowed=True
            unsafe=bool(alcohol and vid and rng.random()<.19)
            mode='unsafe' if unsafe else rng.choices(['driver','taxi','cancel','none'],weights=[25 if alcohol else 4,25,7,43])[0]
            ride=mode in ('driver','taxi')
            destination=(region+rng.choice([-1,1]))%12
            if mode in ('driver','taxi','cancel'):
                ordertime=departure-timedelta(minutes=8)
                all_orders.append(dict(order_id=len(all_orders)+1,order_no=f'TO{len(all_orders)+1:09d}',person_id=pid,order_type=2 if mode=='driver' else 1,order_time=ordertime,start_area_id=areas[region]['area_id'],end_area_id=areas[destination]['area_id'],order_status=2 if mode=='cancel' else 1,completed_at=None if mode=='cancel' else departure+timedelta(minutes=25),recorded_at=(ordertime+timedelta(seconds=10)) if mode=='cancel' else departure+timedelta(minutes=25,seconds=10),is_active=1))
            if vid:
                move(vid,last_area[vid],region,t-timedelta(hours=3))
                # Driver observations are separate evidence, not inferred from ownership.
                actual_driver=pid if not ride and (borrowed or rng.random()<.55) else None
                move(vid,region,destination,departure,actual_driver)
            if base<CUTOFF:
                if unsafe and departure+timedelta(minutes=10)<CUTOFF:
                    cases.append(dict(case_id=f'CA{len(cases)+1:06d}',occur_time=departure+timedelta(minutes=10),area_id=areas[region]['area_id'],place_id=place['place_id'],person_id=pid,vehicle_id=vid,driver_confirmed=1,case_type=1,alcohol_value=round(rng.uniform(25,75),1),distance_home=rng.randint(1,20),dispose_status=1,created_at=departure+timedelta(minutes=30),is_active=1))
                elif rng.random()<.12:
                    controls.append(dict(person_id=pid,area_id=areas[region]['area_id'],sample_date=t.date(),hour_slot=t.hour,match_type=1))
            else:
                # Independent scenario truth, never consulted by engine.calculate.
                truths.append(dict(person_id=pid,area_id=areas[region]['area_id'],at=departure,label=int(unsafe),sample_type=1 if unsafe else 2 if alcohol and ride else 3))
        # Non-drinking background traffic from other vehicle owners, maintaining route continuity.
        active_ids={p['person_id'] for p in selected}
        spare=[v for v in vehicles if v['owner_person_id'] not in active_ids and v['vehicle_id'] not in borrowed_today]
        for v in rng.sample(spare,min(len(spare),30 if light else 100)):
            a=last_area[v['vehicle_id']]; b=(a+rng.choice([-1,1]))%12
            move(v['vehicle_id'],a,b,base+timedelta(hours=rng.randint(7,21),minutes=rng.randint(0,59)))
    insert_many('consume_record',all_cons,conn)
    insert_many('taxi_order',all_orders,conn)
    insert_many('vehicle_track',all_tracks,conn)
    insert_many('driver_evidence',driver_rows,conn)
    insert_many('case_info',cases,conn)
    insert_many('control_person',controls,conn)
    insert_many('ingest_window',[dict(source_type=s,window_start=START,window_end=END,available_at=START,coverage=1) for s in ['consume','track','order']],conn)
    initialize_rules(conn,CUTOFF,'V20261101_D1','V20261101_D2',len(cases),len(controls))
    vid='V20261101_D1'
    # Calculate all observation hours with one batch per date and object type.
    for day in range((END-CUTOFF).days):
        start=CUTOFF+timedelta(days=day)
        for obj in (1,2):
            bid=f'B{start:%Y%m%d}{obj:02d}'
            insert('judge_batch',dict(batch_id=bid,rule_id=f'R00{obj}',version_id=vid,judge_object=obj,data_start=start,data_end=start+timedelta(days=1),area_id=None,run_status=0,run_no=0,object_cnt=0,clue_cnt=0,operator_id='U0004',created_at=start+timedelta(days=1)),conn)
            run_batch(conn,bid,'U0004')
        conn.commit()
        print('Scored',start.date(),flush=True)
    # Labels use exact object+calendar hour. Missing predictions remain coverage gaps.
    grouped=defaultdict_truth(truths)
    insert_many('eval_label',list(grouped.values()),conn)
    counts={t:one_count(conn,t) for t in ['person_info','consume_record','taxi_order','vehicle_track','risk_score','risk_clue']}
    insert('param_config',dict(param_key='dataset_summary',param_value=json.dumps(counts,separators=(',',':')),param_type=3,param_desc='数据生成后计数'),conn)
    insert('audit_log',dict(user_id='U0004',operator_tag='generator',op_type=3,table_name='param_config',record_pk='dataset_seed',op_desc=f'事件优先数据生成，seed={seed}；旧库保留；消费 {len(all_cons)} / 订单 {len(all_orders)} / 过车 {len(all_tracks)}'),conn)
    conn.commit()
    return counts


def one_count(conn,table):
    return query(f'SELECT COUNT(*) n FROM `{table}`',conn=conn)[0]['n']


def defaultdict_truth(truths):
    result={}
    for t in truths:
        hour=t['at'].replace(minute=0,second=0,microsecond=0)
        for obj,oid in [(1,f"{t['area_id']}#{hour:%Y%m%d%H}"),(2,t['person_id'])]:
            key=(obj,oid,hour)
            if key not in result:
                result[key]=dict(object_type=obj,object_id=oid,window_start=hour,window_end=hour+timedelta(hours=1),sample_type=t['sample_type'],label=t['label'],case_cnt=t['label'],created_at=hour+timedelta(hours=1))
            else:
                r=result[key];r['label']=max(r['label'],t['label']);r['case_cnt']+=t['label'];r['sample_type']=1 if r['label'] else min(r['sample_type'],t['sample_type'])
    return result
