"""Run against the managed demo database; all test writes are rolled back or explicitly removed."""
import io
import os
import pytest
from backend.app import create_app
from backend.db import connect,query,one,execute
from backend.validation import validate


@pytest.fixture(scope='module')
def client():
    if os.getenv('DB_NAME','risk_alert_demo') not in ('risk_alert_demo','risk_alert_test'):
        pytest.fail('Integration tests only permit managed demo/test databases')
    app=create_app();app.config['TESTING']=True
    return app.test_client()


def token(client,user='analyst1'):
    r=client.post('/api/login',json={'username':user,'password':'123456'})
    assert r.status_code==200,r.json
    return {'Authorization':'Bearer '+r.json['data']['token']}


def test_real_database_constraints_and_diversity():
    c=connect()
    try:
        result=validate(c)
        assert not result['errors'],result
        assert 50000<=result['business_rows']<=100000
        assert len(result['region_diversity'])==12
    finally:c.close()


def test_read_contracts_and_privileges(client):
    analyst=token(client)
    for path in ['/api/dicts','/api/overview','/api/region-risk','/api/clues','/api/batches','/api/features','/api/versions','/api/eval/confusion','/api/eval/samples','/api/eval/labels','/api/audit','/api/cases','/api/health','/api/risk-map','/api/person-risks','/api/risk-trends?area_id=A02','/api/data']:
        r=client.get(path,headers=analyst)
        assert r.status_code==200,(path,r.json)
        assert r.json['code']==0
    no=client.get('/api/clues');assert no.status_code==401
    teacher=token(client,'teacher')
    assert client.post('/api/batches',headers=teacher,json={}).status_code==403
    dataop=token(client,'dataop')
    assert client.get('/api/clues',headers=dataop).status_code==403
    assert client.get('/api/data/persons',headers=dataop).status_code==200


def test_feedback_state_and_snapshot(client):
    headers=token(client)
    clue=client.get('/api/clues?status=0&size=1',headers=headers).json['data']['list'][0]
    cid=clue['clue_id'];sid=clue['score_id']
    before=client.get(f'/api/scores/{sid}/features',headers=headers).json['data']
    chain=client.get(f'/api/clues/{cid}/chain',headers=headers)
    assert chain.status_code==200 and chain.json['data']['chains']
    c=connect()
    try:
        assert client.patch(f'/api/clues/{cid}/status',json={'status':1},headers=headers).status_code==200
        bad=client.post(f'/api/clues/{cid}/feedback',json={'check_result':2,'check_method':3,'check_remark':'测试非法特征','wrong_feature_ids':['INVENTED']},headers=headers)
        assert bad.status_code==400
        r=client.post(f'/api/clues/{cid}/feedback',json={'check_result':2,'check_method':3,'check_remark':'集成测试：独立记录不足，暂排除','wrong_feature_ids':[]},headers=headers)
        assert r.status_code==201,r.json
        assert client.get(f'/api/clues/{cid}',headers=headers).json['data']['clue']['clue_status']==3
        assert client.post(f'/api/clues/{cid}/feedback',json={'check_result':1,'check_method':1,'check_remark':'重复提交'},headers=headers).status_code==409
        assert client.get(f'/api/scores/{sid}/features',headers=headers).json['data']==before
    finally:
        # Restore only the specific test feedback/state, leaving application data intact.
        execute("DELETE FROM clue_feedback WHERE clue_id=%s AND check_remark=%s",(cid,'集成测试：独立记录不足，暂排除'),c)
        execute('UPDATE risk_clue SET clue_status=0,close_at=NULL,assignee_id=NULL WHERE clue_id=%s',(cid,),c)
        c.commit();c.close()


def test_atomic_import_and_crud(client):
    h=token(client,'dataop')
    row={'person_id':'PTEST900','person_name':'课程测试记录','gender':0,'birth_year':1998,'home_area_id':'A01','person_type':3}
    try:
        r=client.post('/api/data/persons',headers=h,json=row);assert r.status_code==201,r.json
        assert client.patch('/api/data/persons/PTEST900',headers=h,json={'person_name':'已更正'}).status_code==200
        assert client.get('/api/data/persons/PTEST900',headers=h).json['data']['person_name']=='已更正'
        content='person_id,person_name,gender,home_area_id,person_type\nPTEST901,导入第一行,0,A01,3\nPTEST902,导入非法行,0,NO_SUCH_AREA,3\n'
        r=client.post('/api/data/persons/imports',headers=h,data={'file':(io.BytesIO(content.encode()),'test.csv')})
        assert r.status_code==409,r.json
        assert client.get('/api/data/persons/PTEST901',headers=h).status_code==404
        assert client.delete('/api/data/areas/A01',headers=h).status_code==409
    finally:
        assert client.delete('/api/data/persons/PTEST900',headers=h).status_code==200


def test_eval_does_not_expand_batches(client):
    h=token(client)
    report=client.get('/api/eval/confusion',headers=h).json['data']
    detail=client.get('/api/eval/samples?size=200',headers=h).json['data']
    assert sum(report[k] for k in ('tp','fp','fn','tn'))+report['missing_count']==report['sample_total']
    assert report['sample_total']==detail['sample_total']==detail['joined_total']
    assert detail['result_counts']=={k:report[k] for k in ('tp','fp','fn','tn')}


def test_logout_revokes_session(client):
    h=token(client,'teacher')
    assert client.delete('/api/auth/sessions/current',headers=h).status_code==200
    assert client.get('/api/overview',headers=h).status_code==401


def test_people_peak_recommendations_and_partial_search(client):
    h=token(client)
    peak=client.get('/api/person-risks?mode=peak&size=3',headers=h).json['data']
    assert peak['mode']=='peak' and len(peak['list'])==3
    assert all(r['risk_level']==3 and r['total_score']>=70 for r in peak['list'])
    c=connect()
    try:
        for r in peak['list']:
            assert float(one('SELECT MAX(total_score) n FROM risk_score WHERE person_id=%s',(r['person_id'],),c)['n'])==r['total_score']
    finally:c.close()
    partial=client.get('/api/person-risks?q=P001',headers=h).json['data']
    assert partial['total']>0 and all('P001' in r['person_id'] for r in partial['list'])
    assert client.get('/api/person-risks?q=NO_SUCH_PERSON',headers=h).json['data']['total']==0
    assert client.get('/api/person-risks?mode=unknown',headers=h).status_code==400


def test_evidence_discovery_scope_dedup_and_access(client):
    h=token(client)
    subjects=client.get('/api/evidence/subjects?scope=area&q=A02',headers=h).json['data']
    assert subjects['total']==1
    events=client.get('/api/evidence/events?scope=area&area_id=A02&size=200',headers=h).json['data']
    assert events['total']==subjects['list'][0]['event_count']>1
    assert len({r['episode_key'] for r in events['list']})==len(events['list'])
    assert all(r['area_id']=='A02' and r['object_type']==1 for r in events['list'])
    persons=client.get('/api/evidence/events?scope=person&person_id=P0277',headers=h).json['data']
    assert persons['total']>1 and all(r['person_id']=='P0277' for r in persons['list'])
    assert client.get('/api/evidence/events?scope=person',headers=h).status_code==400
    assert client.get('/api/evidence/subjects?scope=invalid',headers=h).status_code==400
    assert client.get('/api/evidence/subjects?scope=area&from=2026-11-02&to=2026-11-01',headers=h).status_code==400
    assert client.get('/api/evidence/subjects',headers=token(client,'dataop')).status_code==403


def test_no_activity_is_not_a_source_outage(client):
    h=token(client)
    result=client.get('/api/risk-map',headers=h).json['data']
    hour=next(r for r in result['risk'] if r['date']=='2026-11-05 10:00:00')
    assert len(hour['areas'])==12
    assert all(r['sample_size']==0 and r['data_coverage']==1 for r in hour['areas'])
    assert all(r['total_score'] is None and r['risk_status']=='no_activity' for r in hour['areas'])
    score=client.get(f"/api/scores/{hour['areas'][0]['score_id']}/features",headers=h).json['data']['score']
    assert score['risk_status']=='no_activity' and score['status_reason']


def test_batch_run_retry_preserves_reviewed_snapshot(client):
    feature=token(client,'featop');analyst=token(client)
    bid='BTEST_RUN_RETRY'
    c=connect()
    try:
        r=client.post('/api/batches',headers=feature,json=dict(batch_id=bid,rule_id='R001',area_id='A02',data_start='2026-11-24 00:00:00',data_end='2026-11-25 00:00:00'))
        assert r.status_code==201,r.json
        r=client.post(f'/api/batches/{bid}/runs',headers=feature)
        assert r.status_code==201 and r.json['data']['object_cnt']==24,r.json
        assert client.post(f'/api/batches/{bid}/runs',headers=feature).status_code==409
        c.rollback()
        clue=one('SELECT * FROM risk_clue WHERE batch_id=%s LIMIT 1',(bid,),c)
        assert clue
        before=client.get(f"/api/scores/{clue['score_id']}/features",headers=analyst).json['data']
        r=client.post(f"/api/clues/{clue['clue_id']}/feedback",headers=analyst,json={'check_result':2,'check_method':3,'check_remark':'批次重试保护测试','wrong_feature_ids':[]})
        assert r.status_code==201,r.json
        # Simulate a retryable batch left by an interrupted external scheduler.
        execute('UPDATE judge_batch SET run_status=3 WHERE batch_id=%s',(bid,),c);c.commit()
        r=client.post(f'/api/batches/{bid}/runs',headers=feature)
        assert r.status_code==201 and r.json['data']['skipped_cnt']>0,r.json
        assert client.get(f"/api/scores/{clue['score_id']}/features",headers=analyst).json['data']==before
    finally:
        c.rollback()
        execute('DELETE FROM clue_feedback WHERE clue_id IN (SELECT clue_id FROM risk_clue WHERE batch_id=%s)',(bid,),c)
        execute('DELETE FROM clue_chain WHERE clue_id IN (SELECT clue_id FROM risk_clue WHERE batch_id=%s)',(bid,),c)
        execute('DELETE FROM risk_clue WHERE batch_id=%s',(bid,),c)
        execute('DELETE FROM risk_score_feature WHERE score_id IN (SELECT score_id FROM risk_score WHERE batch_id=%s)',(bid,),c)
        execute('DELETE FROM risk_score WHERE batch_id=%s',(bid,),c)
        execute('DELETE FROM judge_batch WHERE batch_id=%s',(bid,),c)
        c.commit();c.close()


def test_draft_statistics_publish_and_execution(client):
    feat=token(client,'featop');analyst=token(client)
    vid='VTEST_REVIEW_01';bid='BTEST_REVIEW_01'
    c=connect();original=one('SELECT version_id,baseline_json FROM feature_version WHERE publish_status=1',conn=c)
    feedback_id=None
    target=one('SELECT * FROM risk_clue WHERE clue_status=0 LIMIT 1',conn=c)
    c.rollback()
    try:
        fs=client.get(f"/api/scores/{target['score_id']}/features",headers=analyst).json['data']['features']
        wrong=next(f['feature_id'] for f in fs if f['is_hit']==1)
        r=client.post(f"/api/clues/{target['clue_id']}/feedback",headers=analyst,json={'check_result':2,'check_method':3,'check_remark':'版本学习测试','wrong_feature_ids':[wrong]})
        assert r.status_code==201,r.json
        feedback_id=r.json['data']['feedback_id']
        r=client.post('/api/data/versions',headers=feat,json={'version_id':vid,'version_no':'test-review','remark':'版本回归测试'})
        assert r.status_code==201,r.json
        r=client.post('/api/weights/recalc',headers=feat,json={'version_id':vid})
        assert r.status_code==200 and r.json['data']['feedback_factor_cnt']>=1,r.json
        r=client.post('/api/weights/recalc',headers=feat,json={'version_id':vid})
        assert r.status_code==200 and r.json['data']['changed_cnt']==0,r.json
        c.rollback()
        assert one('SELECT baseline_json FROM feature_version WHERE version_id=%s',(original['version_id'],),c)['baseline_json']==original['baseline_json']
        rule=one('SELECT rule_id FROM judge_rule WHERE version_id=%s AND judge_object=1',(vid,),c)
        assert rule
        r=client.patch(f'/api/versions/{vid}/publish',headers=feat,json={'publish_status':1});assert r.status_code==200,r.json
        r=client.post('/api/batches',headers=feat,json={'batch_id':bid,'rule_id':rule['rule_id'],'area_id':'A02','data_start':'2026-11-24 20:00:00','data_end':'2026-11-24 21:00:00'})
        assert r.status_code==201,r.json
        r=client.post(f'/api/batches/{bid}/runs',headers=feat)
        assert r.status_code==201 and r.json['data']['object_cnt']==1,r.json
    finally:
        c.rollback()
        execute('DELETE FROM clue_chain WHERE clue_id IN (SELECT clue_id FROM risk_clue WHERE batch_id=%s)',(bid,),c)
        execute('DELETE FROM risk_clue WHERE batch_id=%s',(bid,),c)
        execute('DELETE FROM risk_score_feature WHERE score_id IN (SELECT score_id FROM risk_score WHERE batch_id=%s)',(bid,),c)
        execute('DELETE FROM risk_score WHERE batch_id=%s',(bid,),c)
        execute('DELETE FROM judge_batch WHERE batch_id=%s',(bid,),c)
        execute('UPDATE feature_version SET publish_status=0 WHERE version_id=%s',(vid,),c)
        execute('UPDATE feature_version SET publish_status=1 WHERE version_id=%s',(original['version_id'],),c)
        execute('DELETE FROM rule_feature WHERE rule_id IN (SELECT rule_id FROM judge_rule WHERE version_id=%s)',(vid,),c)
        execute('DELETE FROM judge_rule WHERE version_id=%s',(vid,),c)
        execute('DELETE FROM feature_weight WHERE version_id=%s',(vid,),c)
        execute('DELETE FROM version_feedback WHERE version_id=%s',(vid,),c)
        execute('DELETE FROM feature_version WHERE version_id=%s',(vid,),c)
        if feedback_id:
            execute('DELETE FROM clue_feedback WHERE feedback_id=%s',(feedback_id,),c)
            execute('UPDATE risk_clue SET clue_status=%s,close_at=%s,assignee_id=%s WHERE clue_id=%s',(target['clue_status'],target['close_at'],target['assignee_id'],target['clue_id']),c)
        c.commit();c.close()
