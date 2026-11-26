from datetime import datetime,timedelta
from backend.scoring import index_score,decay,episodes,match_episode


def test_continuous_monotonic_and_decay():
    weights=[('a',.5),('b',.5)]
    low=index_score({'a':.1,'b':.4},weights,{'a':1,'b':1})
    high=index_score({'a':.8,'b':.4},weights,{'a':1,'b':1})
    assert low['total_score']<high['total_score']
    assert decay(10)>decay(90)>decay(180)>0
    assert high['total_score']==round(sum(x['contribution'] for x in high['features']),2)


def test_missing_and_counterexample():
    weights=[('a',.5),('b',.5)]
    assert index_score({'a':1,'b':None},weights,{})['total_score'] is None
    x=index_score({'a':1,'b':1},weights,{},safe_ride=True)
    assert x['total_score']==65 and x['blocked']==1


def sample():
    t=datetime(2026,11,7,23,30)
    c=dict(person_id='P1',area_id='A01',consume_id=1,consume_time=t,recorded_at=t,has_alcohol=1)
    tr=dict(track_id=1,owner_person_id='P1',area_id='A01',direction=2,pass_time=t+timedelta(minutes=40),recorded_at=t+timedelta(minutes=41))
    return t,c,tr


def test_cross_midnight_ownership_and_future_evidence():
    t,c,tr=sample();end=t+timedelta(hours=2)
    e=match_episode([c],[tr],[],{},end)
    assert e['track']==tr and not e['confirmed']
    assert match_episode([c],[tr],[],{},t+timedelta(minutes=20))['track'] is None
    evidence={1:dict(person_id='P2',recorded_at=t)}
    assert not match_episode([c],[tr],[],evidence,end)['confirmed']


def test_cancelled_and_previous_ride_do_not_block():
    t,c,tr=sample();end=t+timedelta(hours=2)
    order=dict(person_id='P1',order_status=2,completed_at=None,order_time=t,recorded_at=t,start_area_id='A01')
    assert not match_episode([c],[tr],[order],{},end)['safe']
    order.update(order_status=1,completed_at=t+timedelta(minutes=15))
    assert not match_episode([c],[tr],[order],{},end)['safe']
    order.update(completed_at=t+timedelta(minutes=60))
    assert match_episode([c],[tr],[order],{},end)['safe']


def test_episode_people_and_gap():
    t,c,tr=sample()
    other=dict(c,person_id='P2',consume_id=2)
    later=dict(c,consume_id=3,consume_time=t+timedelta(minutes=100))
    assert len(episodes([later,c,other]))==3


def test_borrowed_vehicle_requires_independent_driver_observation():
    t,c,tr=sample();end=t+timedelta(hours=2)
    tr['owner_person_id']='OTHER_OWNER'
    assert match_episode([c],[tr],[],{},end)['track'] is None
    evidence={1:dict(person_id='P1',recorded_at=t+timedelta(minutes=45))}
    result=match_episode([c],[tr],[],evidence,end)
    assert result['track']==tr and result['confirmed']
