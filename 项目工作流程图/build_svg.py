# -*- coding: utf-8 -*-
"""项目工作流程图（A2 横向 594×420mm）· v2
本版：标题改为《基于多种风险特征分析的酒驾预警系统》且不要副标题；
      库名 26pt（比表名大，最突出）；卡片第一行中文名、第二行表名、第三行一句话。
数据源：schema.json（sql 脚本抽取）+ 本文件的 T 表注释。
"""
import json, pathlib
from dsl import Scene, PT, CJK, MONO, text_w, lighten

ROOT = pathlib.Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))

W, H = 594, 420

G = {
    "case":    {"name": "案例库", "n": 5, "c": "#2E6DA4", "role": "数据管理员",
                "sub": "已经发生过的事实 · 只存 cutoff 之前", "num": "①"},
    "feature": {"name": "特征库", "n": 5, "c": "#7B5EA7", "role": "特征管理员",
                "sub": "从案例里总结出的经验 · 可配置的规则", "num": "②"},
    "info":    {"name": "信息库", "n": 4, "c": "#1F8A8A", "role": "数据管理员",
                "sub": "每天的流水 · 唯一横跨历史段与观察段", "num": "①"},
    "clue":    {"name": "研判线索库", "n": 7, "c": "#D97706", "role": "研判员 / 核查员",
                "sub": "研判的结果与闭环 · 外加评估的标准答案", "num": "④"},
    "support": {"name": "安全支撑库", "n": 5, "c": "#6B7280", "role": "系统管理员",
                "sub": "", "num": ""},
}
INK, MUT, FAINT = "#1f2937", "#6b7280", "#9ca3af"
CORAL = "#e05252"
ARROW = "#475569"

# 表名 -> (中文名, 示例行数, 一句话)
T = {
 "area_info": ("区域表", "10", "研判的空间单元，全库 8 处引用"),
 "place_info": ("场所表", "10", "消费发生在哪，决定 F002 判定"),
 "person_info": ("人员表", "10", "三库共用的人员主数据"),
 "case_info": ("案件表", "10", "历史案件，特征提炼的唯一来源"),
 "control_person": ("对照人群", "10", "同期同区域没酒驾的人，用来算 P0"),

 "vehicle_owner": ("车辆车主", "10", "“车→人”的那座桥"),
 "consume_record": ("消费流水", "23", "餐饮娱乐消费，“场所饮酒”的输入"),
 "taxi_order": ("出行订单", "12", "网约车/代驾，“有无代驾”的输入"),
 "vehicle_track": ("卡口过车", "26", "车辆过卡口，“自驾离开”的输入"),

 "feature_def": ("特征定义", "8", "特征清单 · 取数口径 · 命中条件"),
 "feature_version": ("特征库版本", "3", "权重不覆盖，只升版，旧版可回滚"),
 "feature_weight": ("特征权重", "8", "P1/P0/提升度/权重，全部可复算"),
 "judge_rule": ("研判规则", "3", "阈值、最小样本、最少命中几条"),
 "rule_feature": ("规则-特征关联", "12", "一条规则由哪几条特征组成"),

 "judge_batch": ("研判批次", "10", "一次研判 = 一个批次，可重跑"),
 "risk_score": ("评分表", "6", "每个对象的得分与等级"),
 "risk_score_feature": ("评分命中明细", "24", "每个对象 × 每条特征一行，修复 1NF"),
 "risk_clue": ("风险线索", "4", "过阈值后的状态机，事实靠 score_id 追溯"),
 "clue_feedback": ("⑤ 核查反馈", "3", "人工核查结论，插入即推进线索状态"),
 "clue_feedback_feature": ("反馈特征明细", "2", "记下哪条特征被核查否定"),
 "eval_label": ("评估标签", "10", "观察段的“标准答案”，评估时才读"),

 "sys_user": ("用户表", "10", "账号，所有“谁做的”指向它"),
 "sys_role": ("角色表", "5", "五类角色的定义"),
 "sys_user_role": ("用户角色", "10", "用户 × 角色的多对多"),
 "audit_log": ("审计日志", "10", "谁 + 何时 + 改了什么"),
 "param_config": ("参数配置", "10", "全库口径参数，含 history_cutoff"),
}

BOX = {
    "case":    dict(x=6,   y=40,  w=162, h=146, keys=["area_info", "place_info", "person_info",
                                                      "case_info", "control_person"]),
    "info":    dict(x=6,   y=190, w=162, h=128, keys=["vehicle_owner", "consume_record",
                                                      "taxi_order", "vehicle_track"]),
    "feature": dict(x=200, y=40,  w=146, h=200, keys=["feature_def", "feature_version", "feature_weight",
                                                      "judge_rule", "rule_feature"]),
    "clue":    dict(x=378, y=40,  w=210, h=278,
                    keys=["judge_batch", "risk_score", "risk_score_feature",
                          "risk_clue", "clue_feedback", "clue_feedback_feature"]),
}

BADGE = {"clue_feedback": "TRG", "risk_clue": "TRG",
         "feature_weight": "PRC", "judge_batch": "PRC"}

HEAD_H = 28.0


def head(sc, box, gkey):
    """库头：库名 26pt 实色块（比表名大），右上角角色，下面一行定位说明。"""
    g = G[gkey]
    x, y, w, c = box["x"], box["y"], box["w"], g["c"]
    sc.rect(x, y, w, box["h"], fill=lighten(c, 0.955), stroke=lighten(c, 0.42), sw=0.6, rx=2.8)
    sc.rect(x, y, 2.6, box["h"], fill=c, rx=0.9)
    title = f'{g["num"]} {g["name"]}' if g["num"] else g["name"]
    fm = 26.0 * PT
    tw = text_w(title, fm) + 9.0
    sc.rect(x + 4.6, y + 3.0, tw, 12.4, fill=c, rx=2.0)
    sc.text(x + 4.6 + tw / 2, y + 12.4, title, size=26.0, fill="#ffffff", weight="bold",
            anchor="middle")
    sc.text(x + 8.0 + tw, y + 12.2, f'· {g["n"]} 张', size=12.0, fill=c, weight="bold")
    sc.text(x + w - 4.4, y + 11.0, g["role"], size=8.0, fill=lighten(c, 0.15), anchor="end")
    sc.text(x + 5.6, y + 21.8, g["sub"], size=8.2, fill=MUT)
    sc.rect(x + 4.4, y + 23.6, w - 8.8, 0.32, fill=lighten(c, 0.55))
    return y + HEAD_H


def fit(name, w_avail, cap):
    per = len(name) * 0.56 * 0.3528
    return max(6.0, min(cap, w_avail / max(per, 0.01)))


PUNCT = "，、；。·：｜"


def wrap(s, size, maxw):
    fm = size * PT
    if text_w(s, fm) <= maxw:
        return [s]
    best = None
    for i in range(1, len(s)):
        a, b = s[:i], s[i:]
        wa, wb = text_w(a, fm), text_w(b, fm)
        if wa > maxw or wb > maxw:
            continue
        score = abs(wa - wb) + (0 if a[-1] in PUNCT else 6.0)
        if best is None or score < best[0]:
            best = (score, [a, b])
    if best:
        return best[1]
    lines, cur = [], ""
    for ch in s:
        if text_w(cur + ch, fm) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def card(sc, tname, x, y, w, h, gkey, compact=False):
    """卡片：中文名（最大）→ 表名（等宽）→ 一句话。"""
    cn, rows, desc = T[tname]
    c = G[gkey]["c"]
    sc.rect(x, y, w, h, fill="#ffffff", stroke=lighten(c, 0.46), sw=0.45, rx=2.0)
    sc.rect(x, y, 2.0, h, fill=c, rx=0.9)

    if compact:   # 支撑库小卡：中文名 / 表名 / 一句话
        sc.text(x + 5.0, y + 8.4, cn, size=10.5, fill=c, weight="bold")
        fs_n = fit(tname, w - 12, 8.4)
        sc.text(x + 5.0, y + 14.4, tname, size=fs_n, fill="#0f172a", weight="bold", family=MONO)
        sc.text(x + 5.0, y + 20.0, desc, size=6.6, fill=MUT)
        sc.text(x + w - 4.0, y + 8.2, f'{rows} 行', size=5.8, fill=FAINT, anchor="end",
                family=MONO)
        return

    pad = 5.2
    inner = w - 2 * pad
    cap_c = {"clue": 20.0, "case": 19.0, "info": 19.0, "feature": 18.0}.get(gkey, 12.0)
    fs_c = cap_c
    while True:
        fs_n = min(fit(tname, inner, 16.0), fs_c * 0.80)
        fs_d = fs_c * 0.47
        dl = wrap(desc, fs_d, inner)[:2]
        line_c = fs_c * PT * 1.30
        line_n = fs_n * PT * 1.30
        line_d = fs_d * PT * 1.62
        total = line_c + 1.8 + line_n + 2.0 + line_d * len(dl)
        if total <= h - 6.0 or fs_c <= 8.0:
            break
        fs_c *= 0.95

    total = line_c + 1.8 + line_n + 2.0 + line_d * len(dl)
    top = y + max(4.0, (h - total) / 2)
    yc = top + line_c * 0.80
    sc.text(x + pad, yc, cn, size=fs_c, fill=c, weight="bold")
    sc.text(x + w - pad, yc - line_c * 0.08, f'{rows} 行', size=fs_d * 0.72, fill=FAINT,
            anchor="end", family=MONO)
    yn = top + line_c + 1.8 + line_n * 0.78
    sc.text(x + pad, yn, tname, size=fs_n, fill="#0f172a", weight="bold", family=MONO)
    yd = yn + line_n * 0.55 + 2.0 + line_d * 0.80
    for i, ln in enumerate(dl):
        sc.text(x + pad, yd + i * line_d, ln, size=fs_d, fill=MUT)

    lab = BADGE.get(tname)
    if lab:
        bw = text_w(lab, 5.6 * PT) + 2.2
        sc.rect(x + w - pad - bw, y + h - 7.2, bw, 4.8, fill="#eef2ff", stroke="#c7d2fe",
                sw=0.26, rx=0.8)
        sc.text(x + w - pad - bw / 2, y + h - 4.0, lab, size=5.6, fill="#3730a3",
                anchor="middle", family=MONO, weight="bold")


def arrow(sc, pts, color=ARROW, sw=0.8, dash=None, head=2.0, op=1.0):
    sc.path(pts, stroke=color, sw=sw, dash=dash, head=head, op=op)


def badge(sc, cx, cy, s, stroke=CORAL, color=CORAL, r=3.0, fs=6.2):
    sc.circle(cx, cy, r, fill="#ffffff", stroke=stroke, sw=0.6)
    sc.text(cx, cy + fs * PT * 0.36, s, size=fs, fill=color, weight="bold", anchor="middle")


def build():
    sc = Scene(W, H)
    sc.rect(2, 2, W - 4, H - 4, fill="none", stroke="#dbe3ec", sw=0.5, rx=3)

    # ── 标题（只有标题，没有副标题）──────────────────────────
    sc.text(8, 19.0, "基于多种风险特征分析的酒驾预警系统", size=26.0, fill="#0b1523",
            weight="bold")

    # ── 容器与表卡 ──────────────────────────────────────────
    for gkey in ("case", "info", "feature", "clue"):
        box = BOX[gkey]
        y0 = head(sc, box, gkey)
        if gkey == "feature":
            y0 = 100.0
        pad = 4.5
        iw = box["w"] - pad - 4.0
        cols = 2
        rows = {"case": 3, "info": 2, "feature": 3, "clue": 4}[gkey]
        ih = box["y"] + box["h"] - y0 - 3.4
        gapx, gapy = 5.5, (6.0 if gkey == "clue" else 4.5)
        cw = (iw - gapx * (cols - 1)) / cols
        ch = (ih - gapy * (rows - 1)) / rows
        keys = box["keys"]
        k = 0
        for r in range(rows):
            if k >= len(keys):
                break
            wide = (len(keys) - k) == 1
            for ci in range(cols):
                if k >= len(keys):
                    break
                x = box["x"] + pad + ci * (cw + gapx)
                w = iw if wide else cw
                card(sc, keys[k], x, y0 + r * (ch + gapy), w, ch, gkey)
                k += 1
                if wide:
                    break

    # 线索库第 4 行：评估标签 + 混淆矩阵
    ey = 68.0 + 3 * (57.15 + 6.0)
    card(sc, "eval_label", 382.5, ey, 202.0, 57.15, "clue")
    my0 = ey + 10.0
    mx0 = 498
    cw2, ch2 = 25, 9.4
    sc.text(mx0 - 7, my0 - 2.6, "评估结果（示例库）", size=6.6, fill="#9a3412", weight="bold")
    for j, hh in enumerate(["预测=1", "预测=0"]):
        sc.text(mx0 + cw2 * (j + 0.5), my0 + 4.8, hh, size=5.8, fill=MUT, anchor="middle")
    for i, (lab, a, b, col) in enumerate([("实际=1", "TP 3", "FN 0", "#e7f3e7"),
                                          ("实际=0", "FP 1", "TN 6", "#fdecec")]):
        yy = my0 + 7.6 + i * ch2
        sc.text(mx0 - 2.8, yy + 5.8, lab, size=5.8, fill=MUT, anchor="end")
        for j, cell in enumerate([a, b]):
            sc.rect(mx0 + cw2 * j, yy, cw2 - 1.4, ch2 - 1.4,
                    fill=col if j == 0 else "#f4f6f9", stroke="#e5e7eb", sw=0.25, rx=0.8)
            sc.text(mx0 + cw2 * (j + 0.5) - 0.7, yy + 5.8, cell, size=6.0, fill="#334155",
                    anchor="middle", weight="bold")
    sc.text(mx0 - 7, my0 + 30.8, "精确率 0.75 · 召回率 1.00 · 误报率 0.14", size=6.0, fill="#9b2c2c")
    sc.text(mx0 - 7, my0 + 35.8, "误报率 = 不属实 / 已核查总数", size=5.6, fill="#b06060")

    # 特征库：视图卡 + 版本发布说明
    c = G["feature"]["c"]
    sc.rect(204.5, 70, 137, 22, fill="#ffffff", stroke=lighten(c, 0.46), sw=0.45, rx=2.0)
    sc.rect(204.5, 70, 2.0, 22, fill="#7c3aed", rx=0.9)
    sc.text(209.0, 77.6, "历史案件视图", size=12.5, fill=c, weight="bold")
    sc.text(209.0, 84.2, "v_case_history", size=10.5, fill="#0f172a", weight="bold", family=MONO)
    sc.text(209.0, 89.8, "时点边界的唯一出口：研判只许读它", size=7.0, fill=MUT)
    sc.text(204.5, 96.6, "③ 版本发布：草稿→发布→归档，current_flag 保证同类型仅一版在用", size=6.6,
            fill=c, weight="bold")

    # 线索库头部右侧
    sc.text(584.6, 60.6, "视图出口：v_region_risk → 页面 B1 ｜ v_clue_list → 页面 C1（研判员只有视图权限）",
            size=6.2, fill=lighten(G["clue"]["c"], 0.25), anchor="end")

    # ── 主流程箭头 ──────────────────────────────────────────
    arrow(sc, [(168, 120), (200, 120)], sw=1.0, head=2.5)
    sc.pill(184, 105.0, ["② 统计提炼", "P1 / P0"], size=7.4, minw=25, pady=1.6)
    arrow(sc, [(168, 284), (200, 284)], sw=1.0, head=2.5)
    sc.pill(184, 270.0, ["① 流水", "历史段+观察段"], size=7.4, minw=30, pady=1.6)
    arrow(sc, [(273, 240), (273, 244)], color="#7c3aed", sw=0.7, dash="1.6 1.0", head=1.7)
    sc.text(281, 242.8, "③ 权重 · 阈值 · 取数口径（只读）", size=7.0, fill="#6d28d9")
    badge(sc, 262, 241.5, "③", stroke="#7c3aed", color="#7c3aed", fs=5.6, r=2.9)
    arrow(sc, [(346, 284), (378, 284)], sw=1.0, head=2.5)
    sc.pill(362, 269.5, ["④ 写入", "batch·score·明细"], size=7.4, minw=32, pady=1.6)
    arrow(sc, [(168, 76), (204.5, 76)], color="#7c3aed", sw=0.65, dash="1.6 1.0", head=1.7)
    sc.text(186, 72.8, "读 case_info", size=6.6, fill="#6d28d9", anchor="middle")
    arrow(sc, [(110, 186), (110, 190)], color="#7c3aed", sw=0.65, dash="1.6 1.0", head=1.7)
    sc.text(115, 188.8, "case_info.vehicle_id → vehicle_owner：车辆主数据在信息库，“车→人”靠 owner_person_id",
            size=6.4, fill="#6d28d9")

    # ── 闭环 A：反馈 → 特征库 ───────────────────────────────
    sc.path([(530, 194.3), (530, 191.3), (370, 191.3), (370, 32.0), (256, 32.0), (256, 40)],
            stroke=CORAL, sw=1.7, head=3.4)
    sc.text(262, 25.6, "↺ 闭环 A：核查否定的特征 → 扣减 case_hit → 重算 p1 / lift → 发布新版本权重 → 下一轮研判",
            size=7.8, fill="#b9382f", weight="bold")
    sc.text(262, 30.2, "出口 clue_feedback_feature.is_wrong；入口 feature_weight：版本不覆盖、只新增，旧版留档可回滚",
            size=6.6, fill="#c4544c")

    # ── 闭环 B：评估 → 时间轴 ───────────────────────────────
    sc.path([(560, 318), (560, 362)], stroke=CORAL, sw=1.7, head=3.4)
    sc.text(514, 336.0, "⑥ 评估回写", size=7.8, fill="#b9382f", weight="bold")
    sc.text(514, 341.8, "观察段并入 case_info", size=6.4, fill="#c4544c")
    sc.text(514, 347.4, "cutoff 右移 → 下一轮", size=6.4, fill="#c4544c")

    # 横切：支撑库向上咬合
    for tx, lab in ((120, "鉴权"), (272, "留痕"), (470, "口径")):
        sc.path([(tx, 322), (tx, 316.4)], stroke="#6b7280", sw=0.55, dash="1.0 0.8", head=1.3)
        sc.text(tx + 2.0, 320.4, lab, size=5.2, fill="#6b7280")

    # ── 研判引擎 ────────────────────────────────────────────
    sc.rect(200, 244, 146, 74, fill="#fff7ed", stroke="#ea8a3c", sw=0.85, rx=3.0)
    sc.rect(200, 244, 2.8, 74, fill="#d97706", rx=0.9)
    sc.text(205.4, 254.0, "研判引擎", size=12.0, fill="#9a3412", weight="bold")
    sc.text(342, 253.4, "④ 执行批次", size=8.2, fill="#c2410c", weight="bold", anchor="end")
    sc.text(205.4, 261.4, "按规则取权重 → 逐对象匹配 → 打分 → 过阈值出线索", size=7.0, fill="#7c2d12")
    sc.text(205.4, 267.6, "读：特征库（权重/阈值/口径）＋ 信息库（流水）", size=7.0, fill="#7c2d12")
    sc.text(205.4, 273.8, "写：batch / score / 明细 / clue", size=7.0, fill="#7c2d12")
    for lab, bx, bw, mono in [("PRC sp_upsert_score", 205.4, 43, True),
                              ("重跑：已核查跳过", 250.4, 42, False),
                              ("UNIQUE 防重复", 294.4, 47, False)]:
        sc.rect(bx, 277.6, bw, 7.0, fill="#ffffff", stroke="#fdba74", sw=0.32, rx=1.5)
        sc.text(bx + bw / 2, 282.6, lab, size=5.6, fill="#9a3412", anchor="middle",
                family=MONO if mono else CJK)
    sc.text(205.4, 292.4, "8 条特征：F001 夜间场所 · F002 含酒水 · F003 无代驾 · F004 自驾驶出",
            size=6.4, fill="#b45309")
    sc.text(205.4, 298.0, "F005 离家远 · F006 有代驾(反例) · F008 历史涉案 · F009 历史醉驾",
            size=6.4, fill="#b45309")
    sc.text(205.4, 304.8, "口径参数 history_cutoff 由 param_config 提供：引擎与案例统计共用一个时点",
            size=6.0, fill="#9a3412")
    sc.text(205.4, 310.2, "可复现：批次记 rule_id + version_id 快照，事后能重算当时的分", size=6.0, fill="#9a3412")
    sc.text(205.4, 315.6, "评估时才 LEFT JOIN eval_label；研判过程绝不读答案", size=6.0, fill="#9a3412")

    # ── 安全支撑库 ──────────────────────────────────────────
    c = G["support"]["c"]
    sc.rect(6, 322, 500, 36, fill=lighten(c, 0.93), stroke=lighten(c, 0.42), sw=0.6,
            rx=2.6, dash="2.8 1.8")
    sc.text(10.6, 335.4, "安全支撑库", size=20.0, fill="#374151", weight="bold")
    sc.text(10.8, 342.6, "5 张 · 横切所有库（鉴权 / 留痕 / 口径）", size=6.6, fill=MUT)
    sc.text(10.8, 348.4, "不反向引用业务数据，业务表只向它取“谁做的”", size=6.4, fill=MUT)
    for i, key in enumerate(["sys_user", "sys_role", "sys_user_role", "audit_log", "param_config"]):
        card(sc, key, 96 + i * 82.0, 326.0, 78, 28.0, "support", compact=True)

    # ── 时间轴 ──────────────────────────────────────────────
    sc.rect(6, 362, 582, 26, fill="#f8fafc", stroke="#e2e8f0", sw=0.4, rx=2.0)
    sc.text(10.8, 368.8, "全库唯一时间轴", size=8.0, fill="#334155", weight="bold")
    sc.text(48.0, 368.6, "history_cutoff 只写一处（param_config），改它 = 滚动一轮；视图 v_case_history 按它过滤",
            size=6.2, fill=MUT)
    sc.rect(10, 372.2, 288, 10.2, fill=lighten("#2E6DA4", 0.7), rx=1.4)
    sc.rect(298, 372.2, 190, 10.2, fill=lighten("#1F8A8A", 0.7), rx=1.4)
    sc.rect(488, 372.2, 94, 10.2, fill=lighten(CORAL, 0.84), rx=1.4)
    sc.text(13.8, 379.2, "历史段 2026-09-01 → 10-31 ｜ 写 case_info / 对照人群 / 流水 ｜ 算 P1、P0",
            size=6.4, fill="#1e3a5f")
    sc.text(301.8, 379.2, "观察段 2026-11-01 → 11-30 ｜ 只写流水 + eval_label", size=6.4, fill="#12504f")
    sc.text(491.8, 379.2, "↺ 滚动到下一轮", size=6.4, fill="#9b2c2c", weight="bold")
    sc.path([(298, 369.6), (298, 385.2)], stroke="#b45309", sw=0.7, dash="1.4 1.0")
    sc.text(294, 370.2, "history_cutoff = 2026-11-01 00:00:00", size=5.9, fill="#b45309",
            anchor="end", weight="bold")

    # ── 页脚：图例 + 三条必守 ───────────────────────────────
    sc.rect(6, 392, 424, 24, fill="#fcfdff", stroke="#e2e8f0", sw=0.4, rx=2.0)
    lx = 10.5
    for gkey in ("case", "feature", "info", "clue", "support"):
        sc.rect(lx, 394.2, 4.4, 4.4, fill=G[gkey]["c"], rx=0.8)
        sc.text(lx + 6.2, 398.2, G[gkey]["name"], size=6.8, fill="#374151")
        lx += 6.2 + text_w(G[gkey]["name"], 6.8 * PT) + 7.0
    lx += 3
    for col, dash, lab, sw in [("#475569", None, "数据写入", 1.0), ("#7c3aed", "1.4 1.0", "只读", 0.65),
                               (CORAL, None, "闭环回流", 1.5), ("#6b7280", "0.9 0.8", "横切", 0.6)]:
        sc.path([(lx, 396.4), (lx + 11, 396.4)], stroke=col, sw=sw, dash=dash, head=1.7)
        sc.text(lx + 12.8, 398.3, lab, size=6.6, fill="#374151")
        lx += 12.8 + text_w(lab, 6.6 * PT) + 6.5

    lx = 10.5
    for lab, desc in [("TRG", "触发器"), ("PRC", "存储过程"), ("VEW", "视图")]:
        sc.rect(lx, 402.6, 9.4, 4.4, fill="#eef2ff", stroke="#c7d2fe", sw=0.28, rx=0.7)
        sc.text(lx + 4.7, 406.0, lab, size=5.0, fill="#3730a3", anchor="middle", family=MONO, weight="bold")
        sc.text(lx + 10.6, 406.0, desc, size=6.2, fill="#374151")
        lx += 10.6 + text_w(desc, 6.2 * PT) + 5.0
    sc.text(lx + 2, 406.0, "｜ 卡片 = 中文名 + 表名 + 一句话；右上角是示例库行数", size=6.2, fill=FAINT)

    sc.text(10.5, 413.2, "读图：案例库出经验 → 特征库存经验 → 信息库被经验扫描 → 线索库存结果 → 评估给答案；"
                         "珊瑚色两条是闭环，灰虚线框是横切层。", size=6.2, fill=MUT)

    sc.rect(436, 392, 152, 24, fill="#fff8f8", stroke="#f3c7c7", sw=0.4, rx=2.0)
    sc.text(440.0, 397.6, "① 信息库 person/area/vehicle 必须能在主数据找到", size=5.6, fill="#7f1d1d")
    sc.text(440.0, 402.8, "② match_src 不得出现 case_info（CHECK 拦截）", size=5.6, fill="#7f1d1d")
    sc.text(440.0, 408.0, "③ 观察段流水 ≥ cutoff、历史案件 < cutoff", size=5.6, fill="#7f1d1d")
    sc.text(440.0, 413.2, "score.total_score = 明细 weight 之和（可复算）", size=5.4, fill="#b06060")
    return sc


if __name__ == "__main__":
    sc = build()
    (ROOT / "项目工作流程图.svg").write_text(sc.to_svg(), encoding="utf-8")
    sc.save_json(ROOT / "scene.json")
    print("ok:", len(sc.items), "items")
