from .db import query,one


def validate(conn):
    checks={
      'orphan_consumers': 'SELECT COUNT(*) n FROM consume_record c LEFT JOIN person_info p USING(person_id) WHERE p.person_id IS NULL',
      'case_time_boundary': "SELECT COUNT(*) n FROM case_info WHERE occur_time>=(SELECT CAST(param_value AS DATETIME) FROM param_config WHERE param_key='history_cutoff')",
      'order_completion': 'SELECT COUNT(*) n FROM taxi_order WHERE (order_status=1 AND completed_at IS NULL) OR (completed_at<order_time) OR (recorded_at<COALESCE(completed_at,order_time))',
      'gate_region': "SELECT COUNT(*) n FROM vehicle_track WHERE area_id<>SUBSTRING_INDEX(gate_id,'-',1)",
      'source_time_order': 'SELECT COUNT(*) n FROM consume_record WHERE recorded_at<consume_time',
      'score_reproduction': '''SELECT COUNT(*) n FROM risk_score s JOIN (SELECT score_id,ROUND(LEAST(100,GREATEST(0,SUM(contribution))),2) score FROM risk_score_feature GROUP BY score_id) f USING(score_id) WHERE s.total_score IS NOT NULL AND ABS(s.total_score-f.score)>.01''',
      'future_chain_source': '''SELECT COUNT(*) n FROM chain_node n JOIN clue_chain c USING(chain_id) LEFT JOIN consume_record x USING(consume_id) LEFT JOIN vehicle_track t USING(track_id) LEFT JOIN taxi_order o USING(order_id) WHERE x.recorded_at>=c.snapshot_at OR t.recorded_at>=c.snapshot_at OR o.recorded_at>=c.snapshot_at''',
      'cross_person_chain': '''SELECT COUNT(*) n FROM chain_node n JOIN clue_chain c USING(chain_id) LEFT JOIN consume_record x USING(consume_id) LEFT JOIN vehicle_track t USING(track_id) LEFT JOIN vehicle_owner v ON v.vehicle_id=t.vehicle_id LEFT JOIN driver_evidence d ON d.track_id=t.track_id AND d.recorded_at<c.snapshot_at LEFT JOIN taxi_order o USING(order_id) WHERE (x.person_id<>c.person_id) OR (o.person_id<>c.person_id) OR (v.owner_person_id<>c.person_id AND (d.person_id IS NULL OR d.person_id<>c.person_id))''',
      'closed_clue_time': 'SELECT COUNT(*) n FROM risk_clue WHERE (clue_status IN (2,3))<>(close_at IS NOT NULL)',
      'batch_counts': '''SELECT COUNT(*) n FROM judge_batch b WHERE run_status=2 AND (object_cnt<>(SELECT COUNT(*) FROM risk_score s WHERE s.batch_id=b.batch_id) OR clue_cnt<>(SELECT COUNT(*) FROM risk_clue c WHERE c.batch_id=b.batch_id))''',
    }
    values={k:one(sql,conn=conn)['n'] for k,sql in checks.items()}
    diversity=query('SELECT area_id,COUNT(DISTINCT total_score) distinct_scores,MIN(total_score) minimum,MAX(total_score) maximum FROM risk_score WHERE object_type=1 GROUP BY area_id',conn=conn)
    if any(r['distinct_scores']<10 for r in diversity):values['insufficient_diversity']=1
    # Check every inter-region arrival against the preceding departure, not just legal ranges.
    route=query('''WITH movements AS (SELECT vehicle_id,area_id,direction,pass_time,LAG(area_id) OVER(PARTITION BY vehicle_id ORDER BY pass_time,track_id) previous_area,LAG(direction) OVER(PARTITION BY vehicle_id ORDER BY pass_time,track_id) previous_direction,LAG(pass_time) OVER(PARTITION BY vehicle_id ORDER BY pass_time,track_id) previous_time FROM vehicle_track) SELECT COUNT(*) n FROM movements WHERE direction=1 AND previous_direction=2 AND previous_area<>area_id AND TIMESTAMPDIFF(MINUTE,previous_time,pass_time)<15''',conn=conn)
    values['impossible_vehicle_travel']=route[0]['n']
    volume=one('SELECT (SELECT COUNT(*) FROM consume_record)+(SELECT COUNT(*) FROM taxi_order)+(SELECT COUNT(*) FROM vehicle_track) n',conn=conn)['n']
    return dict(checks=values,errors=[k for k,v in values.items() if v],business_rows=volume,region_diversity=diversity)
