# -*- coding: utf-8 -*-
"""scene.json → .drawio（mxGraph XML）。同一份场景数据，保证 SVG 与 drawio 一致。
层级：容器 group 里放卡片 group，卡片 group 里放字段小标签和文字 —— 拖动时整块跟着走。
"""
import json, pathlib
from xml.sax.saxutils import escape
from dsl import text_w

ROOT = pathlib.Path(__file__).resolve().parent
SCENE = json.loads((ROOT / "scene.json").read_text(encoding="utf-8"))
S = 3.7795  # mm → px @96dpi
W, H = SCENE["w"] * S, SCENE["h"] * S

items = SCENE["items"]
for it in items:                       # 圆统一成包围盒
    if it["t"] == "circle":
        it["x"], it["y"] = it["cx"] - it["r"], it["cy"] - it["r"]
        it["w"] = it["h"] = 2 * it["r"]

rects = [it for it in items if it["t"] == "rect"]
circles = [it for it in items if it["t"] == "circle"]
texts = [it for it in items if it["t"] == "text"]
paths = [it for it in items if it["t"] == "path"]

BOX_AREA = 150.0                       # mm²，小于它的视作小装饰（色条、分隔线、chip）
boxes = [r for r in rects if r["w"] * r["h"] >= BOX_AREA and not (r["w"] > W * 0.9 and r["h"] > H * 0.9)]
smalls = [r for r in rects if r["w"] * r["h"] < BOX_AREA]
boxes += circles                       # 徽标圆当成普通块（不装内容）

cells = []
_next = [1]


def nid():
    _next[0] += 1
    return f"c{_next[0]}"


def inside(r, x, y, pad=0.25):
    return (r["x"] - pad <= x <= r["x"] + r["w"] + pad and
            r["y"] - pad <= y <= r["y"] + r["h"] + pad)


def encloses(a, b, pad=0.4):
    return (b["x"] >= a["x"] - pad and b["y"] >= a["y"] - pad and
            b["x"] + b["w"] <= a["x"] + a["w"] + pad and
            b["y"] + b["h"] <= a["y"] + a["h"] + pad)


def area(r):
    return r["w"] * r["h"]


# ---------- 建父子关系 ----------
parent = {}
for b in boxes:
    par = None
    for c in boxes:
        if c is b or not encloses(c, b):
            continue
        if par is None or area(c) < area(par):
            par = c
    parent[id(b)] = par

children = {id(b): [] for b in boxes}
for b in boxes:
    par = parent[id(b)]
    if par is not None:
        children[id(par)].append(b)

gid = {}

# ---------- 递归输出 ----------
def emit_group(b, parid, ox, oy):
    myid = nid()
    gid[id(b)] = myid
    cells.append(
        f'<mxCell id="{myid}" value="" style="group;html=1;" vertex="1" connectable="0" parent="{parid}">'
        f'<mxGeometry x="{(b["x"] - ox) * S:.1f}" y="{(b["y"] - oy) * S:.1f}" '
        f'width="{b["w"] * S:.1f}" height="{b["h"] * S:.1f}" as="geometry"/></mxCell>')
    return myid


def emit_rect_body(b, parent_id, ox, oy):
    style = rect_style(b)
    cid = nid()
    cells.append(
        f'<mxCell id="{cid}" value="" style="{style}" vertex="1" parent="{parent_id}">'
        f'<mxGeometry x="{(b["x"] - ox) * S:.1f}" y="{(b["y"] - oy) * S:.1f}" '
        f'width="{b["w"] * S:.1f}" height="{b["h"] * S:.1f}" as="geometry"/></mxCell>')
    return cid


def rect_style(r):
    shape = "ellipse" if r["t"] == "circle" else "rounded=1"
    st = [shape, "whiteSpace=wrap", "html=1",
          f'fillColor={r["fill"] if r["fill"] != "none" else "none"}',
          f'strokeColor={r["stroke"] if r["stroke"] != "none" else "none"}',
          f'strokeWidth={r["sw"]:.2f}']
    if r.get("rx"):
        st.append(f'arcSize={max(6, min(60, int(r["rx"] / max(r["w"], 0.01) * 100)))}')
    if r.get("dash"):
        st.append("dashed=1")
    return ";".join(st) + ";"


def text_style(t):
    align = {"start": "left", "middle": "center", "center": "center", "end": "right"}[t["anchor"]]
    st = ["text", "html=1", f"align={align}", "verticalAlign=middle", "spacing=0",
          f'fontSize={t["size"]:.2f}', f'fontColor={t["fill"]}',
          f'fontFamily={t["fontFamily"] if t.get("fontFamily") else t["family"]}']
    if t["weight"] == "bold":
        st.append("fontStyle=1")
    if t.get("ls"):
        st.append(f'spacingLeft={t["ls"]:.1f}')
    return ";".join(st) + ";"


def text_box(t):
    w = max(text_w(t["s"], t["size"] * 0.3528) * S, 4)
    h = t["size"] * 1.55 * S
    x = t["x"] * S
    if t["anchor"] == "middle":
        x -= w / 2
    elif t["anchor"] == "end":
        x -= w
    return x, t["y"] * S - h * 0.80, w, h


def owner_of(x, y):
    best = None
    for b in boxes:
        if inside(b, x, y) and (best is None or area(b) < area(best)):
            best = b
    return best


# 先递归建 group 骨架
def walk(b, ox, oy, parid):
    myid = emit_group(b, parid, ox, oy)
    emit_rect_body(b, myid, b["x"], b["y"])
    for ch in children[id(b)]:
        walk(ch, b["x"], b["y"], myid)


roots = [b for b in boxes if parent[id(b)] is None]
for b in roots:
    walk(b, 0, 0, "1")

# 小装饰（色条、分隔线、chip 底）挂到所属 group
for sm in smalls:
    ow = owner_of(sm["x"] + sm["w"] / 2, sm["y"] + sm["h"] / 2)
    if ow is not None and id(ow) in gid:
        emit_rect_body(sm, gid[id(ow)], ow["x"], ow["y"])
    else:
        emit_rect_body(sm, "1", 0, 0)

# 文字
for t in texts:
    x, y, w, h = text_box(t)
    ow = owner_of(t["x"], t["y"])
    if ow is not None and id(ow) in gid:
        cells.append(
            f'<mxCell id="{nid()}" value="{escape(t["s"])}" style="{text_style(t)}" vertex="1" parent="{gid[id(ow)]}">'
            f'<mxGeometry x="{x - ow["x"] * S:.1f}" y="{y - ow["y"] * S:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry"/></mxCell>')
    else:
        cells.append(
            f'<mxCell id="{nid()}" value="{escape(t["s"])}" style="{text_style(t)}" vertex="1" parent="1">'
            f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry"/></mxCell>')

# 连线
for p in paths:
    pts = p["pts"]
    style = ["html=1", "rounded=0", "edgeStyle=none", "endFill=1",
             f'strokeColor={p["stroke"]}', f'strokeWidth={p["sw"]:.2f}',
             "endSize=6", f'opacity={int(p["op"] * 100)}']
    style.append("endArrow=block" if p["head"] else "endArrow=none")
    if p["dash"]:
        style.append("dashed=1")
    way = "".join(f'<mxPoint x="{q[0] * S:.1f}" y="{q[1] * S:.1f}"/>' for q in pts[1:-1])
    arr = f'<Array as="points">{way}</Array>' if way else ""
    cells.append(
        f'<mxCell id="{nid()}" value="" style="{";".join(style)};" edge="1" parent="1">'
        f'<mxGeometry relative="1" as="geometry">'
        f'<mxPoint x="{pts[0][0] * S:.1f}" y="{pts[0][1] * S:.1f}" as="source"/>'
        f'<mxPoint x="{pts[-1][0] * S:.1f}" y="{pts[-1][1] * S:.1f}" as="target"/>'
        f'{arr}</mxGeometry></mxCell>')

xml = (f'<mxfile host="dsh" type="device">'
       f'<diagram id="flow" name="数据流与库表关系">'
       f'<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
       f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W:.0f}" pageHeight="{H:.0f}" math="0" shadow="0">'
       f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
       + "".join(cells) +
       f'</root></mxGraphModel></diagram></mxfile>')

out = ROOT / "项目工作流程图.drawio"
out.write_text(xml, encoding="utf-8")
print("drawio ok", len(cells), "cells", out.stat().st_size // 1024, "KB",
      "| boxes", len(boxes), "smalls", len(smalls), "texts", len(texts), "edges", len(paths))

