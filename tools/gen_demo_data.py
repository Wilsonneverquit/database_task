#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risk_alert 示例库 · 数据扩充生成器
================================================================================
用途
    按《数据库设计思路方案》§6.1 的"以案生数 + 两段切分"流水线，把示例库从
    259 行扩充到约 3000 行，并同步生成前端 mock 种子的等价数据。

流水线（与设计文档一一对应）
    ① 主数据：区域 → 场所（挂区域）→ 人员（带 home_area）→ 车辆（挂人员）
    ② 造案件：历史段，按"区域 × 时段 × 日期类型"的风险分布抽样
    ③ 以案生痕迹：每起案件派生案发前的消费、有无出行订单、车辆驶出
    ④ 造对照：另选人 × 时段，只造普通流水，不写案件
    ⑤ 观察段：只造流水，把"埋在里面的案件"写进 eval_label
    ⑥ 特征统计：按 feature_def 的口径回看真实流水，算 P1/P0，再算权重
    ⑦ 研判：按 rule_feature + feature_weight 复刻研判引擎，产出评分与命中明细
    ⑧ 闭环：线索 → 核查反馈 → 触发器推进状态 → 被否定特征

设计原则
    · 派生值（P1/P0/lift、object_id、occur_hour、total_score、混淆矩阵）全部由
      最终数据复算，不手填，保证"能复算、可对账"；
    · 随机数固定种子，同参数永远产出同一份数据；
    · 原有 10 起案件 / 10 家场所 / 10 名人员 / 10 辆车 / 4 条线索的编号与取值保持不变。

产出
    sql/risk_alert_示例库.sql        建库脚本的数据段（DDL/视图/触发器/过程保持原样）
    frontend/src/api/mock/seed.js    前端模拟库种子（与 SQL 逐行同源）

用法
    python tools/gen_demo_data.py
"""

import math
import os
import random
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_PATH = os.path.join(ROOT, 'sql', 'risk_alert_示例库.sql')
SEED_PATH = os.path.join(ROOT, 'frontend', 'src', 'api', 'mock', 'seed.js')

SEED = 20261103
CUTOFF = datetime(2026, 11, 1, 0, 0, 0)
HIST_START = date(2026, 9, 1)
HIST_END = date(2026, 10, 31)

rng = random.Random(SEED)

# -----------------------------------------------------------------------------
# 规模参数
# -----------------------------------------------------------------------------
N_CASE = 100        # 历史段案件数（含原有 10 起）
N_CONTROL = 200     # 对照样本数
N_REGION_BATCH = 16 # 区域时段研判批次

TARGET = {          # 特征命中数：h1 / h0（分母 n1=N_CASE、n0=N_CONTROL）
    'F001': (58, 58),
    'F002': (62, 15),
    'F003': (71, 70),
    'F004': (66, 42),
    'F005': (47, 42),
    'F006': (6, 48),
    'F008': (25, 16),
    'F009': (20, 12),
}

W = {}
def put(name, row):
    W.setdefault(name, []).append(row)
    return row

# =============================================================================
# 1. 工具
# =============================================================================

def fmt(d):
    return d.strftime('%Y-%m-%d %H:%M:%S')

def parse(s):
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

def wpick(items, weights):
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if r <= acc:
            return it
    return items[-1]

def allocate(n, k):
    k = max(0, min(n, k))
    idx = list(range(n))
    rng.shuffle(idx)
    chosen = set(idx[:k])
    return [i in chosen for i in range(n)]

def day_type_of(dt):
    return 2 if dt.weekday() >= 5 else 1

def bh(ts):
    """小时桶键：'YYYY-MM-DD HH'"""
    return ts.strftime('%Y-%m-%d %H')

# =============================================================================
# 2. 主数据常量
# =============================================================================

# lng/lat 为示例城市（虚构）的近似坐标，仅用于前端地图演示，不对应真实地理位置
AREAS = [
    ('A01', '中心商圈',      2, None, 1.00, 118.902100, 31.601800),
    ('A02', '老城餐饮街',    2, None, 1.00, 118.881800, 31.604900),
    ('A03', '东部开发区',    1, None, 0.55, 118.962300, 31.598200),
    ('A04', '西郊乡镇',      3, None, 0.28, 118.830100, 31.612000),
    ('A05', '火车站片区',    1, None, 0.78, 118.910200, 31.642100),
    ('A06', '滨江路沿线',    1, None, 0.62, 118.918400, 31.558300),
    ('A07', '大学城',        2, None, 0.86, 118.857600, 31.561900),
    ('A08', '北高速出入口',  4, None, 0.12, 118.900100, 31.671800),
    ('A09', '南湖公园周边',  1, 'A03', 0.42, 118.978200, 31.570200),
    ('A10', '高新工业园',    1, 'A03', 0.34, 118.990300, 31.590100),
    ('A11', '城北老街',      2, None, 0.80, 118.880400, 31.649900),
    ('A12', '城南客运站',    1, None, 0.40, 118.888100, 31.538200),
]
AREA_IDS = [a[0] for a in AREAS]
AREA_NL = {a[0]: a[4] for a in AREAS}
AREA_TYPE = {a[0]: a[2] for a in AREAS}

PLACES = [
    ('PL0001', '金樽酒楼',     1, 'A01', '中心路 12 号'),
    ('PL0002', '星空KTV',      2, 'A01', '中心路 18 号'),
    ('PL0003', '老味道饭馆',   1, 'A02', '老街 36 号'),
    ('PL0004', '夜猫酒吧',     3, 'A02', '老街 55 号'),
    ('PL0005', '江畔餐厅',     1, 'A06', '滨江路 8 号'),
    ('PL0006', '乐坊KTV',      2, 'A07', '学府路 21 号'),
    ('PL0007', '川味小馆',     1, 'A03', '开发大道 77 号'),
    ('PL0008', '蓝调酒吧',     3, 'A05', '站前街 9 号'),
    ('PL0009', '乡里人家',     1, 'A04', '乡道 3 号'),
    ('PL0010', '湖畔茶餐厅',   4, 'A09', '南湖路 15 号'),
    ('PL0011', '鼎盛火锅',     1, 'A01', '中心路 26 号'),
    ('PL0012', '微醺精酿酒吧', 3, 'A01', '商圈西巷 4 号'),
    ('PL0013', '老街炭火烧烤', 1, 'A02', '老街 72 号'),
    ('PL0014', '月光KTV',      2, 'A02', '老街 88 号'),
    ('PL0015', '开发区食堂',   1, 'A03', '开发大道 12 号'),
    ('PL0016', '金港KTV',      2, 'A03', '开发大道 40 号'),
    ('PL0017', '镇口农家乐',   1, 'A04', '镇前路 6 号'),
    ('PL0018', '站前饺子馆',   1, 'A05', '站前街 22 号'),
    ('PL0019', '旅途宾馆餐厅', 4, 'A05', '站前街 30 号'),
    ('PL0020', '滨江渔家',     1, 'A06', '滨江路 33 号'),
    ('PL0021', '江风酒吧',     3, 'A06', '滨江路 45 号'),
    ('PL0022', '学苑餐厅',     1, 'A07', '学府路 8 号'),
    ('PL0023', '青春小酒馆',   3, 'A07', '学府路 39 号'),
    ('PL0024', '高速服务区餐厅', 4, 'A08', '绕城高速北出口'),
    ('PL0025', '南湖鱼庄',     1, 'A09', '南湖路 42 号'),
    ('PL0026', '园区快餐',     1, 'A10', '工业园一路 5 号'),
    ('PL0027', '北门涮肉',     1, 'A11', '北门大街 15 号'),
    ('PL0028', '老北门KTV',    2, 'A11', '北门大街 28 号'),
    ('PL0029', '巷子酒吧',     3, 'A11', '北门小巷 3 号'),
    ('PL0030', '城南面馆',     1, 'A12', '城南路 19 号'),
]
PLACE_AREA = {p[0]: p[3] for p in PLACES}
PLACE_TYPE = {p[0]: p[2] for p in PLACES}
ALCOHOL_BY_AREA = defaultdict(list)
for _p in PLACES:
    if _p[2] in (1, 2, 3):
        ALCOHOL_BY_AREA[_p[3]].append(_p[0])
CASE_AREAS = [a for a in AREA_IDS if len(ALCOHOL_BY_AREA[a]) >= 2]

SURNAMES = list('王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤')
GIVEN_M = ['伟', '强', '磊', '军', '洋', '勇', '杰', '涛', '明', '超', '鹏', '斌', '辉', '刚', '建',
           '峰', '亮', '宇', '浩', '晨', '睿', '凯', '立', '永', '海', '波', '宁', '旭', '阳', '帆',
           '文', '博', '翔', '鹏飞', '建华', '志强', '国庆', '振东', '天佑', '子轩']
GIVEN_F = ['娜', '静', '敏', '丽', '艳', '娟', '芳', '秀英', '霞', '玲', '燕', '萍', '红', '梅', '琳',
           '洁', '倩', '婷', '雪', '颖', '欣', '悦', '佳', '思', '雨', '梦', '晓', '珊', '露', '蓉',
           '文静', '丽娟', '桂兰', '秀兰', '雅琴', '小雨', '欣然', '诗涵', '梦琪', '晓雯']
USED_NAMES = set()

def new_name(gender):
    for _ in range(9000):
        n = rng.choice(SURNAMES) + rng.choice(GIVEN_M if gender == 1 else GIVEN_F)
        if n not in USED_NAMES:
            USED_NAMES.add(n)
            return n
    raise RuntimeError('名字取尽')

PERSON_SEQ = 0
def new_person(gender, home, ptype, birth=None, created='2026-08-20 09:00:00'):
    global PERSON_SEQ
    PERSON_SEQ += 1
    return put('person_info', dict(
        person_id='P%04d' % PERSON_SEQ, person_name=new_name(gender), gender=gender,
        birth_year=birth or rng.randint(1968, 2003), phone='139%08d' % (20000000 + PERSON_SEQ),
        home_area_id=home, person_type=ptype, created_at=created))

VEHICLE_SEQ = 0
def new_vehicle(owner, vtype=1):
    global VEHICLE_SEQ
    VEHICLE_SEQ += 1
    plate = '浙A%05d' % (20000 + VEHICLE_SEQ)
    return put('vehicle_owner', dict(vehicle_id='V%04d' % VEHICLE_SEQ, plate=plate,
                                     plate_mask=plate, owner_person_id=owner,
                                     vehicle_type=vtype, is_active=1))

SEQ = defaultdict(int)
def _next_no(prefix, ts):
    day = ts.strftime('%Y%m%d')
    SEQ[(prefix, day)] += 1
    return '%s%s%03d' % (prefix, day, SEQ[(prefix, day)])

def add_consume(pid, pl, ts, alcohol, amount=None):
    d = parse(ts) if isinstance(ts, str) else ts
    if amount is None:
        lo, hi = {1: (88, 760), 2: (480, 2600), 3: (160, 1400), 4: (30, 260)}[PLACE_TYPE[pl]]
        amount = round(rng.uniform(lo, hi), 2)
    return put('consume_record', dict(record_no=_next_no('CR', d), person_id=pid, place_id=pl,
                                      consume_time=fmt(d), amount=amount, has_alcohol=alcohol))

def add_order(pid, otype, ts, sa, ea, status=1):
    d = parse(ts) if isinstance(ts, str) else ts
    return put('taxi_order', dict(order_no=_next_no('TO', d), person_id=pid, order_type=otype,
                                  order_time=fmt(d), start_area_id=sa, end_area_id=ea,
                                  order_status=status))

def add_track(vid, area, ts, direction):
    d = parse(ts) if isinstance(ts, str) else ts
    return put('vehicle_track', dict(record_no=_next_no('VT', d), vehicle_id=vid,
                                     gate_id='%s-G%02d' % (area, rng.choice([1, 2, 3])),
                                     area_id=area, pass_time=fmt(d), direction=direction))

# =============================================================================
# 3. 静态表
# =============================================================================

def build_static():
    for rid, rname, rdesc in [
            ('R_ANALYST', '研判员', '查看风险等级与线索、填写核查结果'),
            ('R_DATA', '数据管理员', '导入与生成信息数据、执行质量校验'),
            ('R_FEATURE', '特征管理员', '维护特征、权重、规则与版本'),
            ('R_ADMIN', '系统管理员', '账号与角色维护、备份恢复、审计检查'),
            ('R_TEACHER', '教师/评审', '只读查看演示视图与评估报告')]:
        put('sys_role', dict(role_id=rid, role_name=rname, role_desc=rdesc, status=1))

    for uid, un, rn, st in [
            ('U0001', 'admin', '系统管理员', 1), ('U0002', 'analyst1', '研判员甲', 1),
            ('U0003', 'analyst2', '研判员乙', 1), ('U0004', 'dataop', '数据管理员', 1),
            ('U0005', 'featop', '特征管理员', 1), ('U0006', 'auditor', '审计员', 1),
            ('U0007', 'teacher', '指导教师', 1), ('U0008', 'analyst3', '研判员丙', 1),
            ('U0009', 'featop2', '特征管理员2', 1), ('U0010', 'guest', '演示账号', 2)]:
        put('sys_user', dict(user_id=uid, username=un, salt='SALT2026' + uid, real_name=rn,
                             status=st, created_at='2026-08-10 09:00:00'))
    for uid, rid in [('U0001', 'R_ADMIN'), ('U0002', 'R_ANALYST'), ('U0003', 'R_ANALYST'),
                     ('U0004', 'R_DATA'), ('U0005', 'R_FEATURE'), ('U0006', 'R_ADMIN'),
                     ('U0007', 'R_TEACHER'), ('U0008', 'R_ANALYST'), ('U0009', 'R_FEATURE'),
                     ('U0002', 'R_TEACHER')]:
        put('sys_user_role', dict(user_id=uid, role_id=rid, granted_at='2026-08-10 10:00:00'))

    for k, v, t, d in [
            ('history_cutoff', '2026-11-01 00:00:00', 3,
             '案例库只保留此刻之前的历史案件；观察段案件不进 case_info，只进 eval_label'),
            ('pos_sample_rate', '0.32', 2, '正样本比例'),
            ('noise_sample_rate', '0.32', 2, '干扰样本比例'),
            ('control_sample_rate', '0.36', 2, '对照样本比例'),
            ('weight_cap', '3.00', 2, '权重截断绝对值'),
            ('min_feature_sample', '5', 1, '特征样本下限'),
            ('low_threshold', '3.00', 2, '低/中风险分界'),
            ('high_threshold', '6.00', 2, '中/高风险分界'),
            ('test_set_ratio', '0.20', 2, '历史段内部再切 20% 做验证'),
            ('judge_timeout_sec', '30', 1, '研判超时阈值（秒）')]:
        put('param_config', dict(param_key=k, param_value=v, param_type=t, param_desc=d,
                                 updated_at='2026-10-26 10:00:00'))

    for aid, aname, atype, parent, _nl, lng, lat in AREAS:
        put('area_info', dict(area_id=aid, area_name=aname, area_type=atype,
                              parent_area_id=parent, is_active=1,
                              lng=lng, lat=lat,
                              created_at='2026-08-15 09:00:00'))
    for pid, pname, ptype, area, addr in PLACES:
        put('place_info', dict(place_id=pid, place_name=pname, place_type=ptype,
                               area_id=area, address=addr, is_active=1))

    global PERSON_SEQ, VEHICLE_SEQ
    for pid, name, g, by, phone, home, ptype in [
            ('P0001', '张伟', 1, 1988, '13800001001', 'A01', 1),
            ('P0002', '李娜', 2, 1992, '13800001002', 'A04', 1),
            ('P0003', '王强', 1, 1985, '13800001003', 'A09', 1),
            ('P0004', '刘洋', 1, 1995, '13800001004', 'A07', 1),
            ('P0005', '陈静', 2, 1990, '13800001005', 'A06', 1),
            ('P0006', '赵磊', 1, 1982, '13800001006', 'A04', 1),
            ('P0007', '孙丽', 2, 1998, '13800001007', 'A09', 2),
            ('P0008', '周涛', 1, 1979, '13800001008', 'A04', 2),
            ('P0009', '吴敏', 2, 1993, '13800001009', 'A10', 2),
            ('P0010', '郑凯', 1, 1996, '13800001010', 'A01', 3)]:
        PERSON_SEQ = max(PERSON_SEQ, int(pid[1:]))
        USED_NAMES.add(name)
        put('person_info', dict(person_id=pid, person_name=name, gender=g, birth_year=by,
                                phone=phone, home_area_id=home, person_type=ptype,
                                created_at='2026-08-15 09:00:00'))
    for i, plate in enumerate(['浙A12345', '浙A23456', '浙A34567', '浙A45678', '浙A56789',
                               '浙A67890', '浙A78901', '浙A89012', '浙A90123', '浙A01234']):
        VEHICLE_SEQ += 1
        put('vehicle_owner', dict(vehicle_id='V%04d' % (i + 1), plate=plate, plate_mask=plate,
                                  owner_person_id='P%04d' % (i + 1),
                                  vehicle_type=2 if i == 5 else (3 if i == 8 else 1), is_active=1))

    feats = [
        ('F001', 'NIGHT_VENUE', '夜间酒水场所集中度', 1, 1, 1, 2, 'consume_record',
         '该区域该小时内含酒水消费的不同场所数 ≥ 2', 60, 5,
         '区域级聚合特征；对象本身按小时定义，因此不用"是不是深夜"这种恒真条件'),
        ('F002', 'KTV_CONSUME', '在饭店/KTV/酒吧等场所含酒水消费', 2, 1, 3, 1, 'consume_record',
         '窗口内 has_alcohol = 1', 180, 5,
         '区域级看"该区域该小时有没有酒水消费"，个人级看"这个人在窗口内有没有"'),
        ('F003', 'NO_TAXI', '无网约车或代驾订单', 3, 1, 2, 1, 'taxi_order',
         '窗口内 NOT EXISTS 已完成订单（type IN (1,2)）', 180, 5,
         '只有 order_status=1 的订单才算数，取消单不能证明他没开车'),
        ('F004', 'SELF_DRIVE', '自行驾车驶出', 4, 1, 1, 2, 'vehicle_track',
         '该区域该小时内驶出车辆数 ≥ 5', 60, 5,
         '区域级聚合；方向必须是"驶出区域"（direction=2）；不推断具体驾驶人'),
        ('F005', 'FAR_FROM_HOME', '离家较远', 1, 1, 2, 1, 'person_info',
         '消费场所所属区域 ≠ 居住区域（home_area_id）', 180, 5,
         '用"跨区域"近似"离家距离远"，避免在库里引入经纬度和大圆距离计算'),
        ('F006', 'HAS_DRIVER', '有代驾订单（反例）', 5, 2, 2, 1, 'taxi_order',
         '窗口内存在 order_type = 2 且已完成的订单', 180, 5,
         '命中则扣分，counter_block=1 时直接阻断线索生成'),
        ('F008', 'CASE_HISTORY', '历史涉案', 4, 1, 2, 2, 'v_case_history',
         '该人员 90 天内历史案件数 ≥ 1', 0, 5,
         '只能读 v_case_history，视图已把 history_cutoff 之后的案件滤掉'),
        ('F009', 'DRUNK_HISTORY', '历史醉驾', 4, 1, 2, 1, 'v_case_history',
         '该人员历史案件中存在 alcohol_value ≥ 80', 0, 5,
         '同上，历史档案特征，不得读 case_info 原表'),
    ]
    for f in feats:
        put('feature_def', dict(feature_id=f[0], feature_code=f[1], feature_name=f[2],
                                risk_type=1, feature_cat=f[3], direction=f[4],
                                object_scope=f[5], value_type=f[6], src_table='case_info',
                                match_src=f[7], match_expr=f[8], time_window_min=f[9],
                                min_sample=f[10], status=1, description=f[11]))

    for vid, vno, st, bc, bctl, calc, pub, remark in [
            ('V20260901_00', '0.9', 2, 300, 600, '2026-09-01 10:00:00', 'U0005',
             '初版：8 个特征，已归档'),
            ('V20261001_01', '1.0', 1, N_CASE, N_CONTROL, '2026-10-01 10:00:00', 'U0005',
             '现行版本：8 个特征，阈值 3/6'),
            ('V20261101_02', '2.0', 0, N_CASE, N_CONTROL, '2026-11-01 10:00:00', 'U0009',
             '草稿：区域规则阈值收紧到 4/7')]:
        put('feature_version', dict(version_id=vid, risk_type=1, version_no=vno,
                                    publish_status=st, based_case_cnt=bc, based_ctrl_cnt=bctl,
                                    calc_at=calc, published_by=pub, remark=remark,
                                    created_at=calc))

    for rid, rname, vid, jo, ms, mh, lo, hi, cb, remark in [
            ('R001', '区域时段酒驾风险研判（默认）', 'V20261001_01', 1, 2, 2, 3.0, 6.0, 1,
             'F001+F002+F004 三项区域级特征，至少命中 2 项'),
            ('R002', '个人风险线索（选做）', 'V20261001_01', 2, 1, 2, 3.0, 6.0, 1,
             'F002+F003+F005+F006+F008+F009，含反例'),
            ('R003', '区域时段·严版（草稿）', 'V20261101_02', 1, 5, 3, 4.0, 7.0, 1,
             '样本量更高、阈值更严')]:
        put('judge_rule', dict(rule_id=rid, rule_name=rname, risk_type=1, version_id=vid,
                               judge_object=jo, min_sample=ms, min_hit_cnt=mh,
                               low_threshold=lo, high_threshold=hi, counter_block=cb,
                               status=1, remark=remark, created_at='2026-10-01 10:00:00'))
    for rid, fid, req, sn in [('R001', 'F001', 0, 10), ('R001', 'F002', 0, 20), ('R001', 'F004', 1, 30),
                              ('R002', 'F002', 0, 10), ('R002', 'F003', 0, 20), ('R002', 'F005', 0, 30),
                              ('R002', 'F006', 0, 40), ('R002', 'F008', 0, 50), ('R002', 'F009', 0, 60),
                              ('R003', 'F001', 0, 10), ('R003', 'F002', 0, 20), ('R003', 'F004', 1, 30)]:
        put('rule_feature', dict(rule_id=rid, feature_id=fid, is_required=req, sort_no=sn))

# =============================================================================
# 4. 固定原始数据（保持编号与取值不变）
# =============================================================================

FIXED_CASES = [
    ('C20261009001', '2026-10-09 23:40:00', 'A01', 'PL0002', 'P0001', 'V0001', 1, 2, 92.0, 3.2, 1),
    ('C20261009002', '2026-10-10 00:25:00', 'A02', 'PL0004', 'P0002', 'V0002', 1, 1, 68.0, 5.8, 1),
    ('C20261009003', '2026-10-09 22:10:00', 'A03', 'PL0007', 'P0003', 'V0003', 1, 1, 45.0, 2.1, 0),
    ('C20261016001', '2026-10-16 23:05:00', 'A07', 'PL0006', 'P0004', 'V0004', 1, 2, 128.0, 4.6, 2),
    ('C20261016002', '2026-10-16 21:30:00', 'A06', 'PL0005', 'P0005', 'V0005', 0, 1, 33.0, 1.8, 1),
    ('C20261017001', '2026-10-17 00:50:00', 'A05', 'PL0008', 'P0006', 'V0006', 0, 1, 76.0, 6.4, 0),
    ('C20261023001', '2026-10-23 22:40:00', 'A01', 'PL0001', 'P0001', 'V0001', 1, 1, 55.0, 2.9, 1),
    ('C20261030001', '2026-10-30 23:20:00', 'A03', 'PL0010', 'P0003', 'V0003', 1, 2, 88.0, 4.1, 2),
    ('C20261031001', '2026-10-31 21:55:00', 'A07', 'PL0006', 'P0004', 'V0004', 1, 1, 41.0, 4.4, 0),
    ('C20261031002', '2026-10-31 23:35:00', 'A02', 'PL0003', 'P0002', 'V0002', 1, 1, 62.0, 6.1, 2),
]
FIXED_HIST_CONSUME = [
    ('CR20261009001', 'P0001', 'PL0002', '2026-10-09 21:50:00', 680.00, 1),
    ('CR20261009002', 'P0002', 'PL0004', '2026-10-09 22:40:00', 420.00, 1),
    ('CR20261009003', 'P0003', 'PL0007', '2026-10-09 20:35:00', 310.00, 1),
    ('CR20261016001', 'P0004', 'PL0006', '2026-10-16 21:30:00', 760.00, 1),
    ('CR20261016002', 'P0005', 'PL0005', '2026-10-16 19:50:00', 260.00, 1),
    ('CR20261017001', 'P0006', 'PL0008', '2026-10-16 23:10:00', 380.00, 1),
    ('CR20261023001', 'P0001', 'PL0001', '2026-10-23 20:55:00', 540.00, 1),
    ('CR20261030001', 'P0003', 'PL0010', '2026-10-30 21:40:00', 290.00, 1),
    ('CR20261031001', 'P0004', 'PL0006', '2026-10-31 20:20:00', 460.00, 1),
    ('CR20261031002', 'P0002', 'PL0003', '2026-10-31 22:15:00', 330.00, 1),
    ('CR20261009004', 'P0007', 'PL0001', '2026-10-09 20:15:00', 150.00, 0),
    ('CR20261023002', 'P0008', 'PL0009', '2026-10-23 19:30:00', 230.00, 0),
    ('CR20261016003', 'P0009', 'PL0010', '2026-10-16 21:20:00', 180.00, 0),
]
FIXED_HIST_ORDER = [
    ('TO20261009001', 'P0007', 1, '2026-10-09 21:05:00', 'A09', 'A09', 1),
    ('TO20261009002', 'P0007', 2, '2026-10-09 23:20:00', 'A09', 'A09', 1),
    ('TO20261016001', 'P0008', 1, '2026-10-16 20:40:00', 'A04', 'A01', 1),
    ('TO20261016002', 'P0009', 2, '2026-10-16 23:30:00', 'A10', 'A10', 1),
    ('TO20261023001', 'P0009', 1, '2026-10-23 21:10:00', 'A10', 'A05', 1),
    ('TO20261030001', 'P0008', 2, '2026-10-30 22:50:00', 'A04', 'A04', 1),
]
FIXED_HIST_TRACK = [
    ('VT20261009001', 'V0001', 'A01-G01', '2026-10-09 23:25:00', 2),
    ('VT20261009002', 'V0002', 'A02-G01', '2026-10-10 00:10:00', 2),
    ('VT20261009003', 'V0003', 'A03-G01', '2026-10-09 21:55:00', 2),
    ('VT20261016001', 'V0004', 'A07-G01', '2026-10-16 22:50:00', 2),
    ('VT20261016002', 'V0005', 'A06-G01', '2026-10-16 21:15:00', 2),
    ('VT20261017001', 'V0006', 'A05-G01', '2026-10-17 00:35:00', 2),
    ('VT20261023001', 'V0001', 'A01-G01', '2026-10-23 22:25:00', 2),
    ('VT20261030001', 'V0003', 'A03-G01', '2026-10-30 23:05:00', 2),
    ('VT20261031001', 'V0004', 'A07-G01', '2026-10-31 21:40:00', 2),
    ('VT20261031002', 'V0002', 'A02-G01', '2026-10-31 23:20:00', 2),
    ('VT20261009004', 'V0007', 'A09-G01', '2026-10-09 20:10:00', 1),
    ('VT20261023002', 'V0008', 'A04-G01', '2026-10-23 19:45:00', 1),
]
FIXED_HIST_CONTROL = [
    ('P0007', 'A09', '2026-10-09', 22, 1), ('P0007', 'A09', '2026-10-16', 23, 1),
    ('P0008', 'A04', '2026-10-09', 21, 1), ('P0008', 'A04', '2026-10-23', 22, 2),
    ('P0009', 'A10', '2026-10-16', 22, 1), ('P0009', 'A10', '2026-10-30', 23, 3),
    ('P0007', 'A09', '2026-10-23', 21, 3), ('P0008', 'A04', '2026-10-31', 22, 1),
    ('P0009', 'A10', '2026-10-31', 23, 2), ('P0008', 'A04', '2026-10-30', 21, 1),
]
FIXED_NOV_CONSUME = [
    ('CR20261107001', 'P0007', 'PL0003', '2026-11-07 22:40:00', 420.00, 1),
    ('CR20261107002', 'P0008', 'PL0004', '2026-11-07 23:10:00', 360.00, 1),
    ('CR20261107003', 'P0002', 'PL0003', '2026-11-07 22:50:00', 280.00, 1),
    ('CR20261106001', 'P0001', 'PL0001', '2026-11-06 23:20:00', 510.00, 1),
    ('CR20261106002', 'P0009', 'PL0002', '2026-11-06 23:40:00', 390.00, 1),
    ('CR20261107004', 'P0006', 'PL0008', '2026-11-07 23:15:00', 340.00, 1),
    ('CR20261107005', 'P0010', 'PL0008', '2026-11-07 23:30:00', 210.00, 1),
    ('CR20261107006', 'P0007', 'PL0008', '2026-11-07 23:50:00', 180.00, 1),
    ('CR20261107007', 'P0004', 'PL0005', '2026-11-07 22:30:00', 470.00, 1),
    ('CR20261108001', 'P0003', 'PL0007', '2026-11-08 21:10:00', 250.00, 1),
]
FIXED_NOV_ORDER = [
    ('TO20261107001', 'P0007', 2, '2026-11-07 23:30:00', 'A02', 'A09', 1),
    ('TO20261107002', 'P0008', 2, '2026-11-07 23:40:00', 'A02', 'A04', 1),
    ('TO20261106001', 'P0009', 1, '2026-11-06 23:50:00', 'A01', 'A10', 1),
    ('TO20261107003', 'P0010', 1, '2026-11-07 23:55:00', 'A05', 'A01', 1),
    ('TO20261107004', 'P0006', 2, '2026-11-07 23:40:00', 'A05', 'A04', 1),
    ('TO20261108001', 'P0003', 1, '2026-11-08 21:40:00', 'A03', 'A09', 1),
]
FIXED_NOV_TRACK = [
    ('VT20261107001', 'V0007', 'A02-G01', '2026-11-07 23:05:00', 2),
    ('VT20261107002', 'V0008', 'A02-G02', '2026-11-07 23:15:00', 2),
    ('VT20261107003', 'V0009', 'A02-G01', '2026-11-07 23:25:00', 2),
    ('VT20261107004', 'V0010', 'A02-G02', '2026-11-07 23:35:00', 2),
    ('VT20261107005', 'V0001', 'A02-G01', '2026-11-07 23:45:00', 2),
    ('VT20261106001', 'V0002', 'A01-G01', '2026-11-06 23:05:00', 2),
    ('VT20261106002', 'V0003', 'A01-G02', '2026-11-06 23:15:00', 2),
    ('VT20261106003', 'V0005', 'A01-G01', '2026-11-06 23:25:00', 2),
    ('VT20261107006', 'V0006', 'A05-G01', '2026-11-07 23:20:00', 2),
    ('VT20261108001', 'V0004', 'A07-G01', '2026-11-08 00:05:00', 2),
    ('VT20261108002', 'V0007', 'A07-G02', '2026-11-08 00:10:00', 2),
    ('VT20261108003', 'V0008', 'A07-G01', '2026-11-08 00:20:00', 2),
    ('VT20261108004', 'V0009', 'A07-G02', '2026-11-08 00:30:00', 2),
    ('VT20261108005', 'V0010', 'A07-G01', '2026-11-08 00:40:00', 2),
]

HOME = {}
VEH_BY_PERSON = {}
PERSON_BY_ID = {}

def load_fixed_rows():
    for c in FIXED_CASES:
        put('case_info', dict(case_id=c[0], occur_time=c[1], area_id=c[2], place_id=c[3],
                              person_id=c[4], vehicle_id=c[5], driver_confirmed=c[6],
                              case_type=c[7], alcohol_value=c[8], distance_home=c[9],
                              dispose_status=c[10], created_at=c[1][:11] + '03:00:00'))
    for no, pid, pl, t, amt, al in FIXED_HIST_CONSUME + FIXED_NOV_CONSUME:
        put('consume_record', dict(record_no=no, person_id=pid, place_id=pl, consume_time=t,
                                   amount=amt, has_alcohol=al))
    for no, pid, ot, t, sa, ea, st in FIXED_HIST_ORDER + FIXED_NOV_ORDER:
        put('taxi_order', dict(order_no=no, person_id=pid, order_type=ot, order_time=t,
                               start_area_id=sa, end_area_id=ea, order_status=st))
    for no, vid, gate, t, d in FIXED_HIST_TRACK + FIXED_NOV_TRACK:
        put('vehicle_track', dict(record_no=no, vehicle_id=vid, gate_id=gate,
                                  area_id=gate.split('-')[0], pass_time=t, direction=d))
    for no, prefix in [(x[0], 'CR') for x in FIXED_HIST_CONSUME + FIXED_NOV_CONSUME] + \
                      [(x[0], 'TO') for x in FIXED_HIST_ORDER + FIXED_NOV_ORDER] + \
                      [(x[0], 'VT') for x in FIXED_HIST_TRACK + FIXED_NOV_TRACK]:
        SEQ[(prefix, no[2:10])] = max(SEQ[(prefix, no[2:10])], int(no[10:]))
    for p in W['person_info']:
        HOME[p['person_id']] = p['home_area_id']
        PERSON_BY_ID[p['person_id']] = p
    for v in W['vehicle_owner']:
        VEH_BY_PERSON[v['owner_person_id']] = v['vehicle_id']

# =============================================================================
# 5. 桶补足：把"场所数 / 驶出车辆数"补到目标值
# =============================================================================

IDX_CONSUME = defaultdict(list)
IDX_TRACK = defaultdict(list)

def build_index():
    IDX_CONSUME.clear()
    IDX_TRACK.clear()
    for c in W['consume_record']:
        IDX_CONSUME[bh(parse(c['consume_time']))].append(c)
    for t in W['vehicle_track']:
        IDX_TRACK[bh(parse(t['pass_time']))].append(t)

def venues_in(area, ts):
    key = bh(ts)
    return {c['place_id'] for c in IDX_CONSUME[key]
            if c['has_alcohol'] == 1 and PLACE_AREA[c['place_id']] == area}

def exits_in(area, ts):
    key = bh(ts)
    return [t for t in IDX_TRACK[key] if t['direction'] == 2 and t['area_id'] == area]

def topup_venues(area, ts, target, patron_pool):
    """把该区域该小时的含酒水场所数补到 target 家。"""
    have = venues_in(area, ts)
    guard = 0
    while len(have) < target and guard < 20:
        guard += 1
        cand = [p for p in ALCOHOL_BY_AREA[area] if p not in have]
        if not cand:
            break
        pl = rng.choice(cand)
        p = rng.choice(patron_pool)
        add_consume(p['person_id'], pl, ts + timedelta(minutes=rng.randint(1, 58)), 1)
        IDX_CONSUME[bh(ts)].append(W['consume_record'][-1])
        have.add(pl)

def topup_exits(area, ts, target, vehicles):
    """把该区域该小时的"驶出车辆数"补到 target；同时按约 1:3 补驶入记录。
    驶入记录不参与 F004（该特征只数 direction=2），但能让卡口数据像一个真卡口。"""
    have = len(exits_in(area, ts))
    for _ in range(max(0, target - have)):
        add_track(rng.choice(vehicles), area, ts + timedelta(minutes=rng.randint(1, 58)), 2)
        IDX_TRACK[bh(ts)].append(W['vehicle_track'][-1])
    key = bh(ts)
    n_in = len([t for t in IDX_TRACK[key] if t['direction'] == 1 and t['area_id'] == area])
    want_in = max(1, round(target / 3)) if target else 0
    for _ in range(max(0, want_in - n_in)):
        add_track(rng.choice(vehicles), area, ts + timedelta(minutes=rng.randint(1, 58)), 1)
        IDX_TRACK[key].append(W['vehicle_track'][-1])

# =============================================================================
# 6. 历史段：案件 + 以案生痕迹
# =============================================================================

def build_history(start=None, end=None, n_cases=None, fixed_cases=None,
                  created='2026-08-20 09:00:00', order_days=58):
    """生成一批历史段数据；参数默认值即第一批（2026-09~10），第二波传 7~8 月。"""
    start = start or HIST_START
    end = end or HIST_END
    n_cases = n_cases or N_CASE
    fixed_cases = FIXED_CASES if fixed_cases is None else fixed_cases
    used = set()
    for c in fixed_cases:
        t = parse(c[1])
        used.add((c[2], t.strftime('%Y-%m-%d'), t.hour))

    # 背景人员池（只在历史段出现，避免污染对照口径）
    patrons = [new_person(rng.choice([1, 1, 1, 2]), wpick(AREA_IDS, [AREA_NL[a] + 0.2 for a in AREA_IDS]), 3,
                          created=created)
               for _ in range(54)]
    for p in patrons:
        HOME[p['person_id']] = p['home_area_id']
        PERSON_BY_ID[p['person_id']] = p
        if rng.random() < 0.66:
            new_vehicle(p['person_id'], wpick([1, 2, 3], [0.9, 0.05, 0.05]))

    # ---- 时段槽位 ----
    slots = []
    tries = 0
    while len(slots) < n_cases - len(fixed_cases) and tries < 60000:
        tries += 1
        d = start + timedelta(days=rng.randint(0, (end - start).days))
        dw = {0: 0.55, 1: 0.6, 2: 0.7, 3: 0.9, 4: 1.9, 5: 2.3, 6: 1.3}[d.weekday()]
        if rng.random() * 2.3 > dw:
            continue
        area = wpick(CASE_AREAS, [AREA_NL[a] for a in CASE_AREAS])
        h = wpick([20, 21, 22, 23, 24, 25, 26], [0.06, 0.16, 0.27, 0.29, 0.13, 0.06, 0.03])
        base = datetime(d.year, d.month, d.day) + timedelta(hours=h)
        key = (area, base.strftime('%Y-%m-%d'), base.hour)
        if key in used:
            continue
        used.add(key)
        slots.append([base, area])
    assert len(slots) == n_cases - len(fixed_cases)

    # ---- 涉案人员编排 ----
    order_idx = list(range(len(slots)))
    rng.shuffle(order_idx)
    triples = [order_idx[i * 3:i * 3 + 3] for i in range(9)]
    doubles = [order_idx[27 + i * 2:27 + i * 2 + 2] for i in range(3)]
    repeat_idx = {i for g in triples + doubles for i in g}
    single_idx = [i for i in range(len(slots)) if i not in repeat_idx]

    fixed_f = {
        'F001': {c[0]: 1 for c in fixed_cases},
        'F002': {c[0]: 1 for c in fixed_cases},
        'F003': {c[0]: 1 for c in fixed_cases},
        'F004': {c[0]: 1 for c in fixed_cases},
        'F005': {c[0]: 1 if PLACE_AREA[c[3]] != HOME[c[4]] else 0 for c in fixed_cases},
        'F006': {c[0]: 0 for c in fixed_cases},
    }
    n = len(slots)
    flags = {}
    for k in ['F001', 'F002', 'F003', 'F004', 'F006']:
        flags[k] = allocate(n, TARGET[k][0] - sum(fixed_f[k].values()))
    # F006 命中 → 必有订单 → F003 不命中
    for i in range(n):
        if flags['F006'][i]:
            flags['F003'][i] = False
    shortfall = (TARGET['F003'][0] - sum(fixed_f['F003'].values())) - sum(flags['F003'])
    for i in range(n - 1, -1, -1):
        if shortfall <= 0:
            break
        if not flags['F003'][i] and not flags['F006'][i]:
            flags['F003'][i] = True
            shortfall -= 1
    assert shortfall == 0
    # F005：重复涉案人员均在本区反复（离家不远），命中全部由单次人员贡献
    need5 = TARGET['F005'][0] - sum(fixed_f['F005'].values())
    f005_single = allocate(len(single_idx), need5)
    flags['F005'] = [False] * n
    for pos, si in enumerate(single_idx):
        flags['F005'][si] = f005_single[pos]

    # ---- 建人 ----
    def make_case_person(home):
        p = new_person(1 if rng.random() < 0.84 else 2, home, 1, created=created)
        HOME[p['person_id']] = home
        PERSON_BY_ID[p['person_id']] = p
        if rng.random() < 0.76:
            v = new_vehicle(p['person_id'], wpick([1, 2, 3], [0.9, 0.05, 0.05]))
            VEH_BY_PERSON[p['person_id']] = v['vehicle_id']
        return p

    person_of = {}
    for g in triples + doubles:
        g.sort(key=lambda i: slots[i][0])
        home = slots[g[0]][1]
        p = make_case_person(home)
        for si in g:
            person_of[si] = p
    for si in single_idx:
        area = slots[si][1]
        home = area if not flags['F005'][si] else wpick(
            [a for a in AREA_IDS if a != area], [AREA_NL[a] + 0.1 for a in AREA_IDS if a != area])
        person_of[si] = make_case_person(home)

    # 重复涉案人员后续案件回到其居住区域（本地反复），时段冲突则顺延
    for g in triples + doubles:
        home = HOME[person_of[g[0]]['person_id']]
        for si in g[1:]:
            cand = slots[si][0]
            for _ in range(8):
                if (home, cand.strftime('%Y-%m-%d'), cand.hour) not in used:
                    break
                cand = cand + timedelta(hours=1)
            used.add((home, cand.strftime('%Y-%m-%d'), cand.hour))
            slots[si] = [cand, home]

    # ---- 案件行 ----
    first_of_drunk = {g[0] for g in triples}
    rows = []
    for si, (base, area) in enumerate(slots):
        p = person_of[si]
        occur = base + timedelta(minutes=rng.choice(
            [3, 5, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 42, 45, 48, 50, 52, 55, 58]))
        ctype = 2 if si in first_of_drunk else wpick([1, 2, 3], [0.55, 0.38, 0.07])
        if ctype == 1:
            alcohol = round(rng.uniform(22, 78), 1)
        elif ctype == 2:
            alcohol = round(rng.uniform(82, 196), 1)
        else:
            alcohol = round(rng.uniform(40, 178), 1)
        home = HOME[p['person_id']]
        dist = round(rng.uniform(0.4, 5.0) if home == area else rng.uniform(2.5, 24.0), 2)
        rows.append(dict(
            case_id=None, occur_time=fmt(occur), area_id=area,
            place_id=wpick(ALCOHOL_BY_AREA[area], [1.0] * len(ALCOHOL_BY_AREA[area])),
            person_id=p['person_id'], vehicle_id=VEH_BY_PERSON.get(p['person_id']),
            driver_confirmed=1 if rng.random() < 0.72 else 0, case_type=ctype,
            alcohol_value=alcohol, distance_home=dist,
            dispose_status=wpick([0, 1, 2], [0.08, 0.62, 0.30]),
            created_at=fmt(occur + timedelta(hours=3)),
            _want={k: (1 if flags[k][si] else 0) for k in flags}))

    rows.sort(key=lambda r: r['occur_time'])
    seq_day = defaultdict(int)
    for c in W['case_info']:          # 续接原有案件编号，避免主键冲突
        try:
            seq_day[c['case_id'][1:9]] = max(seq_day[c['case_id'][1:9]], int(c['case_id'][9:]))
        except (ValueError, IndexError):
            pass
    for r in rows:
        day = parse(r['occur_time']).strftime('%Y%m%d')
        seq_day[day] += 1
        r['case_id'] = 'C%s%03d' % (day, seq_day[day])
        put('case_info', {k: v for k, v in r.items() if not k.startswith('_')})

    # ---- 以案生痕迹 ----
    all_veh = [v['vehicle_id'] for v in W['vehicle_owner']]
    fixed_bucket = {}
    for c in fixed_cases:
        t = parse(c[1])
        fixed_bucket[(c[2], t.strftime('%Y-%m-%d'), t.hour)] = c

    for r in rows:
        t = parse(r['occur_time'])
        area = r['area_id']
        w = r['_want']
        key = (area, t.strftime('%Y-%m-%d'), t.hour)
        # 本人消费（决定 F002；跨区与否决定 F005）
        add_consume(r['person_id'], r['place_id'], t - timedelta(minutes=rng.randint(35, 165)),
                    w['F002'])
        # 出行订单（F003 / F006）
        if w['F006']:
            add_order(r['person_id'], 2, t - timedelta(minutes=rng.randint(8, 35)), area,
                      HOME[r['person_id']] or area, 1)
        elif not w['F003']:
            add_order(r['person_id'], 1, t - timedelta(minutes=rng.randint(12, 45)), area,
                      HOME[r['person_id']] or area, 1)
        # 车辆驶出
        if r['vehicle_id']:
            add_track(r['vehicle_id'], area, t - timedelta(minutes=rng.randint(3, 28)), 2)

    # 真实订单里总有一部分取消或未完成：放在白天（不影响夜间研判窗口）
    day_patrons = [p['person_id'] for p in patrons]
    for _ in range(16):
        t0 = datetime(start.year, start.month, start.day) + timedelta(
            days=rng.randint(0, order_days), hours=rng.randint(8, 17), minutes=rng.randint(0, 59))
        pid = rng.choice(day_patrons)
        add_order(pid, wpick([1, 2], [0.85, 0.15]), t0, AREA_IDS[rng.randrange(len(AREA_IDS))],
                  HOME[pid] or AREA_IDS[0], wpick([2, 3], [0.6, 0.4]))

    # 建索引后统一补足桶（原有案件也要补）
    build_index()
    for r in rows:
        t = parse(r['occur_time'])
        area = r['area_id']
        w = r['_want']
        topup_venues(area, t.replace(minute=0, second=0), 2 if w['F001'] else 1, patrons)
        topup_exits(area, t.replace(minute=0, second=0),
                    5 if w['F004'] else 1, all_veh)
    # 原有 10 起案件：其痕迹已固定，同样按 F001/F004 命中补足背景
    for c in fixed_cases:
        t = parse(c[1]).replace(minute=0, second=0)
        topup_venues(c[2], t, 2, patrons)
        topup_exits(c[2], t, 5, all_veh)

    return rows

# =============================================================================
# 7. 特征统计（P1 / P0）
# =============================================================================

ORD_BY_PERSON = defaultdict(list)
CON_BY_PERSON = defaultdict(list)
CASE_BY_PERSON = defaultdict(list)

def build_person_index():
    ORD_BY_PERSON.clear(); CON_BY_PERSON.clear(); CASE_BY_PERSON.clear()
    for o in W['taxi_order']:
        ORD_BY_PERSON[o['person_id']].append(o)
    for c in W['consume_record']:
        CON_BY_PERSON[c['person_id']].append(c)
    for c in W['case_info']:
        CASE_BY_PERSON[c['person_id']].append(c)

def feat_values(pid, area, ts):
    """在某时刻、某区域，对某人的 8 条特征取值（口径与 feature_def 一致）。"""
    t = ts
    w0, w1 = t - timedelta(minutes=180), t
    cons = [c for c in CON_BY_PERSON.get(pid, [])
            if w0 <= parse(c['consume_time']) <= w1]
    ords = [o for o in ORD_BY_PERSON.get(pid, [])
            if w0 <= parse(o['order_time']) <= w1 and o['order_status'] == 1]
    prior = [c for c in CASE_BY_PERSON.get(pid, [])
             if t - timedelta(days=90) <= parse(c['occur_time']) < t]
    home = HOME.get(pid)
    return {
        'F001': len(venues_in(area, t)),
        'F002': 1 if any(c['has_alcohol'] == 1 for c in cons) else 0,
        'F003': 1 if not any(o['order_type'] in (1, 2) for o in ords) else 0,
        'F004': len(exits_in(area, t)),
        'F005': 1 if (home and any(PLACE_AREA[c['place_id']] != home for c in cons)) else 0,
        'F006': 1 if any(o['order_type'] == 2 for o in ords) else 0,
        'F008': 1 if prior else 0,
        'F009': 1 if any(c['alcohol_value'] >= 80 for c in prior) else 0,
    }

HITS = {'F001': lambda v: v >= 2, 'F002': lambda v: v >= 1, 'F003': lambda v: v >= 1,
        'F004': lambda v: v >= 5, 'F005': lambda v: v >= 1, 'F006': lambda v: v >= 1,
        'F008': lambda v: v >= 1, 'F009': lambda v: v >= 1}

def compute_stats():
    build_person_index()
    hit1 = defaultdict(int)
    for c in W['case_info']:
        v = feat_values(c['person_id'], c['area_id'], parse(c['occur_time']))
        for f, val in v.items():
            if HITS[f](val):
                hit1[f] += 1
    hit0 = defaultdict(int)
    for s in W['control_person']:
        ts = datetime.strptime('%s %02d:00:00' % (s['sample_date'], s['hour_slot']),
                               '%Y-%m-%d %H:%M:%S')
        v = feat_values(s['person_id'], s['area_id'], ts)
        for f, val in v.items():
            if HITS[f](val):
                hit0[f] += 1
    return hit1, hit0

def compute_weights(hit1, hit0, version_id='V20261001_01', calc_at='2026-10-01 10:00:00'):
    rows = []
    for f in ['F001', 'F002', 'F003', 'F004', 'F005', 'F006', 'F008', 'F009']:
        h1, n1 = hit1[f], len(W['case_info'])
        h0, n0 = hit0[f], len(W['control_person'])
        w = math.log(((h1 + 0.5) / (n1 - h1 + 0.5)) / ((h0 + 0.5) / (n0 - h0 + 0.5)))
        w = max(-3.0, min(3.0, round(w, 4)))
        p1 = round(h1 / n1, 4)
        p0 = round(h0 / n0, 4)
        rows.append(dict(version_id=version_id, feature_id=f, case_hit=h1, case_total=n1,
                         ctrl_hit=h0, ctrl_total=n0, p1=p1, p0=p0,
                         lift=round(p1 / p0, 4) if p0 else None, weight=w,
                         is_valid=1 if min(n1, n0) >= 5 else 0,
                         calc_at=calc_at))
    for r in rows:
        put('feature_weight', r)
    return rows

# =============================================================================
# 8. 观察段流水（只造流水，不写案件）
# =============================================================================

# 观察段排班：每周 4 个区域 × 4 个小时桶。
# object_id = 区域#日期类型#小时，同一区域跨周不得重复，否则评估标签会重复计数。
# 每一项 = (day_type, hour, profile)；day_type 2 表示次日的凌晨时段。
OBS_PLAN = [
    (date(2026, 11, 6), {
        'A02': [(1, 21, 'low'), (1, 22, 'mid'), (2, 22, 'plain'), (2, 23, 'high')],
        'A01': [(1, 21, 'low'), (1, 22, 'high'), (1, 23, 'solo4'), (2, 23, 'd24')],
        'A07': [(1, 21, 'low'), (1, 22, 'plain'), (1, 23, 'd24'), (2, 0, 'low')],
        'A05': [(1, 21, 'plain'), (1, 22, 'solo4'), (1, 23, 'mid'), (2, 0, 'mid')],
    }),
    (date(2026, 11, 13), {
        'A03': [(1, 19, 'low'), (1, 20, 'mid'), (1, 21, 'high'), (1, 22, 'solo4')],
        'A11': [(1, 19, 'plain'), (1, 20, 'low'), (1, 21, 'd24'), (1, 22, 'low')],
        'A06': [(1, 19, 'mid'), (1, 20, 'plain'), (1, 21, 'mid'), (1, 22, 'solo4')],
        'A12': [(1, 19, 'low'), (1, 20, 'plain'), (1, 21, 'mid'), (2, 1, 'plain')],
    }),
    (date(2026, 11, 20), {
        'A01': [(1, 19, 'd24'), (1, 20, 'low'), (2, 1, 'solo4'), (2, 2, 'plain')],
        'A02': [(1, 19, 'high'), (1, 20, 'low'), (2, 0, 'solo4'), (2, 1, 'plain')],
        'A05': [(1, 19, 'mid'), (1, 20, 'low'), (2, 1, 'd24'), (2, 2, 'low')],
        'A07': [(1, 19, 'low'), (1, 20, 'mid'), (2, 1, 'mid'), (2, 2, 'plain')],
    }),
    (date(2026, 11, 27), {
        'A03': [(1, 23, 'd24'), (2, 0, 'low'), (2, 1, 'plain'), (2, 2, 'solo4')],
        'A11': [(1, 23, 'high'), (2, 0, 'low'), (2, 1, 'low'), (2, 2, 'plain')],
        'A09': [(1, 21, 'low'), (1, 22, 'solo4'), (1, 23, 'plain'), (2, 0, 'low')],
        'A10': [(1, 21, 'low'), (1, 22, 'plain'), (2, 1, 'plain'), (2, 2, 'solo4')],
    }),
]

# 剖面 = (含酒水场所数区间, 驶出车辆数区间, 是否有酒水消费)
# 三种特征的组合决定了不同的得分档：6.15 / 4.94 / 4.18 / 2.97 / 1.97 / 0
PROFILES = {
    'high':  ((2, 4), (5, 7), True),    # F001+F002+F004
    'mid':   ((2, 3), (2, 4), True),    # F001+F002
    'd24':   ((1, 1), (5, 6), True),    # F002+F004
    'solo4': ((0, 0), (5, 6), False),   # 仅 F004
    'low':   ((1, 1), (1, 2), True),    # 仅 F002
    'plain': ((0, 0), (1, 2), False),   # 一条都不命中
}

def build_observation(plan_def=None, avoid=None, inherit_patrons=True, per_area=2,
                      created='2026-08-25 09:00:00', profiles=None, n_quiet=1):
    plan_def = OBS_PLAN if plan_def is None else plan_def
    profiles = PROFILES if profiles is None else profiles
    if inherit_patrons:
        obs_patrons = [p for p in W['person_info']
                       if p['person_type'] == 3 and p['person_id'] not in
                       {x[1] for x in FIXED_NOV_CONSUME}]
    else:
        obs_patrons = []
    for a in AREA_IDS:
        for _ in range(per_area):
            p = new_person(1 if rng.random() < 0.8 else 2, a, 3, created=created)
            HOME[p['person_id']] = a
            PERSON_BY_ID[p['person_id']] = p
            obs_patrons.append(p)
    all_veh = [v['vehicle_id'] for v in W['vehicle_owner']]

    plan = []
    build_index()
    seen = set(avoid or ())
    for night, area_map in plan_def:
        for area, combos in area_map.items():
            for dtp, hour, profile in combos:
                assert (area, dtp, hour) not in seen, ('duplicate object', area, dtp, hour)
                seen.add((area, dtp, hour))
                ts = datetime(night.year, night.month, night.day, hour, 0, 0)
                if dtp == 2:
                    ts += timedelta(days=1)
                vr, er, has_alc = profiles[profile]
                if len(ALCOHOL_BY_AREA[area]) < 2 and profile in ('high', 'mid'):
                    profile, vr, er, has_alc = 'low', (1, 1), (1, 2), True
                v = rng.randint(*vr) if has_alc else 0
                e = rng.randint(*er)
                topup_venues(area, ts, v, obs_patrons)
                topup_exits(area, ts, e, all_veh)
                # 同场所还有不喝酒的顾客（吃饭 / 陪客），个人研判才不会"人人报警"
                for _ in range(n_quiet if ALCOHOL_BY_AREA[area] else 0):
                    p = rng.choice(obs_patrons)
                    add_consume(p['person_id'], rng.choice(ALCOHOL_BY_AREA[area]),
                                ts + timedelta(minutes=rng.randint(1, 58)), 0)
                    IDX_CONSUME[bh(ts)].append(W['consume_record'][-1])
                plan.append(dict(night=night, area=area, ts=ts, profile=profile))
    build_person_index()
    return plan

# =============================================================================
# 9. 研判引擎（复刻《前端交接文档》第七节）
# =============================================================================

def rule_features(rule_id, version_id):
    out = []
    for rf in sorted([x for x in W['rule_feature'] if x['rule_id'] == rule_id],
                     key=lambda x: x['sort_no']):
        f = next(x for x in W['feature_def'] if x['feature_id'] == rf['feature_id'])
        w = next((x for x in W['feature_weight']
                  if x['version_id'] == version_id and x['feature_id'] == f['feature_id']), None)
        if f['status'] == 1:
            out.append((f, w))
    return out

def objects_for_batch(batch):
    """按批次数据窗归集对象（区域时段 / 个人），返回 [(key, sample_size, values)]"""
    f = parse(batch['data_start'])
    to = parse(batch['data_end'])
    if batch['judge_object'] == 1:
        groups = defaultdict(lambda: dict(cons=[], tracks=[]))
        for c in W['consume_record']:
            t = parse(c['consume_time'])
            if not (f <= t < to):
                continue
            area = PLACE_AREA[c['place_id']]
            if batch['area_id'] and area != batch['area_id']:
                continue
            key = (area, day_type_of(t), t.hour)
            groups[key]['cons'].append(c)
        for tr in W['vehicle_track']:
            t = parse(tr['pass_time'])
            if not (f <= t < to) or tr['direction'] != 2:
                continue
            if batch['area_id'] and tr['area_id'] != batch['area_id']:
                continue
            groups[(tr['area_id'], day_type_of(t), t.hour)]['tracks'].append(tr)
        out = []
        for (area, dtp, hour), g in groups.items():
            venues = {c['place_id'] for c in g['cons'] if c['has_alcohol'] == 1}
            values = {'F001': len(venues),
                      'F002': 1 if any(c['has_alcohol'] == 1 for c in g['cons']) else 0,
                      'F004': len(g['tracks'])}
            out.append((dict(object_type=1, area_id=area, day_type=dtp, hour_slot=hour,
                             person_id=None),
                        len(g['cons']) + len(g['tracks']), values))
        return out
    # 个人对象：窗口内有消费记录的人
    persons = sorted({c['person_id'] for c in W['consume_record']
                      if f <= parse(c['consume_time']) < to})
    out = []
    for pid in persons:
        mine = [c for c in CON_BY_PERSON.get(pid, []) if f <= parse(c['consume_time']) < to]
        ords = [o for o in ORD_BY_PERSON.get(pid, [])
                if f <= parse(o['order_time']) < to and o['order_status'] == 1]
        home = HOME.get(pid)
        prior = [c for c in CASE_BY_PERSON.get(pid, [])
                 if f - timedelta(days=90) <= parse(c['occur_time']) < f]
        values = {
            'F002': 1 if any(c['has_alcohol'] == 1 for c in mine) else 0,
            'F003': 1 if not any(o['order_type'] in (1, 2) for o in ords) else 0,
            'F005': (1 if any(PLACE_AREA[c['place_id']] != home for c in mine) else 0) if home else None,
            'F006': 1 if any(o['order_type'] == 2 for o in ords) else 0,
            'F008': len([c for c in prior]),
            'F009': len([c for c in prior if c['alcohol_value'] >= 80]),
        }
        out.append((dict(object_type=2, area_id=None, day_type=None, hour_slot=None,
                         person_id=pid), len(mine) + len(ords), values))
    return out

def object_id(o):
    if o['object_type'] == 1:
        return '%s#%d#%02d' % (o['area_id'], o['day_type'], o['hour_slot'])
    return o['person_id']

def run_batches(batches):
    scores = []
    for b in batches:
        rule = next(r for r in W['judge_rule'] if r['rule_id'] == b['rule_id'])
        feats = rule_features(b['rule_id'], b['version_id'])
        objs = objects_for_batch(b)
        b['object_cnt'] = len(objs)
        clue_n = 0
        for o, sample, values in objs:
            rows = []
            for f, w in feats:
                if f['feature_id'] not in values:
                    rows.append(dict(feature_id=f['feature_id'], is_hit=0, weight=w['weight'],
                                     hit_value=0, is_missing=1))
                    continue
                v = values[f['feature_id']]
                if v is None:
                    rows.append(dict(feature_id=f['feature_id'], is_hit=0, weight=w['weight'],
                                     hit_value=0, is_missing=1))
                else:
                    rows.append(dict(feature_id=f['feature_id'],
                                     is_hit=1 if HITS[f['feature_id']](v) else 0,
                                     weight=w['weight'], hit_value=v, is_missing=0))
            total = round(sum(r['is_hit'] * r['weight'] for r in rows), 2)
            level = 1 if total < float(rule['low_threshold']) else (
                2 if total < float(rule['high_threshold']) else 3)
            hit_cnt = sum(1 for r in rows if r['is_hit'] == 1 and
                          next(f for f, w in feats if f['feature_id'] == r['feature_id'])['direction'] == 1)
            blocked = rule['counter_block'] == 1 and any(
                r['is_hit'] == 1 and next(f for f, w in feats
                                          if f['feature_id'] == r['feature_id'])['direction'] == 2
                for r in rows)
            is_clue = 1 if (level >= 2 and hit_cnt >= rule['min_hit_cnt']
                            and sample >= rule['min_sample'] and not blocked) else 0
            scores.append(dict(batch_id=b['batch_id'], rule_id=b['rule_id'],
                               version_id=b['version_id'], object_type=o['object_type'],
                               area_id=o['area_id'], day_type=o['day_type'],
                               hour_slot=o['hour_slot'], person_id=o['person_id'],
                               object_id=object_id(o), sample_size=sample,
                               total_score=total, risk_level=level, is_clue=is_clue,
                               created_at=b['run_at'], features=rows))
            clue_n += is_clue
        b['clue_cnt'] = clue_n
    return scores

# =============================================================================
# 10. 批次
# =============================================================================

def build_batches():
    B = []

    def add(bid, rid, vid, jo, ds, de, area, status, run_no, dur, op, created, run_at=None):
        row = dict(batch_id=bid, rule_id=rid, version_id=vid, judge_object=jo,
                   data_start=ds, data_end=de, area_id=area, run_status=status,
                   run_no=run_no, object_cnt=0, clue_cnt=0, duration_ms=dur,
                   operator_id=op, created_at=created, run_at=run_at or created)
        B.append(row)
        return row

    # 每个观察夜的 4 个区域批次；W1 沿用原始示例的 3 天数据窗（含 11-07 晚间固定流水）
    ran_at = {0: '2026-11-09 08:%02d:00', 1: '2026-11-14 08:%02d:00',
              2: '2026-11-21 08:%02d:00', 3: '2026-11-28 08:%02d:00'}
    for wi, (night, area_map) in enumerate(OBS_PLAN):
        code = night.strftime('%Y%m%d')
        if wi == 0:
            ds, de = '2026-11-06 00:00:00', '2026-11-09 00:00:00'
        else:
            ds = '%s 18:00:00' % night.strftime('%Y-%m-%d')
            de = '%s 03:00:00' % (night + timedelta(days=1)).strftime('%Y-%m-%d')
        for i, area in enumerate(area_map.keys()):
            bid = ('B20261107%02d' % (i + 1)) if wi == 0 else ('B%s%02d' % (code, i + 1))
            at = ran_at[wi] % (i * 10)
            add(bid, 'R001', 'V20261001_01', 1, ds, de, area, 2, 1, None,
                'U0002' if i < 2 else 'U0003', at, at)
        if wi == 0:
            add('B2026110705', 'R002', 'V20261001_01', 2, '2026-11-07 18:00:00',
                '2026-11-08 03:00:00', None, 2, 1, None, 'U0002',
                '2026-11-08 09:00:00', '2026-11-08 09:00:00')
        if wi == 2:
            add('B2026112010', 'R002', 'V20261001_01', 2, '2026-11-20 20:00:00',
                '2026-11-20 21:00:00', None, 2, 1, None, 'U0003',
                '2026-11-21 09:10:00', '2026-11-21 09:10:00')

    # 失败批次：用草稿版本（尚无权重）→ 研判失败
    add('B2026110706', 'R003', 'V20261101_02', 1, '2026-11-06 18:00:00',
        '2026-11-07 03:00:00', 'A03', 3, 1, 120, 'U0002',
        '2026-11-07 09:20:00', '2026-11-07 09:20:00')
    # 待执行
    for i, area in enumerate(['A09', 'A10', 'A04', 'A06']):
        add('B20261107%02d' % (7 + i), 'R001', 'V20261001_01', 1,
            '2026-11-29 00:00:00', '2026-11-30 00:00:00', area, 0, 0, None,
            'U0002' if i % 2 == 0 else 'U0003', '2026-11-28 09:%02d:00' % (30 + i * 5))

    for b in B:
        if b['run_status'] == 2 and b['duration_ms'] is None:
            b['duration_ms'] = rng.randint(520, 1900) if b['judge_object'] == 1 else rng.randint(700, 2400)
    return B

# =============================================================================
# 11. 线索与闭环
# =============================================================================

CLUE_REMARK_TRUE = ['现场核查确认该时段存在酒驾，已移交处置',
                    '调取卡口与订单复核，确认无代驾记录，属实',
                    '经路口执勤记录比对，该时段确有饮酒驾驶行为',
                    '当事人已承认饮酒后驾车，属实']
CLUE_REMARK_FALSE = ['电话回访：聚餐后由家人接送，误报排除',
                     '现场核查为代驾司机驾驶，排除',
                     '该时段车辆由未饮酒同事驾驶，证据不足，排除',
                     '卡口抓拍车辆与研判对象不一致，排除']
CLUE_REMARK_UNKNOWN = ['当事人已离开本地，暂无法核实',
                       '监控资料超过保存期限，无法核实']

PREFERRED_SCORE = {
    ('B2026110701', 'A02#2#23'): 1,
    ('B2026110702', 'A01#2#23'): 2,
    ('B2026110703', 'A07#2#00'): 3,
    ('B2026110704', 'A05#2#23'): 4,
    ('B2026110705', 'P0002'): 5,
    ('B2026110705', 'P0004'): 6,
}
PREFERRED_CLUE = {
    ('B2026110701', 'A02#2#23'): 'CL2026110701',
    ('B2026110702', 'A01#2#23'): 'CL2026110702',
    ('B2026110705', 'P0002'): 'CL2026110703',
    ('B2026110705', 'P0004'): 'CL2026110704',
}

def assign_score_ids(scores, preferred=None, start=1):
    preferred = PREFERRED_SCORE if preferred is None else preferred
    used = {x['score_id'] for x in W['risk_score']} if start > 1 else set()
    for s in scores:
        sid = preferred.get((s['batch_id'], s['object_id']))
        if sid:
            s['score_id'] = sid
            used.add(sid)
    nxt = start
    for s in scores:
        if 'score_id' in s:
            continue
        while nxt in used:
            nxt += 1
        s['score_id'] = nxt
        used.add(nxt)
    scores.sort(key=lambda s: s['score_id'])
    return scores

def build_clues(scores, preferred_clue=None, fixed_status=None):
    clue_rows, fb_rows, cff_rows = [], [], []
    preferred_clue = PREFERRED_CLUE if preferred_clue is None else preferred_clue
    fixed_status = ({'CL2026110701': '2', 'CL2026110702': '3',
                     'CL2026110703': '2', 'CL2026110704': '1'}
                    if fixed_status is None else fixed_status)
    fb_id = max([f['feedback_id'] for f in W.get('clue_feedback', [])] or [0])
    seq_day = defaultdict(int)
    for c in W.get('risk_clue', []):             # 续接已有线索编号
        try:
            seq_day[c['clue_id'][2:10]] = max(seq_day[c['clue_id'][2:10]], int(c['clue_id'][10:]))
        except (ValueError, IndexError):
            pass
    pending = [s for s in scores if s['is_clue'] == 1]
    # 先保证原有 4 条线索的编号与对象对应
    ordered = []
    for (batch_id, oid), cid in preferred_clue.items():
        s = next((x for x in pending if x['batch_id'] == batch_id and x['object_id'] == oid), None)
        if s:
            ordered.append((s, cid))
    rest = [s for s in pending if all(s is not o[0] for o in ordered)]
    rng.shuffle(rest)
    # 状态分布：约 22% 待核查、13% 核查中、30% 已确认、35% 已排除
    statuses = (['0'] * max(1, round(len(pending) * 0.22)) +
                ['1'] * max(1, round(len(pending) * 0.13)) +
                ['2'] * max(1, round(len(pending) * 0.30)))
    statuses += ['3'] * (len(pending) - len(statuses))
    rng.shuffle(statuses)

    for s in rest:
        ordered.append((s, None))

    for idx, (s, cid) in enumerate(ordered):
        batch = next(b for b in W['judge_batch'] if b['batch_id'] == s['batch_id'])
        create_at = parse(batch['run_at']) + timedelta(minutes=rng.randint(1, 6))
        if cid is None:
            day = create_at.strftime('%Y%m%d')
            seq_day[day] += 1
            cid = 'CL%s%02d' % (day, seq_day[day])
            while any(c['clue_id'] == cid for c in clue_rows) or \
                    cid in {c['clue_id'] for c in W.get('risk_clue', [])} or cid in fixed_status:
                seq_day[day] += 1
                cid = 'CL%s%02d' % (day, seq_day[day])
        if cid in fixed_status:
            st = int(fixed_status[cid])
        else:
            st = int(statuses.pop() if statuses else '0')
        assignee = wpick(['U0002', 'U0003', 'U0008'], [0.45, 0.35, 0.20])
        row = dict(clue_id=cid, batch_id=s['batch_id'], score_id=s['score_id'],
                   version_id=s['version_id'], clue_status=st, assignee_id=assignee,
                   create_at=fmt(create_at), close_at=None,
                   _pre_status=1 if st == 1 else 0)
        clue_rows.append(row)
        if st in (2, 3):
            fb_id += 1
            check_time = create_at + timedelta(hours=rng.randint(5, 44))
            if check_time > datetime(2026, 11, 30, 20, 0):
                check_time = datetime(2026, 11, 30, 20, 0)
            result = 1 if st == 2 else 2
            method = wpick([1, 2, 3], [0.35, 0.45, 0.20])
            remark = rng.choice(CLUE_REMARK_TRUE if result == 1 else CLUE_REMARK_FALSE)
            fb_rows.append(dict(feedback_id=fb_id, clue_id=cid, check_result=result,
                                check_method=method, check_remark=remark,
                                checker_id=assignee, check_time=fmt(check_time),
                                weight_applied=1 if rng.random() < 0.7 else 0))
            row['clue_status'] = 2 if result == 1 else 3
            row['close_at'] = fmt(check_time)
            if result == 2:
                hits = [x['feature_id'] for x in s['features'] if x['is_hit'] == 1]
                wrong = rng.sample(hits, k=min(len(hits), rng.randint(1, 2)))
                for f in wrong:
                    cff_rows.append(dict(feedback_id=fb_id, feature_id=f, is_wrong=1))
        elif st == 1 and rng.random() < 0.5:
            # 核查中：已有一条"无法核实"的记录，状态不变
            fb_id += 1
            check_time = create_at + timedelta(hours=rng.randint(3, 20))
            fb_rows.append(dict(feedback_id=fb_id, clue_id=cid, check_result=3,
                                check_method=3, check_remark=rng.choice(CLUE_REMARK_UNKNOWN),
                                checker_id=assignee, check_time=fmt(check_time),
                                weight_applied=0))
    # 两条线索出现二次核查（转派复核），体现"一条线索可核查多次"
    closed = [c for c in clue_rows if c['clue_status'] in (2, 3)]
    for c in rng.sample(closed, k=min(2, len(closed))):
        if any(f['clue_id'] == c['clue_id'] and f['check_result'] == 3 for f in fb_rows):
            continue
        fb_id += 1
        fb_rows.append(dict(feedback_id=fb_id, clue_id=c['clue_id'],
                            check_result=1 if c['clue_status'] == 2 else 2, check_method=3,
                            check_remark='复核：' + ('维持属实结论' if c['clue_status'] == 2
                                                 else '复核后维持排除结论'),
                            checker_id='U0008',
                            check_time=fmt(parse(c['close_at']) + timedelta(hours=2)),
                            weight_applied=1))
    return clue_rows, fb_rows, cff_rows

# =============================================================================
# 12. 评估标签（观察段埋案）
# =============================================================================

def build_eval_labels(scores):
    # 评估标签要求"一个对象一条标签"，且与 risk_score 的 join 必须是 1:1：
    # 只挑在整个评分表中唯一出现的 object_id，否则混淆矩阵会把同一对象重复计数。
    from collections import Counter as _C
    cnt = _C((x['object_type'], x['object_id']) for x in W['risk_score'])
    taken = {l['object_id'] for l in W.get('eval_label', [])}   # 已被前一批标注的对象不再重复
    region = [s for s in scores
              if s['object_type'] == 1 and cnt[(1, s['object_id'])] == 1
              and s['object_id'] not in taken]
    clue = [s for s in region if s['is_clue'] == 1]
    noclue = [s for s in region if s['is_clue'] == 0]
    zero_hit = [s for s in noclue if sum(x['is_hit'] for x in s['features']) == 0]
    rng.shuffle(clue)
    rng.shuffle(zero_hit)
    rng.shuffle(noclue)

    labels = []
    # 正样本：16 起引擎已报警（TP）+ 4 起发生在无消费记录时段（FN）
    tp = clue[:16]
    fn = zero_hit[:4]
    for s in tp:
        labels.append(dict(object_type=1, object_id=s['object_id'], sample_type=1,
                           label=1, case_cnt=1))
    for s in fn:
        labels.append(dict(object_type=1, object_id=s['object_id'], sample_type=1,
                           label=1, case_cnt=1))
    used = {l['object_id'] for l in labels}
    # 干扰样本：确有酒水消费但当晚无酒驾（其中 6 个被误报 → FP）
    rest_clue = [s for s in clue if s['object_id'] not in used][:6]
    for s in rest_clue:
        labels.append(dict(object_type=1, object_id=s['object_id'], sample_type=2,
                           label=0, case_cnt=0))
        used.add(s['object_id'])
    noise_tn = [s for s in noclue if s['object_id'] not in used][:14]
    for s in noise_tn:
        labels.append(dict(object_type=1, object_id=s['object_id'], sample_type=2,
                           label=0, case_cnt=0))
        used.add(s['object_id'])
    # 对照样本：既无酒驾也无明显消费痕迹（TN）
    ctrl = [s for s in noclue if s['object_id'] not in used][:22]
    for s in ctrl:
        labels.append(dict(object_type=1, object_id=s['object_id'], sample_type=3,
                           label=0, case_cnt=0))
        used.add(s['object_id'])
    for l in labels:
        put('eval_label', l)
    return labels

def confusion(scores, labels):
    tp = fp = fn = tn = 0
    for l in labels:
        m = [s for s in scores if s['object_type'] == l['object_type']
             and s['object_id'] == l['object_id']]
        rows = [s['is_clue'] for s in m] or [0]
        for is_clue in rows:
            if l['label'] == 1 and is_clue == 1:
                tp += 1
            elif l['label'] == 0 and is_clue == 1:
                fp += 1
            elif l['label'] == 1:
                fn += 1
            else:
                tn += 1
    return tp, fp, fn, tn

# =============================================================================
# 13. 审计日志
# =============================================================================

def build_audit(clue_rows, fb_rows, batches):
    logs = []
    def log(uid, op, table, pk, desc, t, auto=False):
        logs.append(dict(user_id=uid, operator_tag=uid or 'system', op_type=op,
                         table_name=table, record_pk=pk, op_desc=desc, op_time=fmt(t),
                         auto=auto))

    log('U0001', 1, 'sys_user', 'U0001', '用户登录成功', datetime(2026, 11, 6, 8, 55))
    log('U0002', 1, 'sys_user', 'U0002', '用户登录成功', datetime(2026, 11, 6, 9, 2))
    log('U0004', 3, 'consume_record', None, '导入 2026-10 消费流水批次（质量校验通过）',
        datetime(2026, 11, 2, 10, 30))
    log('U0004', 3, 'taxi_order', None, '导入 2026-10 出行订单批次（质量校验通过）',
        datetime(2026, 11, 2, 10, 42))
    log('U0004', 3, 'vehicle_track', None, '导入 2026-10 卡口过车批次（质量校验通过）',
        datetime(2026, 11, 2, 11, 5))
    log('U0005', 4, 'feature_version', 'V20261001_01', '发布权重版本 1.0（旧版本自动归档）',
        datetime(2026, 11, 2, 14, 0))
    log('U0005', 4, 'feature_weight', 'V20261001_01/F001', '特征权重调整为 1.2097',
        datetime(2026, 11, 2, 14, 12))
    for b in batches:
        if b['run_status'] == 2:
            log(b['operator_id'], 7, 'judge_batch', b['batch_id'],
                '执行研判，对象 %d 个，线索 %d 条' % (b['object_cnt'], b['clue_cnt']),
                parse(b['run_at']) - timedelta(minutes=1))
        elif b['run_status'] == 3:
            log(b['operator_id'], 7, 'judge_batch', b['batch_id'],
                '研判失败：权重版本 V20261101_02 尚未计算权重',
                parse(b['run_at']) - timedelta(minutes=1))
    for c in clue_rows:
        if c['close_at']:
            log(c['assignee_id'], 4, 'risk_clue', c['clue_id'],
                '线索状态变更：0 → %d' % c['clue_status'], parse(c['close_at']), auto=True)
    log('U0006', 6, 'risk_clue', None, '导出线索清单 CSV（共 %d 条）' % len(clue_rows),
        datetime(2026, 11, 28, 9, 0))
    log('U0007', 2, 'risk_score', None, '教师账号查询区域风险汇总',
        datetime(2026, 11, 28, 10, 15))
    log('U0007', 2, 'eval_label', None, '教师账号查看评估报告',
        datetime(2026, 11, 28, 10, 22))
    log('U0001', 4, 'param_config', 'high_threshold', '参数修改：6.00 → 6.00（核对口径，未变更）',
        datetime(2026, 11, 28, 15, 0))
    log('U0006', 4, 'sys_user', 'U0010', '账号状态检查：guest 保持停用',
        datetime(2026, 11, 29, 9, 30))
    log('U0003', 1, 'sys_user', 'U0003', '用户登录成功', datetime(2026, 11, 29, 8, 40))
    logs.sort(key=lambda x: x['op_time'])
    for l in logs:
        put('audit_log', l)
    return logs

# =============================================================================
# 7b. 对照人群（P0 的分母）—— 必须在历史段痕迹全部落盘之后执行
# =============================================================================

def build_controls(fixed_controls=None, start=None, end=None, n_control=None,
                   created='2026-08-22 09:00:00'):
    """200 条对照样本：同期、同区域、同时段，只造普通流水，不写案件。"""
    fixed_controls = FIXED_HIST_CONTROL if fixed_controls is None else fixed_controls
    start = start or HIST_START
    end = end or HIST_END
    n_control = n_control or N_CONTROL
    pool = defaultdict(list)
    for a in AREA_IDS:
        for _ in range(5):
            p = new_person(1 if rng.random() < 0.82 else 2, a, 2, created=created)
            HOME[p['person_id']] = a
            PERSON_BY_ID[p['person_id']] = p
            pool[a].append(p)
    bg_persons = [new_person(1 if rng.random() < 0.8 else 2,
                             wpick(AREA_IDS, [1] * len(AREA_IDS)), 3,
                             created=created) for _ in range(32)]
    floaters = []
    for _ in range(18):
        p = new_person(1 if rng.random() < 0.8 else 2,
                       wpick(AREA_IDS, [AREA_NL[a] + 0.2 for a in AREA_IDS]), 2,
                       created=created)
        HOME[p['person_id']] = p['home_area_id']
        PERSON_BY_ID[p['person_id']] = p
        floaters.append(p)

    # ---- 原有 10 条对照：编号不变，逐条补齐本人流水（避免"缺失当未命中"） ----
    for pid, area, day, hour, mt in fixed_controls:
        put('control_person', dict(person_id=pid, area_id=area, sample_date=day,
                                   hour_slot=hour, match_type=mt))
        t = datetime.strptime('%s %02d:00:00' % (day, hour), '%Y-%m-%d %H:%M:%S')
        has = [c for c in CON_BY_PERSON.get(pid, [])
               if t - timedelta(minutes=180) <= parse(c['consume_time']) <= t]
        if not has:
            add_consume(pid, ALCOHOL_BY_AREA[area][0], t - timedelta(minutes=rng.randint(20, 110)), 0)
    build_index()
    build_person_index()

    fixed = {}
    for pid, area, day, hour, mt in fixed_controls:
        t = datetime.strptime('%s %02d:00:00' % (day, hour), '%Y-%m-%d %H:%M:%S')
        v = feat_values(pid, area, t)
        fixed[pid + day + str(hour)] = {f: (1 if HITS[f](val) else 0) for f, val in v.items()}
    fixed_cnt = {f: sum(1 for x in fixed.values() if x[f] == 1) for f in TARGET}

    n_new = n_control - len(fixed_controls)
    need = {f: TARGET[f][1] - fixed_cnt[f] for f in TARGET}
    assert all(v >= 0 for v in need.values()), need

    # ---- 人员级标签：F008/F009 先定（历史涉案样本必须在"本区"，故不参与多场所集中） ----
    f008 = [False] * n_new
    f009 = [False] * n_new
    for i in [j for j, v in enumerate(allocate(n_new, need['F009'])) if v]:
        f009[i] = True
        f008[i] = True
    for i in [j for j, v in enumerate(allocate(n_new, need['F008'] - need['F009'])) if v]:
        if not f008[i]:
            f008[i] = True
    cnt8 = sum(f008)
    for i in range(n_new - 1, -1, -1):
        if cnt8 >= need['F008']:
            break
        if not f008[i]:
            f008[i] = True
            cnt8 += 1
    assert cnt8 == need['F008'], (cnt8, need['F008'])

    f005 = allocate(n_new, need['F005'])
    for i in range(n_new):
        if f008[i]:
            f005[i] = False
    short = need['F005'] - sum(f005)
    for i in range(n_new - 1, -1, -1):
        if short <= 0:
            break
        if not f005[i] and not f008[i]:
            f005[i] = True
            short -= 1
    assert short == 0

    f002 = allocate(n_new, need['F002'])
    f003 = allocate(n_new, need['F003'])
    f006 = allocate(n_new, need['F006'])
    for i in range(n_new):
        if f006[i]:
            f003[i] = False
    short = need['F003'] - sum(f003)
    for i in range(n_new - 1, -1, -1):
        if short <= 0:
            break
        if not f003[i] and not f006[i]:
            f003[i] = True
            short -= 1
    assert short == 0

    case_by_person = defaultdict(list)
    for c in W['case_info']:
        case_by_person[c['person_id']].append(c)
    ex_offenders = dict(case_by_person)
    drunk_offenders = {p: v for p, v in ex_offenders.items()
                       if any(c['alcohol_value'] >= 80 for c in v)}

    weekend = []
    d = start
    while d <= end:
        if d.weekday() in (4, 5, 6):
            weekend.append(d)
        d += timedelta(days=1)

    def make_bucket(area, ts, g1, g4):
        venues = ALCOHOL_BY_AREA[area][:]
        rng.shuffle(venues)
        v_need = min(2 if g1 == 'hot' else 1, len(venues))
        e_need = rng.randint(5, 6) if g4 == 'hot' else 1
        for pl in venues[:v_need]:
            add_consume(rng.choice(bg_persons)['person_id'], pl,
                        ts + timedelta(minutes=rng.randint(2, 55)), 1)
            IDX_CONSUME[bh(ts)].append(W['consume_record'][-1])
        for _ in range(e_need):
            add_track(rng.choice([v['vehicle_id'] for v in W['vehicle_owner']]), area,
                      ts + timedelta(minutes=rng.randint(2, 58)), 2)
            IDX_TRACK[bh(ts)].append(W['vehicle_track'][-1])

    # ---- 装箱：同一桶内的样本共享 (F001,F004) 标签 ----
    normal_idx = [i for i in range(n_new) if not f008[i]]
    x = 26
    spec = [('hot', 'hot', x), ('hot', 'cold', need['F001'] - x),
            ('cold', 'hot', need['F004'] - x)]
    spec.append(('cold', 'cold', len(normal_idx) - sum(t[2] for t in spec)))
    assert all(t[2] >= 0 for t in spec), spec

    slots = [None] * n_new
    fixed_pid = {}
    pos = 0
    for g1, g4, cnt in spec:
        idxs = normal_idx[pos:pos + cnt]
        pos += cnt
        j = 0
        while j < len(idxs):
            k = min(rng.randint(3, 5), len(idxs) - j)
            bucket = idxs[j:j + k]
            j += k
            area = (wpick(CASE_AREAS, [AREA_NL[a] for a in CASE_AREAS]) if g1 == 'hot'
                    else wpick([a for a in AREA_IDS if ALCOHOL_BY_AREA[a]],
                               [1] * len([a for a in AREA_IDS if ALCOHOL_BY_AREA[a]])))
            ts = None
            for _ in range(80):
                day = rng.choice(weekend)
                hour = wpick([19, 20, 21, 22, 23], [0.10, 0.18, 0.28, 0.28, 0.16])
                cand = datetime(day.year, day.month, day.day, hour, 0, 0)
                if not any(PLACE_AREA[c['place_id']] == area
                           for c in IDX_CONSUME.get(bh(cand), [])):
                    ts = cand
                    break
            if ts is None:
                ts = datetime(day.year, day.month, day.day, hour, 0, 0)
            make_bucket(area, ts, g1, g4)
            for si in bucket:
                slots[si] = (g1, g4, area, ts)

    # ---- F008/F009 样本：先定人，再把时段落在其案件之后、90 天之内 ----
    for si in [i for i in range(n_new) if f008[i]]:
        poolx = [p for p in (drunk_offenders if f009[si] else ex_offenders)
                 if ALCOHOL_BY_AREA.get(HOME[p])]
        rng.shuffle(poolx)
        chosen = None
        for pid_ in poolx:
            cs = [c for c in case_by_person[pid_]
                  if (not f009[si]) or c['alcohol_value'] >= 80]
            anchor = min(parse(c['occur_time']) for c in case_by_person[pid_])
            hi = min(anchor + timedelta(days=88), datetime(2026, 10, 31, 22, 0))
            days = [w for w in weekend
                    if anchor + timedelta(hours=8) <= datetime(w.year, w.month, w.day, 23, 0) <= hi]
            if days:
                chosen = (pid_, rng.choice(days))
                break
        if chosen is None:
            # 没有可用前科人员：退化为普通对照（该样本不计 F008 命中，校验会提示）
            slots[si] = ('cold', 'cold', None, None)
            continue
        pid_, day = chosen
        area = HOME[pid_]
        hour = wpick([19, 20, 21, 22, 23], [0.10, 0.18, 0.28, 0.28, 0.16])
        ts = datetime(day.year, day.month, day.day, hour, 0, 0)
        if any(PLACE_AREA[c['place_id']] == area for c in IDX_CONSUME.get(bh(ts), [])):
            ts = ts + timedelta(days=7)
        make_bucket(area, ts, 'cold', 'cold')
        slots[si] = ('cold', 'cold', area, ts)
        fixed_pid[si] = pid_

    used = {(x[0], str(x[2]), x[3]) for x in fixed_controls}
    used_date = {(x[0], str(x[2])) for x in fixed_controls}
    for si, (g1, g4, area, ts) in enumerate(slots):
        if area is None:
            # 退化样本：放到任意空桶，仅作普通对照
            area = wpick([a for a in AREA_IDS if ALCOHOL_BY_AREA[a]], [1] * 10)
            ts = datetime(rng.choice(weekend).year, rng.choice(weekend).month,
                          rng.choice(weekend).day, 21, 0, 0)
            make_bucket(area, ts, 'cold', 'cold')
        if si in fixed_pid:
            pid = fixed_pid[si]
        elif f005[si]:
            cand = [p['person_id'] for p in floaters + pool[area] if HOME[p['person_id']] != area]
            pid = rng.choice(cand or [p['person_id'] for p in floaters])
            guard = 0
            while ((pid, ts.strftime('%Y-%m-%d'), ts.hour) in used or
                   (pid, ts.strftime('%Y-%m-%d')) in used_date) and guard < 60:
                guard += 1
                pid = rng.choice([p['person_id'] for p in floaters])
        else:
            cand = [p['person_id'] for p in pool[area]]
            pid = rng.choice(cand)
            guard = 0
            while ((pid, ts.strftime('%Y-%m-%d'), ts.hour) in used or
                   (pid, ts.strftime('%Y-%m-%d')) in used_date) and guard < 60:
                guard += 1
                pid = rng.choice(cand)

        if guard >= 60:
            # 兜底：本区同一天可抽样的人不够，就从"无前科"的人员里补一个
            spare = [x['person_id'] for x in W['person_info']
                     if x['person_type'] in (2, 3)
                     and x['person_id'] in HOME
                     and x['person_id'] not in case_by_person
                     and (x['home_area_id'] != area) == bool(f005[si])
                     and (x['person_id'], ts.strftime('%Y-%m-%d')) not in used_date]
            if spare:
                pid = rng.choice(spare)
        used.add((pid, ts.strftime('%Y-%m-%d'), ts.hour))
        used_date.add((pid, ts.strftime('%Y-%m-%d')))
        put('control_person', dict(person_id=pid, area_id=area,
                                   sample_date=ts.strftime('%Y-%m-%d'), hour_slot=ts.hour,
                                   match_type=wpick([1, 2, 3], [0.7, 0.2, 0.1])))
        add_consume(pid, wpick(ALCOHOL_BY_AREA[area], [1.0] * len(ALCOHOL_BY_AREA[area])),
                    ts - timedelta(minutes=rng.randint(15, 150)), 1 if f002[si] else 0)
        if f006[si]:
            add_order(pid, 2, ts - timedelta(minutes=rng.randint(10, 70)), area,
                      HOME.get(pid) or area, 1)
        elif not f003[si]:
            add_order(pid, 1, ts - timedelta(minutes=rng.randint(10, 70)), area,
                      HOME.get(pid) or area, 1)


# =============================================================================
# 15. 第二波：追加数据（第一批 3219 行保持逐字节不变）
# -----------------------------------------------------------------------------
#  做法：把"又补了两个月历史案件 + 又跑了 12 月四个夜晚"当成第二次导入，
#       而不是改参数重算——改参数会让随机流整体平移，第一批所有编号都会变。
#  时间轴（两批拼起来）：
#    2026-07-01 ─ 08-31 │ 09-01 ─ 10-31 │ 11-01 ─ 11-30 │ 12-01 ─ 12-31
#        第二批历史(补录) │   第一批历史    │  第一批观察    │  第二批观察
#                        ↑ 观察段起点不变（history_cutoff = 2026-11-01）
# =============================================================================

W2_SEED = 20261204
W2_HIST_START = date(2026, 7, 1)
W2_HIST_END = date(2026, 8, 29)      # 留 2 天余量：跨零点案件最晚落在 8-30 凌晨
W2_NIGHTS = [date(2026, 12, 4), date(2026, 12, 11), date(2026, 12, 18), date(2026, 12, 25)]
W2_SCHEDULE = [
    ['A01', 'A02', 'A03', 'A04'],
    ['A05', 'A06', 'A07', 'A11'],
    ['A09', 'A10', 'A12', 'A04'],
    ['A06', 'A09', 'A12', 'A10'],
]
# 12 月为年末聚餐高峰：与 11 月同一时段相比，场所与车流都更密，
# 但仍保持"高风险桶少、平常桶多"的总体结构（只影响第二批，第一批剖面不动）。
W2_PROFILES = {
    'high':  ((2, 4), (7, 9), True),
    'mid':   ((2, 3), (4, 6), True),
    'd24':   ((1, 1), (7, 8), True),
    'solo4': ((0, 0), (7, 8), False),
    'low':   ((1, 1), (3, 4), True),
    'plain': ((0, 0), (3, 4), False),
}

# 时段优先级：先给夜间高峰，再给傍晚/凌晨，保证每个区域取到的桶都有实际意义
W2_ORDER_1 = [21, 22, 20, 23, 19, 18, 17]          # 周五傍晚~深夜（day_type = 1）
W2_ORDER_2 = [0, 1, 2, 3, 4, 5]                      # 周六凌晨（day_type = 2）


def wave2_plan():
    """挑出第一批没占用过的 (区域, 日期类型, 小时) 组合，每个批次 4 个桶。"""
    used = {(x['area_id'], x['day_type'], x['hour_slot'])
            for x in W['risk_score'] if x['object_type'] == 1}
    pools = {}
    for a in AREA_IDS:
        pool = [(1, h) for h in W2_ORDER_1] + [(2, h) for h in W2_ORDER_2]
        pools[a] = [c for c in pool if (a, c[0], c[1]) not in used]

    def profiles(area):
        n = len(ALCOHOL_BY_AREA[area])
        if n == 0:
            return ['solo4', 'plain', 'solo4', 'plain']
        if n == 1:
            # 只有一家酒水场所的区域：靠"含酒水消费 + 驶出车辆多"凑出中等风险对象
            return ['low', 'd24', 'plain', 'low']
        return ['high', 'mid', 'low', 'plain']

    plan = []
    for ni, night in enumerate(W2_NIGHTS):
        area_map = {}
        for area in W2_SCHEDULE[ni]:
            combos = pools[area][:4]
            pools[area] = pools[area][4:]
            assert len(combos) == 4, ('该区域可用时段不足', area, len(combos))
            prof = profiles(area)
            area_map[area] = [(dtp, hour, prof[i]) for i, (dtp, hour) in enumerate(combos)]
        plan.append((night, area_map))
    return plan


def build_batches_wave2(plan):
    """第二批：每个(夜晚,区域)一个区域批次，另加 2 个个人批次与 2 个待执行批次。"""
    B = []

    def add(bid, rid, vid, jo, ds, de, area, status, run_no, dur, op, created):
        row = dict(batch_id=bid, rule_id=rid, version_id=vid, judge_object=jo,
                   data_start=ds, data_end=de, area_id=area, run_status=status,
                   run_no=run_no, object_cnt=0, clue_cnt=0, duration_ms=dur,
                   operator_id=op, created_at=created, run_at=created)
        B.append(row)
        return row

    for ni, (night, area_map) in enumerate(plan):
        code = night.strftime('%Y%m%d')
        ds = '%s 17:00:00' % night.strftime('%Y-%m-%d')
        de = '%s 06:00:00' % (night + timedelta(days=1)).strftime('%Y-%m-%d')
        for i, area in enumerate(area_map.keys()):
            at = '%s 08:%02d:00' % ((night + timedelta(days=1)).strftime('%Y-%m-%d'), i * 10)
            add('B%s%02d' % (code, i + 1), 'R001', 'V20261001_01', 1, ds, de, area, 2, 1,
                None, 'U0002' if i < 2 else 'U0003', at)
    # 个人研判：取当晚流水最集中的两个小时（按桶数统计），保证有足够对象
    plan_by_night = {n: am for n, am in plan}
    for night in [W2_NIGHTS[0], W2_NIGHTS[2]]:
        hours = [h for combos in plan_by_night[night].values()
                 for (dtp, h, _p) in combos if dtp == 1]
        peak = sorted(hours, key=lambda x: (-hours.count(x), x))[0]
        h0, h1 = peak, min(peak + 2, 24)
        code = night.strftime('%Y%m%d')
        at = '%s 09:10:00' % (night + timedelta(days=1)).strftime('%Y-%m-%d')
        add('B%s10' % code, 'R002', 'V20261001_01', 2,
            '%s %02d:00:00' % (night.strftime('%Y-%m-%d'), h0),
            '%s %02d:00:00' % (night.strftime('%Y-%m-%d'), h1),
            None, 2, 1, None, 'U0003', at)
    # 待执行：等下一轮值班人员跑
    for i, area in enumerate(['A06', 'A12']):
        at = '2026-12-26 09:%02d:00' % (30 + i * 10)
        add('B20261226%02d' % (i + 1), 'R001', 'V20261001_01', 1,
            '2026-12-25 17:00:00', '2026-12-26 06:00:00', area, 0, 0, None,
            'U0002' if i == 0 else 'U0003', at)
    for b in B:
        if b['run_status'] == 2 and b['duration_ms'] is None:
            b['duration_ms'] = rng.randint(520, 1900) if b['judge_object'] == 1 else rng.randint(700, 2400)
    return B


def build_audit_wave2(clue_rows, batches):
    logs = []

    def log(uid, op, table, pk, desc, t, auto=False):
        logs.append(dict(user_id=uid, operator_tag=uid or 'system', op_type=op,
                         table_name=table, record_pk=pk, op_desc=desc,
                         op_time=fmt(t) if isinstance(t, datetime) else t, auto=auto))

    log('U0004', 3, 'consume_record', None, '补录 2026-07~08 消费流水（质量校验通过）',
        datetime(2026, 12, 2, 10, 20))
    log('U0004', 3, 'taxi_order', None, '补录 2026-07~08 出行订单（质量校验通过）',
        datetime(2026, 12, 2, 10, 36))
    log('U0004', 3, 'vehicle_track', None, '补录 2026-07~08 卡口过车（质量校验通过）',
        datetime(2026, 12, 2, 10, 52))
    log('U0004', 3, 'case_info', None, '补录 2026-07~08 历史案件 100 起', datetime(2026, 12, 2, 11, 10))
    log('U0005', 4, 'feature_weight', 'V20261115_03/F001',
        '按全量两批数据重算草稿版本权重（待评审发布）', datetime(2026, 12, 2, 15, 0))
    for b in batches:
        if b['run_status'] == 2:
            log(b['operator_id'], 7, 'judge_batch', b['batch_id'],
                '执行研判，对象 %d 个，线索 %d 条' % (b['object_cnt'], b['clue_cnt']),
                parse(b['run_at']) - timedelta(minutes=1))
    for c in clue_rows:
        if c['close_at']:
            log(c['assignee_id'], 4, 'risk_clue', c['clue_id'],
                '线索状态变更：0 → %d' % c['clue_status'], parse(c['close_at']), auto=True)
    log('U0006', 6, 'risk_clue', None, '导出 12 月线索清单 CSV', datetime(2026, 12, 27, 9, 0))
    log('U0007', 2, 'eval_label', None, '教师账号复核新增批次的评估结果',
        datetime(2026, 12, 27, 10, 30))
    log('U0002', 1, 'sys_user', 'U0002', '用户登录成功', datetime(2026, 12, 28, 8, 40))
    logs.sort(key=lambda x: x['op_time'])
    for l in logs:
        put('audit_log', l)
    return logs

# =============================================================================
# 14. 校验
# =============================================================================

def verify():
    errs = []
    def ck(cond, msg):
        if not cond:
            errs.append(msg)

    persons = {p['person_id'] for p in W['person_info']}
    areas = {a['area_id'] for a in W['area_info']}
    places = {p['place_id'] for p in W['place_info']}
    vehicles = {v['vehicle_id'] for v in W['vehicle_owner']}
    users = {u['user_id'] for u in W['sys_user']}

    for c in W['case_info']:
        ck(parse(c['occur_time']) < CUTOFF, 'case after cutoff: ' + c['case_id'])
    for c in W['consume_record']:
        ck(parse(c['consume_time']) >= datetime(2026, 7, 1), 'consume too early: ' + c['record_no'])
    for b in W['judge_batch']:
        ck(parse(b['data_start']) >= CUTOFF, 'batch window before cutoff: ' + b['batch_id'])
        ck(parse(b['data_end']) > parse(b['data_start']), 'batch window invalid: ' + b['batch_id'])
        ck(b['run_status'] != 2 or b['duration_ms'] is not None, 'duration missing: ' + b['batch_id'])
        ck(parse(b['data_end']) <= datetime(2027, 1, 1), 'batch beyond observation: ' + b['batch_id'])

    for c in W['consume_record']:
        ck(c['person_id'] in persons, 'orphan consume person ' + c['record_no'])
        ck(c['place_id'] in places, 'orphan consume place ' + c['record_no'])
        ck(0 <= c['amount'] <= 100000, 'amount out of range ' + c['record_no'])
        ck(c['has_alcohol'] in (0, 1), 'has_alcohol ' + c['record_no'])
    for o in W['taxi_order']:
        ck(o['person_id'] in persons, 'orphan order person ' + o['order_no'])
        ck(o['start_area_id'] in areas and o['end_area_id'] in areas, 'orphan order area ' + o['order_no'])
        ck(o['order_type'] in (1, 2) and o['order_status'] in (1, 2, 3), 'order enum ' + o['order_no'])
    for t in W['vehicle_track']:
        ck(t['vehicle_id'] in vehicles, 'orphan track vehicle ' + t['record_no'])
        ck(t['area_id'] == t['gate_id'].split('-')[0], 'gate prefix mismatch ' + t['record_no'])
        ck(t['area_id'] in areas, 'orphan track area ' + t['record_no'])
        ck(t['direction'] in (1, 2), 'track direction ' + t['record_no'])
    for c in W['case_info']:
        ck(c['person_id'] in persons and c['area_id'] in areas, 'case fk ' + c['case_id'])
        ck(c['place_id'] in places, 'case place fk ' + c['case_id'])
        ck(c['vehicle_id'] is None or c['vehicle_id'] in vehicles, 'case vehicle fk ' + c['case_id'])
        ck(0 < c['alcohol_value'] <= 500, 'alcohol range ' + c['case_id'])
        ck(c['distance_home'] is None or 0 <= c['distance_home'] <= 200, 'distance ' + c['case_id'])
        ck(c['case_type'] in (1, 2, 3) and c['dispose_status'] in (0, 1, 2, 3), 'case enum ' + c['case_id'])
    for s in W['control_person']:
        ck(s['person_id'] in persons and s['area_id'] in areas, 'control fk ' + str(s))
        ck(0 <= s['hour_slot'] <= 23, 'control hour ' + str(s))

    def uniq(rows, key, label):
        seen = set()
        for r in rows:
            k = key(r)
            if k in seen:
                errs.append('duplicate %s: %s' % (label, k))
            seen.add(k)
    uniq(W['case_info'], lambda r: r['case_id'], 'case_id')
    uniq(W['consume_record'], lambda r: r['record_no'], 'record_no')
    uniq(W['taxi_order'], lambda r: r['order_no'], 'order_no')
    uniq(W['vehicle_track'], lambda r: r['record_no'], 'track_no')
    uniq(W['person_info'], lambda r: r['phone'], 'phone')
    uniq(W['vehicle_owner'], lambda r: r['plate'], 'plate')
    uniq(W['control_person'], lambda r: (r['person_id'], r['sample_date'], r['hour_slot']), 'uk_control')
    uniq(W['eval_label'], lambda r: (r['object_type'], r['object_id']), 'uk_eval')
    uniq(W['risk_score'], lambda r: (r['batch_id'], r['object_type'], r['object_id']), 'uk_batch_object')
    uniq(W['risk_clue'], lambda r: r['score_id'], 'uk_clue_score')
    uniq(W['feature_weight'], lambda r: (r['version_id'], r['feature_id']), 'uk_weight')
    uniq(W['risk_score_feature'], lambda r: (r['score_id'], r['feature_id']), 'uk_ssf')

    ver_base = {v['version_id']: (v['based_case_cnt'], v['based_ctrl_cnt'])
                for v in W['feature_version']}
    for w in W['feature_weight']:
        ck(w['case_hit'] <= w['case_total'] and w['ctrl_hit'] <= w['ctrl_total'],
           'hit > total ' + w['feature_id'])
        ck(abs(w['p1'] - round(w['case_hit'] / w['case_total'], 4)) < 1e-9, 'p1 mismatch ' + w['feature_id'])
        ck(abs(w['p0'] - round(w['ctrl_hit'] / w['ctrl_total'], 4)) < 1e-9, 'p0 mismatch ' + w['feature_id'])
        ck((w['case_total'], w['ctrl_total']) == ver_base[w['version_id']],
           'sample size mismatch ' + w['feature_id'])
        expect = max(-3.0, min(3.0, round(math.log(
            ((w['case_hit'] + 0.5) / (w['case_total'] - w['case_hit'] + 0.5)) /
            ((w['ctrl_hit'] + 0.5) / (w['ctrl_total'] - w['ctrl_hit'] + 0.5))), 4)))
        ck(abs(w['weight'] - expect) < 1e-9, 'weight not reproducible ' + w['feature_id'])
        ck(-3 <= w['weight'] <= 3, 'weight out of range ' + w['feature_id'])

    for s in W['risk_score']:
        rows = [x for x in W['risk_score_feature'] if x['score_id'] == s['score_id']]
        ck(len(rows) >= 3, 'too few features for score %d' % s['score_id'])
        total = round(sum(x['is_hit'] * x['weight'] for x in rows), 2)
        ck(abs(total - s['total_score']) < 0.005, 'score not reproducible %d' % s['score_id'])
        if s['object_type'] == 1:
            ck(bool(s['area_id']) and bool(s['day_type']) and s['hour_slot'] is not None,
               'region fields %d' % s['score_id'])
            ck(s['object_id'] == '%s#%d#%02d' % (s['area_id'], s['day_type'], s['hour_slot']),
               'object_id mismatch %d' % s['score_id'])
        else:
            ck(s['person_id'] is not None and s['object_id'] == s['person_id'],
               'person object mismatch %d' % s['score_id'])

    clue_scores = {c['score_id'] for c in W['risk_clue']}
    ck(clue_scores == {s['score_id'] for s in W['risk_score'] if s['is_clue'] == 1},
       'clue / is_clue mismatch')
    for c in W['risk_clue']:
        ck((c['clue_status'] in (2, 3)) == (c['close_at'] is not None),
           'ck_clue_close violated ' + c['clue_id'])
    for f in W['clue_feedback']:
        ck(f['check_result'] in (1, 2, 3) and f['check_method'] in (1, 2, 3), 'feedback enum')
        ck(f['checker_id'] in users, 'feedback checker')
    hit_map = defaultdict(set)
    for x in W['risk_score_feature']:
        if x['is_hit'] == 1:
            hit_map[x['score_id']].add(x['feature_id'])
    for cf in W['clue_feedback_feature']:
        fb = next(f for f in W['clue_feedback'] if f['feedback_id'] == cf['feedback_id'])
        clue = next(c for c in W['risk_clue'] if c['clue_id'] == fb['clue_id'])
        ck(cf['feature_id'] in hit_map[clue['score_id']], 'negated feature not hit: ' + str(cf))

    for b in W['judge_batch']:
        n_obj = len([s for s in W['risk_score'] if s['batch_id'] == b['batch_id']])
        n_clue = len([c for c in W['risk_clue'] if c['batch_id'] == b['batch_id']])
        ck(b['object_cnt'] == n_obj, 'object_cnt mismatch ' + b['batch_id'])
        ck(b['clue_cnt'] == n_clue, 'clue_cnt mismatch ' + b['batch_id'])

    for l in W['eval_label']:
        ck(any(s['object_type'] == l['object_type'] and s['object_id'] == l['object_id']
               for s in W['risk_score']), 'label without score: ' + l['object_id'])
        ck(l['sample_type'] in (1, 2, 3) and l['label'] in (0, 1), 'label enum')
    tp, fp, fn, tn = confusion(W['risk_score'], W['eval_label'])
    ck(tp + fn > 0 and fp + tn > 0, 'confusion matrix degenerate')

    if errs:
        print('校验失败 %d 项：' % len(errs))
        for e in errs[:40]:
            print('  -', e)
        raise SystemExit(1)
    print('校验通过：约束 / 外键 / 唯一键 / 派生列 / 线索闭环 / 批次计数 / 评估标签 全部一致')
    return tp, fp, fn, tn

# =============================================================================
# 15. 落盘：SQL 数据段
# =============================================================================

def q(v):
    return "'" + str(v).replace('\\', '\\\\').replace("'", "''") + "'"

def chunks(rows, n=40):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]

def emit_sql(data_sql):
    with open(SQL_PATH, encoding='utf-8') as f:
        orig = f.read()
    sep = '-- =============================================================================\n'
    i_ddl = orig.index(sep + '--  一、建表（26 张）')
    i_data = orig.index(sep + '--  四、示例数据（全部虚构）')
    ddl = orig[i_ddl:i_data]
    head = header_text()
    with open(SQL_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + ddl + data_sql)

def header_text():
    c = {k: len(v) for k, v in W.items()}
    total = sum(c.values())
    return """-- =============================================================================
--  多风险特征预警系统 · 示例数据库（方案 C + 审查整改版 · 两批扩充数据集）
--  库名：risk_alert        引擎：InnoDB        字符集：utf8mb4 / utf8mb4_0900_as_cs
--  数据：全部虚构，仅用于课程演示
--  用法：MySQL 8.0+ 整份执行（mysql -u root -p < risk_alert_示例库.sql）
-- -----------------------------------------------------------------------------
--  结构：区域表 area_info 新增经纬度字段（lng/lat + 1 个 CHECK，用于前端风险地图），
--  其余结构未变（26 张表 / 45 个外键 / 65 个 CHECK / 3 个触发器 / 2 个存储过程 /
--  3 个视图）；数据仅扩充：259 行 → 第一批 3219 行 → 本版 %d 行。
--    · 主数据：区域 %d、场所 %d、人员 %d、车辆 %d
--    · 案例库：案件 %d（分两批补录）、对照样本 %d
--    · 信息库：消费 %d、出行订单 %d、卡口过车 %d
--    · 研判：批次 %d、评分 %d、命中明细 %d、线索 %d、核查反馈 %d、评估标签 %d
--    · 派生列（p1/p0/lift、object_id、occur_hour、total_score）全部由数据库计算，
--      脚本里不出现手填值；权重由四个命中数经同一公式算出，可复算
--  两批数据的时间轴（第二批只追加，不改动第一批任何一行）：
--    2026-07-01 ─ 08-30 │ 09-01 ─ 10-31 │ 11-01 ─ 11-30 │ 12-01 ─ 12-31
--       第二批历史(补录) │    第一批历史   │   第一批观察   │   第二批观察
--                        ↑ history_cutoff = 2026-11-01（观察段起点未变）
--  权重版本 v1.0 仍锁定在首批 100 起案件 / 200 条对照上（based_case_cnt 可查），
--  第二批属于补录，纳入统计需另发版本，故 feature_weight 未动、重算仍为幂等。
--  数据生成：tools/gen_demo_data.py（固定随机种子，两批各自独立随机源，可复算）
-- =============================================================================

DROP DATABASE IF EXISTS risk_alert;
CREATE DATABASE risk_alert DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
USE risk_alert;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;

""" % (total, c['area_info'], c['place_info'], c['person_info'], c['vehicle_owner'],
       c['case_info'], c['control_person'], c['consume_record'], c['taxi_order'],
       c['vehicle_track'], c['judge_batch'], c['risk_score'], c['risk_score_feature'],
       c['risk_clue'], c['clue_feedback'], c['eval_label'])


def sql_data_section(tp, fp, fn, tn):
    L = []
    A = L.append
    A(sep_line('四、示例数据（全部虚构）'))
    A('-- 说明：本节由 tools/gen_demo_data.py 生成，派生列不参与 INSERT。')
    A('')
    A(sep_line('4.1 安全支撑库'))
    A('-- 角色（5）')
    A(ins('sys_role', ['role_id', 'role_name', 'role_desc', 'status'], W['sys_role'],
          lambda r: [q(r['role_id']), q(r['role_name']), q(r['role_desc']), str(r['status'])]))
    A('-- 用户（10），演示口令 123456')
    A(ins('sys_user', ['user_id', 'username', 'password_hash', 'salt', 'real_name', 'status',
                       'created_at'], W['sys_user'],
          lambda r: [q(r['user_id']), q(r['username']),
                     "SHA2(CONCAT('%s','123456'),256)" % r['salt'], q(r['salt']),
                     q(r['real_name']), str(r['status']), q(r['created_at'])]))
    A(ins('sys_user_role', ['user_id', 'role_id', 'granted_at'], W['sys_user_role'],
          lambda r: [q(r['user_id']), q(r['role_id']), q(r['granted_at'])]))
    A('-- 参数（9；history_cutoff 已在第二节写入）')
    A(ins('param_config', ['param_key', 'param_value', 'param_type', 'param_desc', 'updated_at'],
          [p for p in W['param_config'] if p['param_key'] != 'history_cutoff'],
          lambda r: [q(r['param_key']), q(r['param_value']), str(r['param_type']),
                     q(r['param_desc']), q(r['updated_at'])]))

    A('')
    A(sep_line('4.2 案例库'))
    A('-- 区域（%d）' % len(W['area_info']))
    A(ins('area_info', ['area_id', 'area_name', 'area_type', 'parent_area_id', 'is_active',
                        'lng', 'lat', 'created_at'], W['area_info'],
          lambda r: [q(r['area_id']), q(r['area_name']), str(r['area_type']),
                     q(r['parent_area_id']) if r['parent_area_id'] else 'NULL',
                     str(r['is_active']), q(r['lng']), q(r['lat']), q(r['created_at'])]))
    A('-- 场所（%d）：1 饭店 / 2 KTV / 3 酒吧 / 4 其他' % len(W['place_info']))
    A(ins('place_info', ['place_id', 'place_name', 'place_type', 'area_id', 'address', 'is_active'],
          W['place_info'],
          lambda r: [q(r['place_id']), q(r['place_name']), str(r['place_type']),
                     q(r['area_id']), q(r['address']), str(r['is_active'])]))
    A('-- 人员（%d）：phone_hash 只存散列，不存明文' % len(W['person_info']))
    A(ins('person_info', ['person_id', 'person_name', 'gender', 'birth_year', 'phone_hash',
                          'home_area_id', 'person_type', 'created_at'], W['person_info'],
          lambda r: [q(r['person_id']), q(r['person_name']), str(r['gender']),
                     str(r['birth_year']), "SHA2('%s',256)" % r['phone'],
                     q(r['home_area_id']) if r['home_area_id'] else 'NULL',
                     str(r['person_type']), q(r['created_at'])]))
    A('-- 车辆（%d）：plate_hash 只存散列' % len(W['vehicle_owner']))
    A(ins('vehicle_owner', ['vehicle_id', 'plate_hash', 'plate_mask', 'owner_person_id',
                            'vehicle_type', 'is_active'], W['vehicle_owner'],
          lambda r: [q(r['vehicle_id']), "SHA2('%s',256)" % r['plate'], q(r['plate_mask']),
                     q(r['owner_person_id']), str(r['vehicle_type']), str(r['is_active'])]))
    A('-- 案件（%d）：全部在历史段；occur_hour 是生成列，不参与插入' % len(W['case_info']))
    A(ins('case_info', ['case_id', 'occur_time', 'area_id', 'place_id', 'person_id',
                        'vehicle_id', 'driver_confirmed', 'case_type', 'alcohol_value',
                        'distance_home', 'dispose_status', 'created_at'], W['case_info'],
          lambda r: [q(r['case_id']), q(r['occur_time']), q(r['area_id']), q(r['place_id']),
                     q(r['person_id']), q(r['vehicle_id']) if r['vehicle_id'] else 'NULL',
                     str(r['driver_confirmed']), str(r['case_type']),
                     '%.1f' % r['alcohol_value'],
                     '%.2f' % r['distance_home'] if r['distance_home'] is not None else 'NULL',
                     str(r['dispose_status']), q(r['created_at'])]))
    A('-- 对照人群（%d）' % len(W['control_person']))
    A(ins('control_person', ['person_id', 'area_id', 'sample_date', 'hour_slot', 'match_type'],
          W['control_person'],
          lambda r: [q(r['person_id']), q(r['area_id']), q(r['sample_date']),
                     str(r['hour_slot']), str(r['match_type'])]))

    A('')
    A(sep_line('4.3 信息库（历史段 + 观察段）'))
    A('-- 消费流水（%d）' % len(W['consume_record']))
    A(ins('consume_record', ['record_no', 'person_id', 'place_id', 'consume_time', 'amount',
                             'has_alcohol'], W['consume_record'],
          lambda r: [q(r['record_no']), q(r['person_id']), q(r['place_id']),
                     q(r['consume_time']), '%.2f' % r['amount'], str(r['has_alcohol'])]))
    A('-- 出行订单（%d）：1 网约车 / 2 代驾' % len(W['taxi_order']))
    A(ins('taxi_order', ['order_no', 'person_id', 'order_type', 'order_time', 'start_area_id',
                         'end_area_id', 'order_status'], W['taxi_order'],
          lambda r: [q(r['order_no']), q(r['person_id']), str(r['order_type']),
                     q(r['order_time']), q(r['start_area_id']), q(r['end_area_id']),
                     str(r['order_status'])]))
    A('-- 卡口过车（%d）：area_id 由 CHECK 强制与 gate_id 前缀一致' % len(W['vehicle_track']))
    A(ins('vehicle_track', ['record_no', 'vehicle_id', 'gate_id', 'area_id', 'pass_time',
                            'direction'], W['vehicle_track'],
          lambda r: [q(r['record_no']), q(r['vehicle_id']), q(r['gate_id']), q(r['area_id']),
                     q(r['pass_time']), str(r['direction'])]))

    A('')
    A(sep_line('4.4 特征库'))
    A('-- 特征（8）：双口径 src_table / match_src')
    A(ins('feature_def', ['feature_id', 'feature_code', 'feature_name', 'risk_type',
                          'feature_cat', 'direction', 'object_scope', 'value_type',
                          'src_table', 'match_src', 'match_expr', 'time_window_min',
                          'min_sample', 'status', 'description'], W['feature_def'],
          lambda r: [q(r['feature_id']), q(r['feature_code']), q(r['feature_name']),
                     str(r['risk_type']), str(r['feature_cat']), str(r['direction']),
                     str(r['object_scope']), str(r['value_type']), q(r['src_table']),
                     q(r['match_src']), q(r['match_expr']), str(r['time_window_min']),
                     str(r['min_sample']), str(r['status']), q(r['description'])]))
    A('-- 版本（3）：current_flag 生成列 + 唯一键，同风险类型只能有一个已发布版本')
    A(ins('feature_version', ['version_id', 'risk_type', 'version_no', 'publish_status',
                              'based_case_cnt', 'based_ctrl_cnt', 'calc_at', 'published_by',
                              'remark', 'created_at'], W['feature_version'],
          lambda r: [q(r['version_id']), str(r['risk_type']), q(r['version_no']),
                     str(r['publish_status']), str(r['based_case_cnt']),
                     str(r['based_ctrl_cnt']), q(r['calc_at']), q(r['published_by']),
                     q(r['remark']), q(r['created_at'])]))
    A('-- 权重（8）：p1/p0/lift 由生成列自动算，这里只给四个命中数与 weight')
    A(ins('feature_weight', ['version_id', 'feature_id', 'case_hit', 'case_total', 'ctrl_hit',
                             'ctrl_total', 'weight', 'is_valid', 'calc_at'],
          W['feature_weight'],
          lambda r: [q(r['version_id']), q(r['feature_id']), str(r['case_hit']),
                     str(r['case_total']), str(r['ctrl_hit']), str(r['ctrl_total']),
                     '%.4f' % r['weight'], str(r['is_valid']), q(r['calc_at'])]))
    A('-- 规则（3）')
    A(ins('judge_rule', ['rule_id', 'rule_name', 'risk_type', 'version_id', 'judge_object',
                         'min_sample', 'min_hit_cnt', 'low_threshold', 'high_threshold',
                         'counter_block', 'status', 'remark', 'created_at'], W['judge_rule'],
          lambda r: [q(r['rule_id']), q(r['rule_name']), str(r['risk_type']),
                     q(r['version_id']), str(r['judge_object']), str(r['min_sample']),
                     str(r['min_hit_cnt']), '%.2f' % r['low_threshold'],
                     '%.2f' % r['high_threshold'], str(r['counter_block']),
                     str(r['status']), q(r['remark']), q(r['created_at'])]))
    A(ins('rule_feature', ['rule_id', 'feature_id', 'is_required', 'sort_no'],
          W['rule_feature'],
          lambda r: [q(r['rule_id']), q(r['feature_id']), str(r['is_required']),
                     str(r['sort_no'])]))

    A('')
    A(sep_line('4.5 研判线索库'))
    A('-- 批次（%d）' % len(W['judge_batch']))
    A(ins('judge_batch', ['batch_id', 'rule_id', 'version_id', 'judge_object', 'data_start',
                          'data_end', 'area_id', 'run_status', 'run_no', 'object_cnt',
                          'clue_cnt', 'duration_ms', 'operator_id', 'created_at'],
          W['judge_batch'],
          lambda r: [q(r['batch_id']), q(r['rule_id']), q(r['version_id']),
                     str(r['judge_object']), q(r['data_start']), q(r['data_end']),
                     q(r['area_id']) if r['area_id'] else 'NULL', str(r['run_status']),
                     str(r['run_no']), str(r['object_cnt']), str(r['clue_cnt']),
                     str(r['duration_ms']) if r['duration_ms'] is not None else 'NULL',
                     q(r['operator_id']), q(r['created_at'])]))
    A('-- 评分（%d）：object_id 是生成列，不参与插入' % len(W['risk_score']))
    A(ins('risk_score', ['score_id', 'batch_id', 'rule_id', 'version_id', 'object_type',
                         'area_id', 'day_type', 'hour_slot', 'person_id', 'sample_size',
                         'total_score', 'risk_level', 'is_clue', 'created_at'],
          W['risk_score'],
          lambda r: [str(r['score_id']), q(r['batch_id']), q(r['rule_id']),
                     q(r['version_id']), str(r['object_type']),
                     q(r['area_id']) if r['area_id'] else 'NULL',
                     str(r['day_type']) if r['day_type'] else 'NULL',
                     str(r['hour_slot']) if r['hour_slot'] is not None else 'NULL',
                     q(r['person_id']) if r['person_id'] else 'NULL',
                     str(r['sample_size']), '%.2f' % r['total_score'],
                     str(r['risk_level']), str(r['is_clue']), q(r['created_at'])]))
    A('-- 命中明细（%d）：包含未命中与缺失，才能区分"没命中"和"没评估"' % len(W['risk_score_feature']))
    A(ins('risk_score_feature', ['score_id', 'feature_id', 'is_hit', 'weight', 'hit_value',
                                 'is_missing'], W['risk_score_feature'],
          lambda r: [str(r['score_id']), q(r['feature_id']), str(r['is_hit']),
                     '%.4f' % r['weight'],
                     '%.2f' % r['hit_value'] if r['hit_value'] is not None else 'NULL',
                     str(r['is_missing'])]))
    A('-- 线索（%d）：状态为 0/1 的按原样插入；已确认/已排除的由反馈触发器推进' % len(W['risk_clue']))
    A(ins('risk_clue', ['clue_id', 'batch_id', 'score_id', 'version_id', 'clue_status',
                        'assignee_id', 'create_at'], W['risk_clue'],
          lambda r: [q(r['clue_id']), q(r['batch_id']), str(r['score_id']),
                     q(r['version_id']), str(r['_pre_status']),
                     q(r['assignee_id']), q(r['create_at'])]))
    A('')
    A('-- 核查反馈（%d）：插入即触发 trg_feedback_close_clue，自动推进线索状态并写 close_at' % len(W['clue_feedback']))
    cur = None
    for f in W['clue_feedback']:
        if f['checker_id'] != cur:
            cur = f['checker_id']
            A("SET @app_user_id = '%s';" % cur)
        A("INSERT INTO clue_feedback (clue_id, check_result, check_method, check_remark, checker_id,"
          " check_time, weight_applied) VALUES")
        A("(%s,%d,%d,%s,%s,%s,%d);" % (q(f['clue_id']), f['check_result'], f['check_method'],
                                        q(f['check_remark']), q(f['checker_id']),
                                        q(f['check_time']), f['weight_applied']))
    A('')
    A('-- 触发器写审计时 op_time 取 NOW()（导入时刻）；这里按核查时刻回填，保证审计时间线从属于业务事件')
    A("UPDATE audit_log a")
    A("  JOIN clue_feedback f ON f.clue_id = a.record_pk AND f.check_result IN (1,2)")
    A("   SET a.op_time = f.check_time")
    A(" WHERE a.table_name = 'risk_clue' AND a.op_type = 4 AND a.operator_tag <> 'system';")
    A('')
    A('-- 误报定位（%d）：记录哪条特征被核查否定，下一轮据此降权' % len(W['clue_feedback_feature']))
    A(ins('clue_feedback_feature', ['feedback_id', 'feature_id', 'is_wrong'],
          W['clue_feedback_feature'],
          lambda r: [str(r['feedback_id']), q(r['feature_id']), str(r['is_wrong'])]))
    A('-- 评估标签（%d）：观察段埋案，研判过程不读取' % len(W['eval_label']))
    A(ins('eval_label', ['object_type', 'object_id', 'sample_type', 'label', 'case_cnt'],
          W['eval_label'],
          lambda r: [str(r['object_type']), q(r['object_id']), str(r['sample_type']),
                     str(r['label']), str(r['case_cnt'])]))

    A('')
    A(sep_line('4.6 审计日志'))
    manual = [x for x in W['audit_log'] if not x['auto']]
    A('-- 手工记录 %d 条；线索状态变更由触发器自动写入（见上）' % len(manual))
    A(ins('audit_log', ['user_id', 'operator_tag', 'op_type', 'table_name', 'record_pk',
                        'op_desc', 'op_time'], manual,
          lambda r: [q(r['user_id']) if r['user_id'] else 'NULL', q(r['operator_tag']),
                     str(r['op_type']), q(r['table_name']),
                     q(r['record_pk']) if r['record_pk'] else 'NULL',
                     q(r['op_desc']), q(r['op_time'])]))

    A('')
    A(sep_line('五、验收与演示查询'))
    A('-- 【1】没有任何特征的研判口径指向案件原表  → 0 行')
    A("-- SELECT feature_id FROM feature_def WHERE match_src = 'case_info';")
    A('--')
    A('-- 【2】案例库里没有观察段数据  → 0')
    A("-- SELECT COUNT(*) FROM case_info WHERE occur_time >=")
    A("--   (SELECT CAST(param_value AS DATETIME) FROM param_config WHERE param_key='history_cutoff');")
    A('--')
    A('-- 【3】评估集干扰样本占比 ≥ 30%%  → %.2f' % (len([l for l in W['eval_label'] if l['sample_type'] == 2]) / len(W['eval_label'])))
    A('-- SELECT SUM(sample_type=2)/COUNT(*) FROM eval_label;')
    A('--')
    A('-- 【4】总分与明细可复算  → 两列相等')
    A('-- SELECT s.score_id, s.total_score,')
    A('--        (SELECT ROUND(SUM(x.weight),2) FROM risk_score_feature x')
    A('--          WHERE x.score_id=s.score_id AND x.is_hit=1) AS 明细加权和')
    A('-- FROM risk_score s;')
    A('--')
    A('-- 【5】混淆矩阵  → TP=%d FP=%d FN=%d TN=%d' % (tp, fp, fn, tn))
    A('-- SELECT SUM(l.label=1 AND IFNULL(s.is_clue,0)=1) AS TP,')
    A('--        SUM(l.label=0 AND IFNULL(s.is_clue,0)=1) AS FP,')
    A('--        SUM(l.label=1 AND IFNULL(s.is_clue,0)=0) AS FN,')
    A('--        SUM(l.label=0 AND IFNULL(s.is_clue,0)=0) AS TN')
    A('-- FROM eval_label l LEFT JOIN risk_score s')
    A('--   ON s.object_type=l.object_type AND s.object_id=l.object_id;')
    A('--')
    A('-- 【6】闭环：误报否定了哪条特征（下一轮据此降权）')
    A('-- SELECT f.feature_id, f.feature_name, COUNT(*) AS 被否定次数')
    A('-- FROM clue_feedback_feature cff JOIN feature_def f USING(feature_id)')
    A('-- WHERE cff.is_wrong = 1 GROUP BY f.feature_id, f.feature_name;')
    A('')
    return '\n'.join(L)


def sep_line(title):
    return ('-- =============================================================================\n'
            '--  ' + title + '\n'
            '-- =============================================================================')


def ins(table, cols, rows, render, chunk=40):
    out = ['INSERT INTO %s (%s) VALUES' % (table, ', '.join(cols))]
    groups = list(chunks(rows, chunk))
    for gi, g in enumerate(groups):
        vals = ',\n'.join('(' + ', '.join(render(r)) + ')' for r in g)
        out.append(vals + (';' if gi == len(groups) - 1 else ','))
    return '\n'.join(out)

# =============================================================================
# 16. 落盘：前端模拟库种子
# =============================================================================

def emit_js():
    L = []
    A = L.append
    A('// 模拟数据：与 sql/risk_alert_示例库.sql 逐行同源（%d 张表 / %d 行），由' %
      (len(W), sum(len(v) for v in W.values())))
    A('// tools/gen_demo_data.py 生成。生成列（object_id、p1/p0/lift、occur_hour）不在这里存，')
    A('// 由 server.js 按库里的同一公式计算；触发器产生的状态变化与审计记录直接写成执行后的结果。')
    A('// 姓名、手机号散列、车牌不进入前端模拟库（脱敏习惯：页面只需要编号与区域）。')
    A('')
    A('export function createSeed() {')
    A('  return {')

    def arr(name, rows, render, indent='    '):
        A(indent + name + ': [')
        for r in rows:
            A(indent + '  ' + render(r) + ',')
        A(indent + '],')

    def objs(name, rows):
        A('    ' + name + ': [')
        for r in rows:
            parts = []
            for k, v in r.items():
                if k.startswith('_'):
                    continue
                parts.append('%s: %s' % (k, jsval(v)))
            A('      { ' + ', '.join(parts) + ' },')
        A('    ],')

    objs('sys_role', W['sys_role'])
    A('    // 演示口令统一为 123456；password_hash/salt 只留在数据库，接口不返回')
    def u(r):
        return "{ user_id: '%s', username: '%s', real_name: '%s', status: %d }" % (
            r['user_id'], r['username'], r['real_name'], r['status'])
    arr('sys_user', W['sys_user'], u)
    def ur(r):
        return "['%s', '%s']" % (r['user_id'], r['role_id'])
    A('    sys_user_role: [')
    for r in W['sys_user_role']:
        A("      ['%s', '%s']," % (r['user_id'], r['role_id']))
    A('    ].map(([user_id, role_id]) => ({ user_id, role_id })),')

    def p(r):
        return "[%s, %s, %d, %s]" % (jsstr(r['param_key']), jsstr(r['param_value']),
                                     r['param_type'], jsstr(r['param_desc']))
    A('    param_config: [')
    for r in W['param_config']:
        A('      %s,' % p(r))
    A('    ].map(([param_key, param_value, param_type, param_desc], i) =>')
    A('      ({ param_id: i + 1, param_key, param_value, param_type, param_desc,'
      ' updated_at: \'2026-10-26 10:00:00\' })),')

    A('    area_info: [')
    for r in W['area_info']:
        A("      ['%s', '%s', %d, %s, %s, %s]," % (r['area_id'], r['area_name'], r['area_type'],
                                           jsstr(r['parent_area_id']), r['lng'], r['lat']))
    A('    ].map(([area_id, area_name, area_type, parent_area_id, lng, lat]) =>')
    A('      ({ area_id, area_name, area_type, parent_area_id, lng, lat })),')

    A('    place_info: [')
    for r in W['place_info']:
        A("      ['%s', '%s', %d, '%s']," % (r['place_id'], r['place_name'],
                                             r['place_type'], r['area_id']))
    A('    ].map(([place_id, place_name, place_type, area_id]) =>')
    A('      ({ place_id, place_name, place_type, area_id })),')

    A('    // 人员只保留研判需要的字段；姓名、手机号散列不进前端模拟库')
    A('    person_info: [')
    for r in W['person_info']:
        A("      ['%s', %s, %d]," % (r['person_id'], jsstr(r['home_area_id']), r['person_type']))
    A('    ].map(([person_id, home_area_id, person_type]) => ({ person_id, home_area_id, person_type })),')

    A('    // 车牌明文不进前端，只留车辆编号、车主与类型')
    A('    vehicle_owner: [')
    for r in W['vehicle_owner']:
        A("      ['%s', '%s', %d]," % (r['vehicle_id'], r['owner_person_id'], r['vehicle_type']))
    A('    ].map(([vehicle_id, owner_person_id, vehicle_type]) =>')
    A('      ({ vehicle_id, owner_person_id, vehicle_type })),')

    A('    case_info: [')
    for r in W['case_info']:
        A("      ['%s', '%s', '%s', '%s', '%s', %s, %d, %d, %.1f, %.2f, %d]," % (
            r['case_id'], r['occur_time'], r['area_id'], r['place_id'], r['person_id'],
            jsstr(r['vehicle_id']), r['driver_confirmed'], r['case_type'],
            r['alcohol_value'], r['distance_home'], r['dispose_status']))
    A('    ].map(([case_id, occur_time, area_id, place_id, person_id, vehicle_id, driver_confirmed,')
    A('           case_type, alcohol_value, distance_home, dispose_status]) =>')
    A('      ({ case_id, occur_time, area_id, place_id, person_id, vehicle_id, driver_confirmed,')
    A('         case_type, alcohol_value, distance_home, dispose_status })),')

    A('    control_person: [')
    for r in W['control_person']:
        A("      ['%s', '%s', '%s', %d, %d]," % (r['person_id'], r['area_id'],
                                                 r['sample_date'], r['hour_slot'], r['match_type']))
    A('    ].map(([person_id, area_id, sample_date, hour_slot, match_type]) =>')
    A('      ({ person_id, area_id, sample_date, hour_slot, match_type })),')

    A('    consume_record: [')
    for r in W['consume_record']:
        A("      ['%s', '%s', '%s', '%s', %.2f, %d]," % (r['record_no'], r['person_id'],
                                                        r['place_id'], r['consume_time'],
                                                        r['amount'], r['has_alcohol']))
    A('    ].map(([record_no, person_id, place_id, consume_time, amount, has_alcohol]) =>')
    A('      ({ record_no, person_id, place_id, consume_time, amount, has_alcohol })),')

    A('    taxi_order: [')
    for r in W['taxi_order']:
        A("      ['%s', '%s', %d, '%s', '%s', '%s', %d]," % (
            r['order_no'], r['person_id'], r['order_type'], r['order_time'],
            r['start_area_id'], r['end_area_id'], r['order_status']))
    A('    ].map(([order_no, person_id, order_type, order_time, start_area_id, end_area_id, order_status]) =>')
    A('      ({ order_no, person_id, order_type, order_time, start_area_id, end_area_id, order_status })),')

    A('    vehicle_track: [')
    for r in W['vehicle_track']:
        A("      ['%s', '%s', '%s', '%s', %d]," % (r['record_no'], r['vehicle_id'],
                                                   r['gate_id'], r['pass_time'], r['direction']))
    A('    ].map(([record_no, vehicle_id, gate_id, pass_time, direction]) =>')
    A('      ({ record_no, vehicle_id, gate_id, area_id: gate_id.slice(0, 3), pass_time, direction })),')

    A('    feature_def: [')
    for r in W['feature_def']:
        A("      ['%s', '%s', '%s', %d, %d, %d, %d, '%s', %s, %d," % (
            r['feature_id'], r['feature_code'], r['feature_name'], r['feature_cat'],
            r['direction'], r['object_scope'], r['value_type'], r['match_src'],
            jsstr(r['match_expr']), r['time_window_min']))
        A("        %s]," % jsstr(r['description']))
    A("    ].map(([feature_id, feature_code, feature_name, feature_cat, direction, object_scope,")
    A("      value_type, match_src, match_expr, time_window_min, description]) => ({")
    A("      feature_id, feature_code, feature_name, risk_type: 1, feature_cat, direction, object_scope, value_type,")
    A("      src_table: 'case_info', match_src, match_expr, time_window_min, min_sample: 5, status: 1, description,")
    A("    })),")

    A('    feature_version: [')
    for r in W['feature_version']:
        A("      ['%s', '%s', %d, %d, %d, '%s', '%s', %s]," % (
            r['version_id'], r['version_no'], r['publish_status'], r['based_case_cnt'],
            r['based_ctrl_cnt'], r['calc_at'], r['published_by'], jsstr(r['remark'])))
    A('    ].map(([version_id, version_no, publish_status, based_case_cnt, based_ctrl_cnt, calc_at, published_by, remark]) =>')
    A('      ({ version_id, risk_type: 1, version_no, publish_status, based_case_cnt, based_ctrl_cnt,')
    A('         calc_at, published_by, remark, created_at: calc_at })),')

    A('    feature_weight: [')
    for r in W['feature_weight']:
        A("      ['%s', %d, %d, %d, %d, %.4f]," % (r['feature_id'], r['case_hit'],
                                                   r['case_total'], r['ctrl_hit'],
                                                   r['ctrl_total'], r['weight']))
    A('    ].map(([feature_id, case_hit, case_total, ctrl_hit, ctrl_total, weight]) => ({')
    A("      version_id: 'V20261001_01', feature_id, case_hit, case_total, ctrl_hit, ctrl_total,")
    A("      weight, is_valid: 1, calc_at: '2026-10-01 10:00:00',")
    A('    })),')

    A('    judge_rule: [')
    for r in W['judge_rule']:
        A("      ['%s', '%s', '%s', %d, %d, %d, %.1f, %.1f, %d, %s]," % (
            r['rule_id'], r['rule_name'], r['version_id'], r['judge_object'], r['min_sample'],
            r['min_hit_cnt'], r['low_threshold'], r['high_threshold'], r['counter_block'],
            jsstr(r['remark'])))
    A('    ].map(([rule_id, rule_name, version_id, judge_object, min_sample, min_hit_cnt,')
    A('      low_threshold, high_threshold, counter_block, remark]) => ({')
    A('      rule_id, rule_name, risk_type: 1, version_id, judge_object, min_sample, min_hit_cnt,')
    A('      low_threshold, high_threshold, counter_block, status: 1, remark,')
    A('    })),')

    A('    rule_feature: [')
    for r in W['rule_feature']:
        A("      ['%s', '%s', %d, %d]," % (r['rule_id'], r['feature_id'],
                                           r['is_required'], r['sort_no']))
    A('    ].map(([rule_id, feature_id, is_required, sort_no]) => ({ rule_id, feature_id, is_required, sort_no })),')

    A('    judge_batch: [')
    for r in W['judge_batch']:
        A("      ['%s', '%s', '%s', %d, '%s', '%s', %s, %d, %d, %d, %d, %s, '%s', '%s']," % (
            r['batch_id'], r['rule_id'], r['version_id'], r['judge_object'], r['data_start'],
            r['data_end'], jsstr(r['area_id']), r['run_status'], r['run_no'], r['object_cnt'],
            r['clue_cnt'], jsval(r['duration_ms']), r['operator_id'], r['created_at']))
    A('    ].map(([batch_id, rule_id, version_id, judge_object, data_start, data_end, area_id,')
    A('      run_status, run_no, object_cnt, clue_cnt, duration_ms, operator_id, created_at]) =>')
    A('      ({ batch_id, rule_id, version_id, judge_object, data_start, data_end, area_id,')
    A('         run_status, run_no, object_cnt, clue_cnt, duration_ms, operator_id, created_at })),')

    A('    risk_score: [')
    for r in W['risk_score']:
        A("      [%d, '%s', '%s', %d, %s, %s, %s, %s, %d, %.2f, %d, %d]," % (
            r['score_id'], r['batch_id'], r['rule_id'], r['object_type'],
            jsstr(r['area_id']), jsval(r['day_type']), jsval(r['hour_slot']),
            jsstr(r['person_id']), r['sample_size'], r['total_score'],
            r['risk_level'], r['is_clue']))
    A('    ].map(([score_id, batch_id, rule_id, object_type, area_id, day_type, hour_slot, person_id,')
    A('      sample_size, total_score, risk_level, is_clue]) =>')
    A("      ({ score_id, batch_id, rule_id, version_id: 'V20261001_01', object_type, area_id,")
    A('         day_type, hour_slot, person_id, sample_size, total_score, risk_level, is_clue })),')

    A('    risk_score_feature: [')
    for r in W['risk_score_feature']:
        A("      [%d, '%s', %d, %.4f, %.2f, %d]," % (r['score_id'], r['feature_id'], r['is_hit'],
                                                    r['weight'], r['hit_value'], r['is_missing']))
    A('    ].map(([score_id, feature_id, is_hit, weight, hit_value, is_missing]) =>')
    A('      ({ score_id, feature_id, is_hit, weight, hit_value, is_missing })),')

    A('    // 已确认/已排除的线索，其状态与关闭时间由 trg_feedback_close_clue 在插反馈时写入')
    A('    risk_clue: [')
    for r in W['risk_clue']:
        A("      ['%s', '%s', %d, %d, '%s', '%s', %s]," % (
            r['clue_id'], r['batch_id'], r['score_id'], r['clue_status'], r['assignee_id'],
            r['create_at'], jsstr(r['close_at'])))
    A('    ].map(([clue_id, batch_id, score_id, clue_status, assignee_id, create_at, close_at]) =>')
    A("      ({ clue_id, batch_id, score_id, version_id: 'V20261001_01', clue_status, assignee_id, create_at, close_at })),")

    A('    clue_feedback: [')
    for r in W['clue_feedback']:
        A("      [%d, '%s', %d, %d, %s, '%s', '%s', %d]," % (
            r['feedback_id'], r['clue_id'], r['check_result'], r['check_method'],
            jsstr(r['check_remark']), r['checker_id'], r['check_time'], r['weight_applied']))
    A('    ].map(([feedback_id, clue_id, check_result, check_method, check_remark, checker_id, check_time, weight_applied]) =>')
    A('      ({ feedback_id, clue_id, check_result, check_method, check_remark, checker_id, check_time, weight_applied })),')

    A('    clue_feedback_feature: [')
    for r in W['clue_feedback_feature']:
        A("      { feedback_id: %d, feature_id: '%s', is_wrong: %d }," % (
            r['feedback_id'], r['feature_id'], r['is_wrong']))
    A('    ],')

    A('    eval_label: [')
    for r in W['eval_label']:
        A("      [%d, '%s', %d, %d, %d]," % (r['object_type'], r['object_id'],
                                             r['sample_type'], r['label'], r['case_cnt']))
    A('    ].map(([object_type, object_id, sample_type, label, case_cnt]) =>')
    A('      ({ object_type, object_id, sample_type, label, case_cnt })),')

    A('    audit_log: [')
    for r in W['audit_log']:
        A("      [%s, %d, '%s', %s, %s, '%s']," % (
            jsstr(r['user_id']), r['op_type'], r['table_name'], jsstr(r['record_pk']),
            jsstr(r['op_desc']), r['op_time']))
    A('    ].map(([user_id, op_type, table_name, record_pk, op_desc, op_time], i) =>')
    A("      ({ log_id: i + 1, user_id, operator_tag: user_id, op_type, table_name, record_pk, op_desc, op_time })),")

    A('  }')
    A('}')
    with open(SEED_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')


def jsstr(v):
    if v is None:
        return 'null'
    return "'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'"


def jsval(v):
    if v is None:
        return 'null'
    if isinstance(v, (int, float)):
        return str(v)
    return jsstr(v)

# =============================================================================
# 17. 主流程
# =============================================================================

def main():
    build_static()
    load_fixed_rows()
    build_index()
    build_person_index()

    print('① 造案件与以案生痕迹 ...')
    build_history()
    build_index()
    build_person_index()

    print('② 造对照人群 ...')
    build_controls()
    build_index()
    build_person_index()

    print('③ 统计特征出现率与权重 ...')
    hit1, hit0 = compute_stats()
    weights = compute_weights(hit1, hit0)
    for w in weights:
        print('   %s  h1=%3d/%d  h0=%3d/%d  p1=%.4f p0=%.4f lift=%s  w=%+.4f' % (
            w['feature_id'], w['case_hit'], w['case_total'], w['ctrl_hit'], w['ctrl_total'],
            w['p1'], w['p0'], w['lift'], w['weight']))

    print('④ 造观察段流水 ...')
    build_observation()
    build_index()

    print('⑤ 执行研判 ...')
    batches = build_batches()
    for b in batches:
        put('judge_batch', b)
    scores = run_batches([b for b in batches if b['run_status'] == 2])
    assign_score_ids(scores)
    for s in scores:
        put('risk_score', {k: v for k, v in s.items() if k != 'features'})
        for fr in s['features']:
            put('risk_score_feature', dict(score_id=s['score_id'], **fr))

    print('⑥ 生成线索与核查反馈 ...')
    clues, fbs, cffs = build_clues(scores)
    for c in clues:
        put('risk_clue', c)
    for f in fbs:
        put('clue_feedback', f)
    for c in cffs:
        put('clue_feedback_feature', c)

    print('⑦ 写评估标签与审计日志 ...')
    build_eval_labels(scores)
    build_audit(clues, fbs, batches)

    # ======================= 第二波：追加数据 =======================
    # 从这一步起换用独立随机源，第一批的任何取值都不会被扰动
    global rng
    rng = random.Random(W2_SEED)

    print('⑧ 第二波：补录 2026-07~08 历史案件 ...')
    build_history(W2_HIST_START, W2_HIST_END, N_CASE, [],
                  created='2026-06-20 09:00:00', order_days=59)
    build_index()
    build_person_index()

    print('⑨ 第二波：补造对照人群 ...')
    build_controls([], W2_HIST_START, W2_HIST_END, N_CONTROL,
                   created='2026-06-22 09:00:00')
    build_index()
    build_person_index()

    # 说明：现行权重版本 v1.0 是按首批 100 起案件统计的快照（based_case_cnt=100）。
    # 第二批 100 起属于补录，若要纳入统计需另发版本——发布新版本会归档旧版本，
    # 属于版本管理动作而非数据导入，因此这里不动 feature_weight，保持可复算（重算为幂等）。
    hit1f, hit0f = compute_stats()
    W2_FULL_STATS = {f: (hit1f[f], len(W['case_info']), hit0f[f], len(W['control_person']))
                     for f in ['F001', 'F002', 'F003', 'F004', 'F005', 'F006', 'F008', 'F009']}

    print('⑪ 第二波：造 12 月观察段流水 ...')
    plan2 = wave2_plan()
    build_observation(plan2, avoid=None, inherit_patrons=False, per_area=3,
                      created='2026-11-20 09:00:00',
                      profiles=W2_PROFILES, n_quiet=1)
    build_index()
    build_person_index()

    print('⑫ 第二波：执行研判 ...')
    batches2 = build_batches_wave2(plan2)
    for b in batches2:
        put('judge_batch', b)
    scores2 = run_batches([b for b in batches2 if b['run_status'] == 2])
    assign_score_ids(scores2, preferred={},
                     start=max(x['score_id'] for x in W['risk_score']) + 1)
    for sc in scores2:
        put('risk_score', {k: v for k, v in sc.items() if k != 'features'})
        for fr in sc['features']:
            put('risk_score_feature', dict(score_id=sc['score_id'], **fr))

    print('⑬ 第二波：线索、评估标签与审计 ...')
    clues2, fbs2, cffs2 = build_clues(scores2, preferred_clue={}, fixed_status={})
    for c in clues2:
        put('risk_clue', c)
    for f in fbs2:
        put('clue_feedback', f)
    for c in cffs2:
        put('clue_feedback_feature', c)
    build_eval_labels(scores2)
    build_audit_wave2(clues2, batches2)

    print('   若按全量 %d 起案件 / %d 条对照重算，权重将为：' %
          (len(W['case_info']), len(W['control_person'])))
    for f, (h1, n1, h0, n0) in W2_FULL_STATS.items():
        w = max(-3.0, min(3.0, round(math.log(((h1 + 0.5) / (n1 - h1 + 0.5)) /
                                              ((h0 + 0.5) / (n0 - h0 + 0.5))), 4)))
        cur = next(x['weight'] for x in W['feature_weight']
                   if x['version_id'] == 'V20261001_01' and x['feature_id'] == f)
        print('     %s  全量 w=%+.4f（现行 %+.4f，差 %+.4f）' % (f, w, cur, w - cur))

    print('⑭ 校验 ...')
    tp, fp, fn, tn = verify()
    total = sum(len(v) for v in W.values())
    print('   混淆矩阵 TP=%d FP=%d FN=%d TN=%d' % (tp, fp, fn, tn))
    print('   精确率 %.3f 召回率 %.3f 误报率 %.3f' % (
        tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0,
        fp / (fp + tn) if fp + tn else 0))

    print('⑨ 落盘 ...')
    emit_sql(sql_data_section(tp, fp, fn, tn))
    emit_js()

    print('\n%-22s %6s' % ('表', '行数'))
    for k in ['sys_role', 'sys_user', 'sys_user_role', 'param_config', 'area_info',
              'place_info', 'person_info', 'vehicle_owner', 'case_info', 'control_person',
              'consume_record', 'taxi_order', 'vehicle_track', 'feature_def', 'feature_version',
              'feature_weight', 'judge_rule', 'rule_feature', 'judge_batch', 'risk_score',
              'risk_score_feature', 'risk_clue', 'clue_feedback', 'clue_feedback_feature',
              'eval_label', 'audit_log']:
        print('%-22s %6d' % (k, len(W[k])))
    print('%-22s %6d' % ('合计', total))


if __name__ == '__main__':
    main()
