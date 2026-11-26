"""Exercise every registered API method against both live databases, including writes.

RUN_DUAL_DB=1 opts into the two-instance integration test. Fixture writes are visible
only to one connection per instance. Closing those connections rolls everything back.
"""
import io
import os
from contextlib import ExitStack, closing

import pytest
from werkzeug.security import generate_password_hash

from backend import db
from backend.app import create_app
from backend.public_store import verify
from backend.resources import SPECS

pytestmark = pytest.mark.skipif(os.getenv('RUN_DUAL_DB')!='1',reason='requires both installed MySQL sources')


class IsolatedRequest:
    def __init__(self, conn):
        self.conn = conn
        self.commit()

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        db.execute('SAVEPOINT http_committed',conn=self.conn)

    def rollback(self):
        db.execute('ROLLBACK TO SAVEPOINT http_committed',conn=self.conn)

    def close(self):
        pass


def shape(value):
    if isinstance(value,dict):
        fields = {}
        for k,v in value.items():
            if k=='tables' and isinstance(v,dict):
                assert all(type(n) is int for n in v.values())
                fields[k]='table-count-map'
            else:
                fields[k]=shape(v)
        return fields
    if isinstance(value,list):
        return [shape(value[0])] if value else []
    if type(value) in (float,int):
        return 'number'
    return type(value).__name__


def compare(a,b,path='data'):
    if isinstance(a,list) and isinstance(b,list):
        if a and b:
            compare(a[0],b[0],path+'[]')
    elif isinstance(a,dict) and isinstance(b,dict):
        assert a.keys()==b.keys(),(path,a.keys()^b.keys())
        for k in a:
            compare(a[k],b[k],path+'.'+k)
    elif a!='NoneType' and b!='NoneType':
        assert a==b,(path,a,b)


def exercise(client,app,source,conn):
    records={}
    routes=set()
    headers={'X-Data-Source':source}
    def send(method,path,status=200,label=None,**kwargs):
        rule,_=app.url_map.bind('localhost').match(path.split('?')[0],method=method,return_rule=True)
        routes.add((method,rule.rule))
        response=client.open(path,method=method,headers=headers,**kwargs)
        assert response.status_code==status,(source,method,path,response.json)
        if method=='OPTIONS':
            assert response.data==b''
            return
        assert response.headers['X-Data-Source']==source
        body=response.json
        assert response.mimetype=='application/json' and set(body)=={'code','message','data'}
        assert type(body['code']) is int and type(body['message']) is str
        assert body['code']==(0 if status<400 else status*10)
        key=(method,label or rule.rule,status)
        records[key]=shape(body['data'])
        return body['data']

    uid='CONTRACT_USER'
    db.insert('sys_user',dict(user_id=uid,username=uid,real_name='接口测试',salt='test',
              password_hash=generate_password_hash('contract-fixture')),conn)
    for row in db.query('SELECT role_id FROM sys_role',conn=conn):
        db.insert('sys_user_role',dict(user_id=uid,**row),conn)
    db.insert('param_config',dict(param_key='contract_param',param_value='start'),conn)
    send('GET','/api/health',401)
    send('OPTIONS','/api/arbitrary',204)
    login=dict(username=uid,password='contract-fixture')
    send('POST','/api/login',json=login)
    token=send('POST','/api/auth/sessions',json=login)['token']
    headers['Authorization']='Bearer '+token
    other='demo' if source=='real' else 'real'
    assert client.get('/api/health',headers={**headers,'X-Data-Source':other}).status_code==401
    def create(resource,row):
        return send('POST','/api/data/'+resource,201,json=row,label='create '+resource)['id']
    aid=create('areas',dict(area_id='CT_AREA',area_name='测试道路',area_type=1,lng=1,lat=1))
    pid=create('persons',dict(person_id='CT_PERSON',person_name='测试人员'))
    place=create('places',dict(place_id='CT_PLACE',place_name='测试场所',area_id=aid))
    car=create('vehicles',dict(vehicle_id='CT_CAR',plate_mask='CT-TEST',owner_person_id=pid))
    begin='2026-11-26 21:00:00'
    end='2026-11-26 22:00:00'
    def at(minute):
        return f'2026-11-26 21:{minute:02}:00'
    for minute in (20,24,28,32):
        create('consumptions',dict(record_no='CT_C'+str(minute),person_id=pid,place_id=place,
                consume_time=at(minute),recorded_at=at(minute),amount=30,has_alcohol=1))
    create('tracks',dict(record_no='CT_TRACK',vehicle_id=car,area_id=aid,gate_id=aid+'-G1',
                         pass_time=at(48),recorded_at=at(48),direction=2))
    create('orders',dict(order_no='CT_ORDER',person_id=pid,order_time=at(2),recorded_at=at(8),
                         completed_at=at(8),order_type=1,order_status=1))
    create('cases',dict(case_id='CT_CASE',occur_time='2010-01-01 12:00:00',area_id=aid,
                        person_id=pid,alcohol_value=60))
    for cat in ('consume','order','track'):
        create('coverage',dict(source_type=cat,window_start='2026-11-26 17:00:00',window_end=end,
                              available_at='2026-11-26 16:00:00',coverage=1))
    version=create('versions',dict(version_id='CT_VERSION',version_no='test-contract'))
    db.insert('eval_label',dict(object_type=2,object_id=pid,sample_type=1,label=1,
              window_start=begin,window_end=end),conn)
    send('POST','/api/weights/recalc',json={'version_id':version})
    send('PATCH','/api/versions/'+version+'/publish',json={'publish_status':1})
    for obj,ending in [(1,'/run'),(2,'/runs')]:
        rule=db.one('SELECT rule_id id FROM judge_rule WHERE version_id=%s AND judge_object=%s',(version,obj),conn)['id']
        bid=send('POST','/api/batches',201,json=dict(batch_id='CT_BATCH'+str(obj),area_id=aid,
                 data_start=begin,data_end=end,rule_id=rule))['batch_id']
        assert send('POST','/api/batches/'+bid+ending,201)['object_cnt']==1
    clue=send('GET','/api/clues?person_id='+pid)['list'][0]
    cid=clue['clue_id']
    send('PATCH','/api/clues/'+cid+'/status',json={'status':1})
    send('POST','/api/clues/'+cid+'/feedback',201,json=dict(check_result=2,check_method=3,check_remark='接口测试'))
    send('GET','/api/clues/'+cid)
    assert send('GET','/api/clues/'+cid+'/chain')['chains']
    send('GET',f"/api/scores/{clue['score_id']}/features")
    for path in ['dicts','overview','region-risk?area_id='+aid,'batches?size=1','features','features/F002',
                 'versions','eval/confusion','eval/samples?size=1&result=tp','eval/labels','audit?size=1',
                 'users','params','cases?area_id='+aid,'health','data-quality','risk-map?aggregation=day_peak',
                 'risk-trends?person_id='+pid,'persons/'+pid+'/timeline','person-risks?q='+pid,
                 'evidence/subjects?scope=person&q='+pid,'evidence/events?scope=person&person_id='+pid,'data']:
        send('GET','/api/'+path)
    send('PATCH','/api/features/F002/status',409,json={'status':0})
    send('PATCH','/api/params/contract_param',json={'param_value':'changed'})
    for resource,(table,pk,_,_) in SPECS.items():
        data=send('GET','/api/data/'+resource+'?size=1',label='list '+resource)
        assert data['list'],resource
        key=data['list'][0][pk]
        send('GET',f'/api/data/{resource}/{key}',label='detail '+resource)
    send('POST','/api/data/persons/imports',201,data={'file':(io.BytesIO(b'person_id,person_name\nCT_EXTRA,test\n'),'rows.csv')})
    send('PATCH','/api/data/persons/CT_EXTRA',json={'person_name':'edited'})
    send('DELETE','/api/data/persons/CT_EXTRA')
    send('GET','/api/data/persons/CT_EXTRA',404)
    send('DELETE','/api/auth/sessions/current')
    send('GET','/api/health',401)
    return records,routes


def test_dual_api_contract(monkeypatch):
    assert verify()['TABLE']>0
    monkeypatch.setenv('DATA_SOURCE','real')
    app=create_app()
    with ExitStack() as stack:
        conns={s:stack.enter_context(closing(db.connect(source=s))) for s in ('demo','real')}
        monkeypatch.setattr(db,'connect',lambda *,source:IsolatedRequest(conns[source]))
        client=app.test_client()
        assert client.get('/api/health').headers['X-Data-Source']=='real'
        assert client.get('/data-source-config.js').data==b'window.RISK_DEFAULT_SOURCE="real";'
        assert client.get('/api/health',headers={'X-Data-Source':'bad'}).status_code==400
        pairs=[exercise(client,app,s,conn) for s,conn in conns.items()]
        expected={(method,r.rule) for r in app.url_map.iter_rules() if r.rule.startswith('/api/')
                  for method in (r.methods-{'HEAD','OPTIONS'})}
        expected.add(('OPTIONS','/api/<path:rest>'))
        for _,routes in pairs:
            assert routes==expected,expected^routes
        left,right=pairs[0][0],pairs[1][0]
        assert left.keys()==right.keys()
        for key in left:
            compare(left[key],right[key],str(key))
        print(f'{len(expected)} methods/routes, {len(left)} paired response checks, both sources')
