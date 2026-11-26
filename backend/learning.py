"""Historical statistics and reviewed feedback enter a new draft, never rewrite history."""
import json
import math
from .db import query,one,execute,insert,audit
from .engine import build_baseline,load_events
from .scoring import dt,match_episode
from datetime import timedelta


def recalculate(conn,version_id,user):
    version=one('SELECT * FROM feature_version WHERE version_id=%s FOR UPDATE',(version_id,),conn)
    if not version:raise ValueError('版本不存在')
    if version['publish_status']!=0:raise ValueError('只允许重算草稿；已发布与归档版本保持冻结')
    cutoff=dt(one("SELECT param_value FROM param_config WHERE param_key='history_cutoff'",conn=conn)['param_value'])
    cases=query('SELECT * FROM v_case_history WHERE created_at<%s',(cutoff,),conn)
    controls=query('SELECT * FROM control_person WHERE sample_date<%s',(cutoff,),conn)
    earliest=min([c['occur_time'] for c in cases]+[cutoff])-timedelta(hours=3)
    cons,tracks,orders,evidence=load_events(conn,earliest,cutoff)
    by_person={};by_track={};by_order={}
    for c in cons:by_person.setdefault(c['person_id'],[]).append(c)
    for t in tracks:by_track.setdefault(t['owner_person_id'],[]).append(t)
    for o in orders:by_order.setdefault(o['person_id'],[]).append(o)
    def hit(pid,area,t):
        mine=[c for c in by_person.get(pid,[]) if t-timedelta(hours=3)<=c['consume_time']<t]
        alc=[c for c in mine if c['has_alcohol']]
        e=match_episode(mine,by_track.get(pid,[]),by_order.get(pid,[]),evidence,t) if mine else None
        # Current case excluded: only strictly earlier records, also before global cutoff.
        prior=sum(c['person_id']==pid and t-timedelta(days=90)<=c['occur_time']<t and c['created_at']<t for c in cases)
        venues={c['place_id'] for c in cons if c['area_id']==area and c['has_alcohol'] and t-timedelta(hours=1)<=c['consume_time']<t}
        return {'F001':len(venues)>=2,'F002':bool(alc),'F003':bool(alc) and not(e and e['safe']),
                'F004':bool(e and e['track']),'F005':bool(e and e['track'] and alc),'F006':bool(e and e['safe']),'F008':prior>0}
    case_hits={k:0 for k in ('F001','F002','F003','F004','F005','F006','F008')};ctrl_hits=dict(case_hits)
    for c in cases:
        h=hit(c['person_id'],c['area_id'],c['occur_time'])
        for k in case_hits:case_hits[k]+=int(h[k])
    for c in controls:
        t=dt(str(c['sample_date']))+timedelta(hours=c['hour_slot'])
        h=hit(c['person_id'],c['area_id'],t)
        for k in ctrl_hits:ctrl_hits[k]+=int(h[k])
    previous={r['feature_id']:float(r['weight']) for r in query('SELECT feature_id,weight FROM feature_weight WHERE version_id=%s',(version_id,),conn)}
    execute('DELETE FROM feature_weight WHERE version_id=%s',(version_id,),conn)
    changed=0
    for k,a in case_hits.items():
        c=ctrl_hits[k];n1=len(cases);n0=len(controls)
        w=min(3,max(-3,round(math.log(((a+.5)/(n1-a+.5))/((c+.5)/(n0-c+.5))),4)))
        changed+=int(previous.get(k)!=w)
        insert('feature_weight',dict(version_id=version_id,feature_id=k,case_hit=a,case_total=n1,ctrl_hit=c,ctrl_total=n0,weight=w,is_valid=int(n1>=5 and n0>=5)),conn)
    # Feedback discounts are tracked per draft using a junction, not a global boolean only.
    feedbacks=query('SELECT x.feature_id,COUNT(*) n FROM clue_feedback_feature x JOIN clue_feedback f USING(feedback_id) WHERE f.check_result=2 AND x.is_wrong=1 GROUP BY x.feature_id',conn=conn)
    baseline=build_baseline(conn,cutoff)
    baseline['reviewed_negations']={r['feature_id']:r['n'] for r in feedbacks}
    execute('INSERT IGNORE INTO version_feedback(version_id,feedback_id) SELECT %s,f.feedback_id FROM clue_feedback f WHERE f.check_result=2 AND EXISTS(SELECT 1 FROM clue_feedback_feature x WHERE x.feedback_id=f.feedback_id AND x.is_wrong=1)',(version_id,),conn)
    execute('UPDATE clue_feedback f JOIN version_feedback v USING(feedback_id) SET f.weight_applied=1 WHERE v.version_id=%s',(version_id,),conn)
    execute('UPDATE feature_version SET baseline_json=%s,based_case_cnt=%s,based_ctrl_cnt=%s,calc_at=NOW() WHERE version_id=%s',(json.dumps(baseline),len(cases),len(controls),version_id),conn)
    # Clone the published rules once; reduce disproved factors and renormalize in the draft.
    originals=query('SELECT r.* FROM judge_rule r JOIN feature_version v ON v.version_id=r.version_id WHERE v.publish_status=1',conn=conn)
    for r in originals:
        rid=('D'+str(version_id)[-10:]+str(r['judge_object']))[:16]
        cfg=json.loads(r['config_json'])
        weights=[(f,float(w)/(1+.05*baseline['reviewed_negations'].get(f,0))) for f,w in cfg['weights']]
        total=sum(w for f,w in weights)
        cfg={'weights':[[f,w/total] for f,w in weights],'version_id':version_id}
        existing=one('SELECT rule_id FROM judge_rule WHERE rule_id=%s',(rid,),conn)
        if existing:
            execute('UPDATE judge_rule SET config_json=%s WHERE rule_id=%s',(json.dumps(cfg),rid),conn)
        else:
            insert('judge_rule',dict(rule_id=rid,rule_name=r['rule_name']+'·反馈修订',version_id=version_id,judge_object=r['judge_object'],min_sample=r['min_sample'],min_hit_cnt=r['min_hit_cnt'],low_threshold=r['low_threshold'],high_threshold=r['high_threshold'],counter_block=r['counter_block'],config_json=json.dumps(cfg)),conn)
            for i,(f,w) in enumerate(weights):insert('rule_feature',dict(rule_id=rid,feature_id=f,sort_no=i),conn)
    audit(user,'feature_version',version_id,f'草稿统计重算，历史案件 {len(cases)}，对照 {len(controls)}；反馈因子修订 {len(feedbacks)}',4,conn)
    return dict(version_id=version_id,feature_cnt=len(case_hits),changed_cnt=changed,feedback_factor_cnt=len(feedbacks))
