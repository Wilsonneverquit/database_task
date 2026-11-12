# -*- coding: utf-8 -*-
"""渲染：SVG → PNG(300dpi) + PDF(矢量, A2) + 预览图。用 PyMuPDF。"""
import pathlib, time
import fitz

ROOT = pathlib.Path(__file__).resolve().parent
SVG = ROOT / "项目工作流程图.svg"
PDF = ROOT / "项目工作流程图.pdf"
PNG = ROOT / "项目工作流程图.png"
PRE = ROOT / "_preview.png"

doc = fitz.open(SVG)
page = doc[0]
print("page pt:", round(page.rect.width, 1), round(page.rect.height, 1),
      "=> mm:", round(page.rect.width / 72 * 25.4, 1), "x", round(page.rect.height / 72 * 25.4, 1))

# 1) PNG 300dpi
pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
pix.save(PNG)
print("png ok", pix.width, "x", pix.height, PNG.stat().st_size // 1024, "KB")

# 2) 预览图
pix = page.get_pixmap(matrix=fitz.Matrix(120 / 72, 120 / 72), alpha=False)
pix.save(PRE)

# 3) PDF：先写临时文件，再替换（旧文件可能被阅读器占用）
pdfsim = fitz.open("pdf", doc.convert_to_pdf())
tmp = ROOT / "_tmp.pdf"
pdfsim.save(tmp, garbage=4, deflate=True)
for i in range(12):
    try:
        tmp.replace(PDF)
        print("pdf ok", PDF.stat().st_size // 1024, "KB", "pages:", pdfsim.page_count,
              "media:", pdfsim[0].rect)
        break
    except PermissionError:
        time.sleep(2)
else:
    print("!! 项目工作流程图.pdf 被其它程序占用（阅读器/预览），新版暂存为 _tmp.pdf；关闭后重跑即可。")
