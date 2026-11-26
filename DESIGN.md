---
name: 多风险特征预警系统
description: 深蓝石墨研判工作台，明亮城市地图与可追溯证据。
colors:
  primary: "#4d8fff"
  primary-text: "#94bdff"
  primary-soft: "#1b3151"
  cyan: "#42c6d6"
  page: "#0b1220"
  surface: "#121d2d"
  surface-raised: "#18263a"
  surface-inset: "#0e1828"
  border: "#29394f"
  text: "#e7eef8"
  secondary: "#bdcadd"
  muted: "#9aaac0"
  low: "#a5c5c4"
  low-background: "#203538"
  mid: "#e5bb71"
  mid-background: "#3a3021"
  high: "#f38e88"
  high-background: "#3b252d"
typography:
  headline:
    fontFamily: "Segoe UI Variable Text, Segoe UI, Microsoft YaHei, PingFang SC, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Segoe UI Variable Text, Segoe UI, Microsoft YaHei, PingFang SC, sans-serif"
    fontSize: "16px"
    fontWeight: 500
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, Microsoft YaHei, PingFang SC, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  data:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "40px"
    fontWeight: 500
    lineHeight: 1.15
rounded:
  control: "8px"
  panel: "14px"
spacing:
  tight: "8px"
  compact: "12px"
  standard: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#081322"
    rounded: "{rounded.control}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
---

# Design System: 多风险特征预警系统

## Overview

**Creative North Star: 深蓝石墨研判工作台。**

面向线索核查、风险解释与课程演示，以清晰的数据、时间与来源关系建立科技感。深色外壳统一导航、内容和控件，城市地图保留明亮的地表、建筑、河流与绿化。

视觉依据为 `frontend/src/styles/main.css`、`styles/chart-theme.js` 和当前页面实现。界面以操作、阅读为主，保留原有技术说明、教学示意标识和人工核查边界。

## Colors

基础背景、内容、浮动层采用三层明度。蓝色表达操作与选择，青色用于地图交互强调；低、中、高风险使用独立语义色，并始终配合文字等级。

热力矩阵的低、中风险色块使用深色数字，高风险色块使用白色数字。具体填色由 `chartPalette` 管理，不能直接套用深色面板的文字色。Three.js 城市材质与二维教学底图保留自然配色，只将画布外围环境改为深色。

## Typography

中文正文沿用系统中文字体栈，数字采用 Bahnschrift 与等宽数字特性。Consolas 只用于编号、时间和来源字段。页面标题 28px，窄屏 25px；卡片标题 16px。正文与说明分层，说明段落优先控制在 75ch 以内。

## Layout

全站内容最大宽度 1680px，桌面主区边距 28px / 32px，900px 以下边距 16px。页面区块默认间隔 24px。导航支持文字展开、图标收起和窄屏抽屉。

首页顶部紧凑排列四项指标，主体采用城市态势预览与待核查队列的约 2:1 布局；1000px 以下改为单列、指标改为两列。证据浏览分为对象、事件时间轴和来源详情，1100px 以下折叠来源布局，800px 以下顺序单列。网格只属于证据工作区。地图保留全屏、可收起侧栏、缩放、平移和旋转行为。

## Elevation & Depth

普通面板以色阶和细边框划分。浮动菜单、提示与弹窗使用带向下偏移的柔和阴影。底色只有轻微明暗过渡，地图城市本身依靠现有三维几何和照明表现空间关系。

## Shapes

普通面板圆角 12–14px，控件 8px，状态标签 4px。图标沿用 Element Plus 图标库，维持一致的线条与尺寸。

## Components

- Element Plus 使用官方暗色变量基础，并由项目主题统一覆盖；挂载到 body 的下拉菜单、抽屉、日期面板和消息框同样使用深色。
- 表格表头、悬停、选中和条纹行使用不同色阶，命中与缺失状态保留独立底色。
- 图表轴、图例、缩放条和提示框使用共享主题；风险阈值、评分算法与数据来源不因外观变化而改变。
- 地图标签采用高不透明度深色面板，当前落点优先避让；全屏控制栏沿用同一主题。
- Three.js 地表使用颜色、细节与有效凹凸纹理；标准、精细和流畅三档控制纹理、阴影、像素比与细节。近景几何按需创建，静止或隐藏时减少渲染。
- 地图手动操作暂停镜头跟随并保留播放进度；显式继续跟随。三维线段采用可控宽度，实线表示同事件链关联展示，虚线仅表示时间先后。
- 焦点环、滚动条、选中文字与输入光标使用主题色；保留减少动态效果偏好。

## Do's and Don'ts

- Do：优先展示风险、时间、来源及可执行操作，保留现有技术说明。
- Do：新增页面复用主题变量，同时检查空、加载、错误、禁用及选中状态。
- Don't：把地图改成完整地球仪，或用统一暗色蒙层遮盖明亮城市细节。
- Don't：未经单独批准增加持续流动粒子；保留用户触发的时间顺序跳跃。
- Don't：用霓虹边框、全屏装饰网格或随机动效抢占数据的视觉重心。
