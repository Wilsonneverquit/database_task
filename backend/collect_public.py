"""Collect a bounded, attributable public release. No database side effects."""
import csv
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .db import ROOT

OUT = ROOT / 'data' / 'public'
FSA = 'https://ratings.food.gov.uk/api/open-data-files/FHRS027en-GB.xml'
RIDES = ('https://data.mendeley.com/public-files/datasets/wp5gkjbvb9/files/'
         'a9f71dee-1b26-4008-a3f1-a79f48d320ca/file_downloaded')
TX = 'https://data.texas.gov/resource/g5bj-yb6k.json?' + urlencode({
    '$select': 'obligation_end_date,count(*) as reports,sum(total_sales_receipts) as sales_usd',
    '$where': "location_city='AUSTIN' AND location_state='TX' AND obligation_end_date between '2016-06-01' and '2016-09-30T23:59:59'",
    '$group': 'obligation_end_date', '$order': 'obligation_end_date'})
PREFIX_BYTES = 1048576
CN = timezone(timedelta(hours=8))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(url, *, prefix=False):
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / 'source'
        args = ['curl.exe' if os.name == 'nt' else 'curl', '-fsSL', '--retry', '2',
                '--max-time', '110', '--max-filesize', str(PREFIX_BYTES if prefix else 8000000)]
        if prefix:
            args += ['--range', f'0-{PREFIX_BYTES - 1}']
        subprocess.run([*args, '-o', str(dest), url], check=True)
        raw = dest.read_bytes()
    if not raw or (prefix and len(raw) != PREFIX_BYTES):
        raise ValueError('Incomplete public download')
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    # Immutable raw cache, excluded from version control. Retain public bytes only.
    cache = ROOT / '.runtime' / 'public-raw'
    cache.mkdir(parents=True, exist_ok=True)
    (cache / sha(raw)).write_bytes(raw)
    return raw, dict(url=url, retrieved_utc=stamp, bytes=len(raw), sha256=sha(raw))


def cambridge(raw):
    doc = ET.fromstring(raw)
    records = doc.findall('./EstablishmentCollection/EstablishmentDetail')
    if len(records) != int(doc.findtext('./Header/ItemCount')) or doc.findtext('./Header/ReturnCode') != 'Success':
        raise ValueError('FSA source count or status mismatch')
    street_pattern = re.compile(r"\d+[A-Za-z]?(?:\s*(?:-|to|and)\s*\d+[A-Za-z]?)?\s+([A-Za-z][A-Za-z .'’\-]*(?:Street|Road|Lane|Avenue|Parade|Place|Square|Terrace|Hill|Walk|Way|Drive|Court|Broadway))", re.I)
    coords, names, places = defaultdict(list), {}, {}
    stats = Counter()
    for row in records:
        if row.findtext('LocalAuthorityCode') != '027':
            raise ValueError('Unexpected FSA authority')
        kind = {'1': 1, '7843': 3}.get(row.findtext('BusinessTypeID'))
        if not kind:
            stats['other_category'] += 1
            continue
        addr = [' '.join((row.findtext(f'AddressLine{i}') or '').split()) for i in range(1, 5)]
        matches = [street_pattern.fullmatch(line) for line in addr]
        match = next((m for m in matches if m), None)
        lng, lat = row.findtext('Geocode/Longitude'), row.findtext('Geocode/Latitude')
        if not match or not lng or not lat or not (0 < float(lng) < 0.25 and 52.1 < float(lat) < 52.3):
            stats['no_unambiguous_urban_street_or_coordinates'] += 1
            continue
        street = match[1].strip().replace('’', "'").title()
        aid = 'CB' + sha(street.casefold().encode())[:10]
        pid = 'FH' + row.findtext('FHRSID')
        name = ' '.join((row.findtext('BusinessName') or '').split())
        address = ', '.join(filter(None, addr))
        if not name or len(name)>80 or len(address)>200 or len(street)>60 or len(pid)>16:
            stats['field_limits'] += 1
            continue
        item = dict(place_id=pid, place_name=name, place_type=kind, area_id=aid, address=address)
        if pid in places:
            if places[pid] != item:
                raise ValueError('Conflicting FHRSID')
            stats['duplicates'] += 1
            continue
        if aid in names and names[aid] != street:
            raise ValueError('Street ID collision')
        names[aid] = street
        coords[aid].append((float(lng), float(lat)))
        places[pid] = item
    areas = [dict(area_id=k, area_name=names[k], area_type=1,
                  lng=round(sum(x for x,_ in points)/len(points),6),
                  lat=round(sum(y for _,y in points)/len(points),6)) for k,points in sorted(coords.items())]
    if not places:
        raise ValueError('No eligible venues')
    return areas, list(places.values()), dict(input=len(records), excluded=dict(stats), extract_date=doc.findtext('./Header/ExtractDate'))


def ride_sample(raw):
    # This archive CSV has one physical line per ride. Discard the incomplete last line.
    reader = csv.DictReader(io.StringIO(raw[:raw.rindex(b'\n')+1].decode('utf-8-sig')), strict=True)
    people, orders, stats = {}, {}, Counter()
    for r in reader:
        stats['input'] += 1
        if not all((r.get(k) or '').isdigit() for k in ('RIDE_ID','rider_id')):
            stats['bad_key'] += 1
            continue
        try:
            coords = [(float(r[f'{side}_location_lat']), float(r[f'{side}_location_long'])) for side in ('start','end')]
            if not all(30.0<=lat<=30.6 and -98.1<=lng<=-97.4 for lat,lng in coords):
                stats['outside_austin_sample_box'] += 1
                continue
            times = [datetime.fromisoformat(r[k]) for k in ('created_date','started_on','completed_on','updated_date')]
            if not all(t.tzinfo for t in times) or times != sorted(times):
                raise ValueError()
        except (ValueError,TypeError):
            stats['incomplete_or_invalid'] += 1
            continue
        pid, oid = 'RA'+r['rider_id'], 'RA'+r['RIDE_ID']
        if len(pid)>16 or len(oid)>32:
            stats['bad_key'] += 1
            continue
        start, _, end, updated = [t.astimezone(CN).strftime('%Y-%m-%d %H:%M:%S') for t in times]
        item = dict(order_no=oid, person_id=pid, order_type=1, order_status=1, order_time=start,
                    completed_at=end, recorded_at=updated, start_area_id=None, end_area_id=None)
        if oid in orders:
            if orders[oid] != item:
                raise ValueError('Conflicting RIDE_ID')
            stats['duplicates'] += 1
            continue
        people[pid] = dict(person_id=pid, person_name='匿名乘客 '+pid, person_type=3)
        orders[oid] = item
    if not orders:
        raise ValueError('No eligible rides')
    return list(people.values()), list(orders.values()), dict(stats)


def main():
    venues, fsa = fetch(FSA)
    rides, archive = fetch(RIDES, prefix=True)
    receipts, tx = fetch(TX)
    areas, places, fs = cambridge(venues)
    persons, orders, rs = ride_sample(rides)
    months = json.loads(receipts)
    if len(months)!=4 or [r['obligation_end_date'][:7] for r in months] != [f'2016-{m:02d}' for m in range(6,10)]:
        raise ValueError('Unexpected Texas reporting periods')
    for r in months:
        if int(r['reports'])<=0 or float(r['sales_usd'])<0:
            raise ValueError('Invalid receipts summary')
    bundle = dict(area_info=areas, place_info=places, person_info=persons, taxi_order=orders, receipt_summary=months)
    payload = gzip.compress(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode(), mtime=0)
    digest = sha(payload)
    manifest = dict(format=1, snapshot_sha256=digest, counts={k:len(v) for k,v in bundle.items()},
        sources=[
            dict(**fsa, publisher='Food Standards Agency / Cambridge City', license='Open Government Licence',
                 terms='https://ratings.food.gov.uk/terms-and-conditions', tables=['area_info','place_info'], selection=fs),
            dict(**archive, publisher='RideAustin; Zuniga-Garcia et al., Mendeley Data v1', license='CC0 1.0',
                 terms='https://data.mendeley.com/datasets/wp5gkjbvb9/1', tables=['person_info','taxi_order'],
                 selection=rs, byte_range=f'0-{PREFIX_BYTES-1}'),
            dict(**tx, publisher='Texas Comptroller of Public Accounts', license='Public Domain',
                 terms='https://data.texas.gov/dataset/g5bj-yb6k', tables=['data_quality_report'], selection='Austin TX, Jun–Sep 2016, month totals only')])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (digest+'.json.gz')).write_bytes(payload)
    temp = OUT / 'manifest.tmp'
    temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(OUT/'manifest.json')
    print(json.dumps(manifest['counts']))


if __name__=='__main__':
    main()
