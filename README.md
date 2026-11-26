# 酒驾风险研判课程项目

Flask + PyMySQL + MySQL，Vue 3 + Element Plus + ECharts。默认使用真实后端和 `risk_alert_demo` 演示库，原始 `risk_alert` 与旧 SQL 保留，不在启动时清空。

本版另提供独立的公开数据库 `risk_alert_real`。打开 `/login?source=real` 查看公开订单、场所和采集说明，使用 `/login?source=demo` 体验完整模拟案例。首次安装、真实库登录方式、数据来源和接口测试见[公开数据与双库操作手册](docs/public-database.md)。

## Windows 启动

需要 Python 3.10+、Node.js 18+、MySQL 8+ 程序。项目自带启动脚本会用本机 MySQL 程序启动独立实例（127.0.0.1:3307），数据保存在 `.runtime/mysql`，不注册系统服务。

```powershell
.\start.ps1
# MySQL 未加入 PATH 时：
.\start.ps1 -MySQLHome 'D:/MySQL/server'
```

打开 http://127.0.0.1:5000 。首次启动安装依赖、迁移、生成数据并计算观察期评分，需要数分钟。再次启动保留已有数据。停止本脚本启动的进程：`.\stop.ps1`。

已有 MySQL 连接可复制 `backend/.env.example` 为 `backend/.env` 并设置连接参数；应用只允许迁移 `risk_alert_demo` / `risk_alert_test`。自备数据库时可分别运行：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m backend.manage migrate
backend/.venv/Scripts/python.exe -m backend.manage seed
# 前端开发：frontend 目录 npm ci，然后 npm run dev（5173 代理到 5000）
backend/.venv/Scripts/python.exe -m backend.app
```

## 演示账号

口令均为 `123456`：`analyst1`（研判员兼教师）、`analyst2`（研判员）、`featop`（特征管理员）、`admin`（系统管理员）、`teacher`（只读评审）、`dataop`（数据管理员）。数据是明确标识的合成数据，不含真实个人资料。

## 展示路线

1. `analyst1` 登录：研判工作台查看优先线索和证据时间轴。
2. 打开线索：沿区域背景、消费、关联车辆移动查看来源，再提交核查。
3. 风险详情：查看 0–100 指数的因子贡献和小时趋势；地图按真实日期与小时回放。
4. 人员风险：查看个人事件与关联车辆记录；车主不自动视为驾驶人。
5. 换 `dataop`：维护主数据、流水和 CSV 导入，演示外键拒绝删除及导入回滚。
6. 换 `featop`：重算 3.1 草稿版本，再发布并用该草稿生成的规则创建批次。已发布版本冻结。
7. 评估和审计：按具体对象与小时去重；没有评分的标签显示覆盖缺口，不算正常样本。

## 数据与算法

固定 seed=20261125，数据期 2026-09-26 至 2026-11-24，历史边界 2026-11-01。12 区域、1500 人，约 9.7 万条消费/订单/过车流水。事件先生成，评分由同一个后端引擎计算，禁止补流水凑目标分数。每条线索保存带外键来源的事件快照。

风险指数使用连续因子、历史第 95 百分位基线、90 分钟时间衰减；低/中/高阈值为 40/70。独立驾驶观察与仅车主关联分开；同次行程已完成的代驾/网约车作为反例。指数不是发生概率，所有行为判断需人工核查。

历史命中率和对数优势比保存在原特征权重表，用于课程统计展示；0–100 的归一化因子系数保存在版本化规则配置中，两者不混用。核查否定记录在草稿重算时折减对应系数并重新归一化，通过 `version_feedback` 追溯。

## 校验与重建

```powershell
backend/.venv/Scripts/python.exe -m backend.manage check
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
# 以下命令显式重建演示副本，原库保持不变：
backend/.venv/Scripts/python.exe -m backend.manage reset-demo --confirm-database risk_alert_demo
```

前端目录：`npm run build`、`npm run test:dashboard`；后端启动后 `npm run test:real` 使用本机 Chrome/Edge 验证真实页面，截图在 `.runtime/screenshots`。原始数据审计可运行 `backend/.venv/Scripts/python.exe -m backend.manage audit-original`，生成时的审计结果也保存在演示库供数据管理页查看。

迁移位于 `sql/migrations`，具有版本与校验和；已有课程说明和 `sql/risk_alert_示例库.sql` 属于旧实现参考，其中 6477 行、3/6 阈值、纯浏览器存储等描述不代表当前默认实现。请勿将旧建库脚本直接用于演示库升级。
