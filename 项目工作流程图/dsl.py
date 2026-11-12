# -*- coding: utf-8 -*-
"""极简绘图 DSL：同一份场景数据 → SVG（主交付）+ JSON（供 drawio 生成）。
坐标单位统一为 mm，字体以 pt 给药，内部换算成 mm（1pt = 0.3528mm），保证 A2 打印尺寸正确。
"""
import json, math

PT = 0.3528  # mm per pt
CJK = "Microsoft YaHei"
MONO = "Consolas"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def text_w(s, fmm):
    """估算文本宽度（mm）。CJK 按 1.0em，其余按 0.56em，空格 0.32em。"""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if o < 128:
            w += 0.32 if ch == " " else 0.56
        elif 0x2010 <= o <= 0x2BFF or 0xFF00 <= o <= 0xFFEF or o >= 0x3000:
            w += 1.0
        else:
            w += 0.9
    return w * fmm


def lighten(hexcolor, amount=0.9):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * amount)
    g = round(g + (255 - g) * amount)
    b = round(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


class Scene:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.items = []

    # ---------- 图元 ----------
    def rect(self, x, y, w, h, fill="none", stroke="none", sw=0.3, rx=0, dash=None, op=None):
        self.items.append({"t": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill,
                           "stroke": stroke, "sw": sw, "rx": rx, "dash": dash, "op": op})

    def text(self, x, y, s, size=6, fill="#1f2937", weight="normal", anchor="start",
             family=CJK, ls=0, op=None):
        if s == "":
            return
        self.items.append({"t": "text", "x": x, "y": y, "s": s, "size": size, "fill": fill,
                           "weight": weight, "anchor": anchor, "family": family,
                           "ls": ls, "op": op})

    def path(self, pts, stroke="#1f2937", sw=0.4, dash=None, head=None, tail=None,
             fill="none", op=1.0, rough=0):
        self.items.append({"t": "path", "pts": [list(p) for p in pts], "stroke": stroke,
                           "sw": sw, "dash": dash, "head": head, "tail": tail,
                           "fill": fill, "op": op})

    def circle(self, cx, cy, r, fill="none", stroke="none", sw=0.3, op=None):
        self.items.append({"t": "circle", "cx": cx, "cy": cy, "r": r, "fill": fill,
                           "stroke": stroke, "sw": sw, "op": op})

    # ---------- 组合件 ----------
    def pill(self, cx, cy, lines, size=5.2, fill="#ffffff", stroke="#cbd5e1",
             color="#334155", padx=1.6, pady=1.0, weight="normal", mono=False, sw=0.25,
             radius=None, align="center", minw=0):
        fam = MONO if mono else CJK
        fm = size * PT
        w = max([text_w(l, fm) for l in lines] + [0]) + 2 * padx
        w = max(w, minw)
        lh = fm * 1.30
        h = lh * len(lines) + 2 * pady - (lh - fm) * 0.5
        x = cx - w / 2
        y = cy - h / 2
        r = h / 2 if radius is None else radius
        self.rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw, rx=r)
        for i, line in enumerate(lines):
            ty = y + pady + fm * 0.82 + i * lh
            tx = x + w / 2 if align == "center" else x + padx
            self.text(tx, ty, line, size=size, fill=color, weight=weight, anchor=align,
                      family=fam)
        return w, h

    # ---------- 输出 ----------
    def to_svg(self):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}mm" '
               f'height="{self.h}mm" viewBox="0 0 {self.w} {self.h}">',
               f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff"/>']
        for it in self.items:
            out.append(self._svg_item(it))
        out.append("</svg>")
        return "\n".join(out)

    def _svg_item(self, it):
        t = it["t"]
        if t == "rect":
            dash = f' stroke-dasharray="{it["dash"]}"' if it["dash"] else ""
            op = f' opacity="{it["op"]}"' if it.get("op") is not None else ""
            return (f'<rect x="{it["x"]:.2f}" y="{it["y"]:.2f}" width="{it["w"]:.2f}" '
                    f'height="{it["h"]:.2f}" rx="{it["rx"]}" fill="{it["fill"]}" '
                    f'stroke="{it["stroke"]}" stroke-width="{it["sw"]}"{dash}{op}/>')
        if t == "circle":
            op = f' opacity="{it["op"]}"' if it.get("op") is not None else ""
            return (f'<circle cx="{it["cx"]:.2f}" cy="{it["cy"]:.2f}" r="{it["r"]:.2f}" '
                    f'fill="{it["fill"]}" stroke="{it["stroke"]}" stroke-width="{it["sw"]}"{op}/>')
        if t == "text":
            ls = f' letter-spacing="{it["ls"]}"' if it.get("ls") else ""
            op = f' opacity="{it["op"]}"' if it.get("op") is not None else ""
            anchor = {"middle": "middle", "end": "end"}.get(it["anchor"], "start")
            return (f'<text x="{it["x"]:.2f}" y="{it["y"]:.2f}" font-family="{it["family"]}" '
                    f'font-size="{it["size"] * PT:.3f}" fill="{it["fill"]}" '
                    f'font-weight="{it["weight"]}" text-anchor="{anchor}"{ls}{op}>'
                    f'{esc(it["s"])}</text>')
        if t == "path":
            pts = it["pts"]
            d = "M " + " L ".join(f"{p[0]:.2f} {p[1]:.2f}" for p in pts)
            dash = f' stroke-dasharray="{it["dash"]}"' if it["dash"] else ""
            out = (f'<path d="{d}" fill="{it["fill"]}" stroke="{it["stroke"]}" '
                   f'stroke-width="{it["sw"]}" stroke-linecap="round" '
                   f'stroke-linejoin="round"{dash} opacity="{it["op"]}"/>')
            if it["head"]:
                out += self._arrow_head(pts[-1], pts[-2], it["stroke"], it["head"])
            if it["tail"]:
                out += self._arrow_head(pts[0], pts[1], it["stroke"], it["tail"])
            return out
        return ""

    def _arrow_head(self, tip, prev, color, size):
        dx, dy = tip[0] - prev[0], tip[1] - prev[1]
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        px, py = -uy, ux
        back = size * 1.9
        half = size * 0.78
        p1 = (tip[0] - ux * back + px * half, tip[1] - uy * back + py * half)
        p2 = (tip[0] - ux * back - px * half, tip[1] - uy * back - py * half)
        return (f'<path d="M {tip[0]:.2f} {tip[1]:.2f} L {p1[0]:.2f} {p1[1]:.2f} '
                f'L {p2[0]:.2f} {p2[1]:.2f} Z" fill="{color}" stroke="none"/>')

    def save_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"w": self.w, "h": self.h, "items": self.items}, f,
                      ensure_ascii=False, indent=None)
