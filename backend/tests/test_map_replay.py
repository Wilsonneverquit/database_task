from backend.app import create_app
from backend.map_replay import locate_node
from backend.db import one


def test_location_semantics():
    places={'P1':dict(area_id='A01',place_name='示例饭店')}
    assert locate_node(dict(node_type='consume'),dict(place_id='P1'),places)==('A01','示例饭店')
    assert locate_node(dict(node_type='track'),dict(area_id='A02',gate_id='A02-G01',direction=2),places)[0]=='A02'
    assert locate_node(dict(node_type='order'),dict(end_area_id=None),places)[0] is None
    for kind in ['gap','score','area_context']:
        assert locate_node(dict(node_type=kind),dict(area_id='A01'),places)[0] is None


def test_read_only_replay_contract():
    app=create_app()
    client=app.test_client()
    def auth(user):
        response=client.post('/api/login',json=dict(username=user,password='123456'))
        assert response.status_code==200
        return {'Authorization':'Bearer '+response.json['data']['token']}
    assert client.get('/api/map-replay/events').status_code==401
    dataop=auth('dataop')
    assert client.get('/api/map-replay/events',headers=dataop).status_code==403
    headers=auth('teacher')
    params=dict(size=200,**{'from':'2026-11-24 00:00:00','to':'2026-11-25 00:00:00'})
    response=client.get('/api/map-replay/events',query_string=params,headers=headers)
    assert response.status_code==200,response.json
    data=response.json['data'];rows=data['list']
    assert rows and data['total']>=len(rows)
    assert [r['event_at'] for r in rows]==sorted(r['event_at'] for r in rows)
    assert len({(r['person_id'],r['episode_key']) for r in rows})==len(rows)
    assert all(r['area_id'] and r['consume_id'] and r['event_at']>='2026-11-24' for r in rows)
    row=rows[0]
    filtered=client.get('/api/map-replay/events',query_string=params|dict(area_id=row['area_id'],person_id=row['person_id']),headers=headers).json['data']['list']
    assert filtered and all(r['area_id']==row['area_id'] and r['person_id']==row['person_id'] for r in filtered)
    detail=client.get(f"/api/map-replay/chains/{row['chain_id']}",headers=headers)
    assert detail.status_code==200,detail.json
    nodes=detail.json['data']['nodes']
    assert nodes and [n['event_at'] for n in nodes]==sorted(n['event_at'] for n in nodes)
    assert any(n['located'] and n['node_type']=='consume' for n in nodes)
    for n in nodes:
        if n['node_type'] in ['area_context','score','gap']: assert not n['located']
        if n['located']: assert n['area_id'] and n['lng'] is not None and n['lat'] is not None
        if n['source_record'] and n['source_record'].get('recorded_at'):
            assert n['source_record']['recorded_at']<detail.json['data']['chain']['snapshot_at']
    assert client.get(f"/api/map-replay/chains/{row['chain_id']}",headers=dataop).status_code==403
    assert client.get('/api/map-replay/chains/999999999',headers=headers).status_code==404
    assert client.get('/api/map-replay/events?from=2026-11-25&to=2026-11-24',headers=headers).status_code==400
    early=client.get('/api/map-replay/events?as_of=2026-10-01',headers=headers).json['data']
    assert early['total']==0
    with app.app_context():
        order=one("SELECT chain_id,node_id FROM chain_node WHERE node_type='order' ORDER BY node_id DESC LIMIT 1")
    assert order, '演示库应含订单证据节点'
    order_detail=client.get(f"/api/map-replay/chains/{order['chain_id']}",headers=headers).json['data']
    start_node=next(n for n in order_detail['nodes'] if n['event_id']==f"{order['node_id']}:start")
    end_node=next(n for n in order_detail['nodes'] if n['event_id']==str(order['node_id']))
    assert start_node['area_id']==start_node['source_record']['start_area_id']
    assert end_node['area_id']==end_node['source_record']['end_area_id']
    assert start_node['event_at']==start_node['source_record']['order_time']
    assert start_node['event_at']<=end_node['event_at']
