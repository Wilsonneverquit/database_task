"""Pure deterministic continuous scoring; all timestamps are naive Asia/Shanghai."""
import math
from datetime import datetime, timedelta

REGION = [('F001', .20), ('F002', .25), ('F004', .25), ('F003', .15), ('F008', .15)]
PERSON = [('F002', .25), ('F004', .30), ('F003', .15), ('F008', .15), ('F005', .15)]
NAMES = {'F001': '酒水场所集中度', 'F002': '近期酒水消费强度', 'F003': '缺少安全出行记录',
         'F004': '消费后关联车辆移动', 'F005': '消费与车辆时空匹配', 'F006': '同次行程安全出行反例', 'F008': '历史同类风险'}


def dt(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def decay(minutes):
    return math.exp(-max(0, minutes) / 90)


def percentile95(values):
    values = sorted(float(v) for v in values)
    return values[max(0, math.ceil(len(values) * .95) - 1)] if values else 1.0


def index_score(raw, weights, denominators, missing=(), safe_ride=False, min_sample=1, sample_size=1):
    details = []
    coverage = 0
    for fid, weight in weights:
        absent = fid in missing or raw.get(fid) is None
        value = raw.get(fid)
        denominator = max(float(denominators.get(fid, 1)), .0001)
        normalized = None if absent else min(1., max(0., float(value) / denominator))
        contribution = 0 if absent else round(100 * weight * normalized, 4)
        coverage += 0 if absent else weight
        details.append(dict(feature_id=fid, raw_value=value, normalized_value=normalized,
                            contribution=contribution, weight=weight, is_hit=int(not absent and normalized >= .2),
                            is_missing=int(absent), hit_value=value))
    if safe_ride:
        details.append(dict(feature_id='F006', raw_value=1, normalized_value=1, contribution=-35,
                            weight=-.35, is_hit=1, is_missing=0, hit_value=1))
    total = round(min(100, max(0, sum(x['contribution'] for x in details))), 2) if coverage >= .7 and sample_size >= min_sample else None
    return dict(total_score=total, data_coverage=round(coverage, 4), blocked=int(safe_ride),
                risk_level=None if total is None else (1 if total < 40 else 2 if total < 70 else 3), features=details)


def episodes(consumes):
    """Same person/area, <=90m gap; never merge merely spatially adjacent people."""
    grouped = {}
    for c in sorted(consumes, key=lambda x: (x['person_id'], x['consume_time'], x['consume_id'])):
        key = (c['person_id'], c['area_id'])
        previous = grouped.setdefault(key, [])
        if not previous or (c['consume_time'] - previous[-1][-1]['consume_time']).total_seconds() > 5400:
            previous.append([])
        previous[-1].append(c)
    return [e for groups in grouped.values() for e in groups]


def match_episode(consumes, tracks, orders, evidence, as_of):
    """Only records known strictly before as_of. Ownership is association, not driving."""
    first, last = consumes[0], consumes[-1]
    end = min(as_of, last['consume_time'] + timedelta(hours=3))
    def links_person(t):
        known=evidence.get(t['track_id'])
        if known and known['recorded_at'] < as_of:
            return known['person_id']==first['person_id']
        return t['owner_person_id']==first['person_id']
    matching = [t for t in tracks if links_person(t) and
                t['area_id'] == first['area_id'] and t['direction'] == 2 and
                last['consume_time'] <= t['pass_time'] < end and t['recorded_at'] < as_of]
    # Use the first departure, not any later trip in a broad time window.
    track = min(matching, key=lambda x: x['pass_time'], default=None)
    ride_end = track['pass_time'] if track else end
    safe = [o for o in orders if o['person_id'] == first['person_id'] and o['order_status'] == 1
            and o['completed_at'] is not None and last['consume_time'] <= o['order_time'] <= ride_end
            and o['completed_at'] < as_of and o['recorded_at'] < as_of
            and o['start_area_id'] == first['area_id']]
    # An order must belong to this journey. A finished earlier journey does not block a later departure.
    safe = [o for o in safe if track is None or o['order_time'] <= track['pass_time'] <= o['completed_at']]
    confirmed = bool(track and track['track_id'] in evidence and
                     evidence[track['track_id']]['person_id'] == first['person_id'] and
                     evidence[track['track_id']]['recorded_at'] < as_of)
    return {'consumes': consumes, 'track': track, 'orders': safe, 'confirmed': confirmed,
            'safe': bool(safe), 'key': f"{first['person_id']}:{first['consume_id']}", 'person_id': first['person_id'],
            'area_id': first['area_id'], 'first_at': first['consume_time']}
