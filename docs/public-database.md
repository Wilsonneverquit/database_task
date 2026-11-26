# 公开数据采集、迁移与双库运行手册

项目有两个独立的 MySQL 服务。网页、Flask 路由和权限规则共用一套代码。课程里的完整风险案例使用模拟库；公开库适合演示真实数据采集、时间标准化、主外键关联、统计粒度和缺失数据处理。

## 本次交付与来源

2026-11-26 采集，时间以 [manifest.json](../data/public/manifest.json) 中每个文件的 UTC 时间为准。清洗包与清单随项目交付，可以离线重放。清单保留下载 URL（包括聚合查询）、字节数、原始 SHA-256、许可、剔除数量和清洗包 SHA-256。公开库的数据质量报告保存安装时的清单，后续重新下载不会改动库内留档。

| 数据类别 | 发布者、渠道和许可 | 本次字段映射、粒度和范围 |
| --- | --- | --- |
| 剑桥餐饮场所 | 英国 Food Standards Agency 与 Cambridge City；地方主管机构 FHRS XML，Open Government Licence。Contains public sector information licensed under the Open Government Licence. [下载目录](https://ratings.food.gov.uk/open-data) · [发布方条款](https://ratings.food.gov.uk/terms-and-conditions) | 从 1,464 条名录中取来源类型 1（餐厅/咖啡厅/食堂）与 7843（酒馆/酒吧/夜店），映射为课程类型 1、3。要求有效坐标、可明确解析的街道和符合字段长度的名称地址。保留 302 家餐饮场所、17 家酒馆类场所。FHRSID 加 FH 前缀写入 place_id，同名不同编号保留。未使用卫生评分、徽标。 |
| 剑桥街道区域 | 从上述同一 FHRS 快照派生，沿用相同署名和许可 | 规范门牌地址中的街名后分组，得到 82 条城市道路。用街名散列生成稳定区域键，冲突时中止。中心坐标为入样场所坐标均值，保留六位小数。这是课程定义的街道分组，不是行政边界。 |
| 奥斯汀网约车和匿名乘客 | RideAustin 原始记录，Zuniga-Garcia 等发布于 Mendeley Data，版本 1，DOI 10.17632/wp5gkjbvb9.1，CC0 1.0。[数据与许可](https://data.mendeley.com/datasets/wp5gkjbvb9/1) | 读取 Rides_DataA.csv 固定前 1 MiB 的完整行。按上下车坐标筛入奥斯汀样本范围，排除 9 条范围外、1 条时间或必填项异常的记录。5,008 条完整输入产生 4,998 个完成订单和 2,588 个不同乘客编号。这是文件顺序样本，无全量或随机代表性。 |
| 奥斯汀酒水销售申报 | Texas Comptroller of Public Accounts，Mixed Beverage Sales Receipts，数据目录标注 Public Domain。[发布页与授权](https://data.texas.gov/dataset/Mixed-Beverage-Sales-Receipts/g5bj-yb6k) | 使用经营地 AUSTIN/TX 筛选 2016 年 6–9 月，按申报期结束日计数并汇总 total_sales_receipts。保留 4 个月份、原始金额单位美元和申报数，存于 data_quality_report.report_json.receipt_summary。申报数按源行计数。月度销售额不能拆为具体顾客或商户的一笔消费。 |

**订单字段。** RIDE_ID → order_no，rider_id → person_id，二者均加 RA 前缀；同一订单号只允许一条，一人可有多单。person_name 使用“匿名乘客 + 编号”作为显示标签。created_date → order_time，completed_on → completed_at，updated_date → recorded_at（来源系统最后更新时间，采集时间另记）。检查下单 ≤ 上车 ≤ 完成 ≤ 更新，将带偏移量的时间统一为 UTC+8 后写入 DATETIME。本批从 2016-06-04 22:52:35 至 2016-07-03 13:05:19。截去的 CSV 尾部残行不参与计算。源坐标只用于范围筛选，清洗包不含逐客上下车坐标。

**关联边界。** 可验证的关联有“匿名乘客 → 完成订单”和“剑桥街道 → 登记场所”。英国场所和美国行程属于独立样本，订单的两个区域外键保留 NULL。登记为酒馆不代表某人到过或饮酒。源数据没有可验证的个人含酒消费、车主、逐车卡口、驾驶人确认、实测血液酒精浓度或核查结论，因此对应事实表和评估标签为空，未导入模拟评分、案件、线索或快照。没有全量覆盖依据时不建立 ingest_window。系统账号、权限、规则和版本是应用配置，时间边界是订单样本窗口；这些均不计入公开观测数量。新增案件须有来源、时间、合法的人员关联和实测数值。

## 安装并核对

在项目根目录执行，要求 Windows PowerShell/PowerShell 7、MySQL 8+、Python 3.10+、Node.js 18+。首次安装项目依赖需要联网，使用已交付快照导入不需要联网。

```powershell
.\start.ps1 -MySQLHome 'D:/MySQL/server'
.\real-instance.ps1 start -MySQLHome 'D:/MySQL/server'
backend/.venv/Scripts/python.exe -m backend.public_store install
backend/.venv/Scripts/python.exe -m backend.public_store verify
```

- 模拟库为 127.0.0.1:3307/risk_alert_demo，数据目录是 .runtime/mysql。公开库为 127.0.0.1:3308/risk_alert_real，目录是 .runtime/mysql-real。两个进程、端口和持久数据目录独立。项目安装后，start.ps1 会同时启动已有的本地实例；stop.ps1 正常关闭项目服务。单独控制公开库使用 real-instance.ps1 start 或 stop。
- install 先检查清洗包 SHA-256 和记录数，再应用仓库内的四份迁移。对照**当前应用运行的演示库**检查在线 DDL，匹配才开始装载。初始化账号、配置、业务数据、来源报告在同一事务中提交，按父表到子表顺序写入，失败回滚。命名锁排除并发装载。同一快照重复安装返回 already_installed；已有人工作业或其他版本的库不会被覆盖。
- 公开库首次安装为六个课程角色账号各自生成随机口令，保存在本机 .runtime/public-logins.json。课堂展示建议用 analyst1（研判与评审只读浏览能力）或 teacher；dataop 用于 CRUD。数据库服务密码位于 .runtime/real-db-password，两类口令用途不同。不要分发 .runtime、账号文件或 MySQL 数据目录。
- 路径 .runtime/public-raw 按 SHA-256 保存本机采集的原始字节。固定清洗快照在 data/public，原始网址、版本和转换实现见 [采集程序](../backend/collect_public.py)。运行 `backend/.venv/Scripts/python.exe -m backend.collect_public` 可从源站重新采集；动态名录可能更新。该命令会更新工作区 manifest.json，并按新哈希另存清洗包，不改数据库。保留旧清单再刷新，审核差异后在新的暂存 MySQL 服务安装。验证通过后切换 REAL_DB_HOST/REAL_DB_PORT。回退时改回旧服务即可。
- 自备 MySQL 服务可直接设置 REAL_DB_HOST、REAL_DB_PORT、REAL_DB_USER、REAL_DB_PASSWORD，跳过本地 real-instance.ps1；目标 schema 固定为 risk_alert_real。迁移用户需要创建数据库、表、视图、约束、触发器和例程以及读取定义的权限。应用运行账号可另配，须有现有 API 需要的读写和例程执行权限。使用普通应用账户时注意例程及视图的 DEFINER 必须仍有效。

## 结构、类型与约束

两实例现场校验为 **35 张基表、3 个视图、3 个触发器、2 个存储过程**。每库 116 个表级索引（含主键）、59 个外键和 85 个 CHECK。校验获取每一对象的 SHOW CREATE，覆盖字段顺序、数据类型、精度、默认值、可空性、生成表达式、字符集、主键、索引列顺序、外键引用与约束、视图及例程定义。比较忽略库名前缀和自增计数器当前值。结构保留旧 DDL 中描述演示数据的字段注释；实际数据来源以库内来源报告为准。

| 表组 | 业务用途 |
| --- | --- |
| area_info、place_info、person_info、vehicle_owner | 场所通过 area_id 关联道路，车辆通过 owner_person_id 关联人员。经纬度为 DECIMAL(10,6)，人员编号最长 16 字符。 |
| consume_record、taxi_order、vehicle_track、driver_evidence、ingest_window | 原始事件、独立驾驶观察与采集覆盖。事件业务号唯一，金额为 DECIMAL，时间为 DATETIME；完成订单必须有完成时间，源更新时间不得早于完成时间。 |
| case_info、control_person、eval_label | 历史案件、对照样本、独立评估标签。案件需人员外键及大于零的酒精实测值。 |
| feature_def、feature_version、feature_weight、judge_rule、rule_feature、version_feedback | 指标、版本、权重、规则及反馈。模拟库的统计结果不拷入公开库。 |
| judge_batch、risk_score、risk_score_feature、risk_clue、clue_chain、chain_node、chain_edge、clue_feedback、clue_feedback_feature | 研判、评分构成、证据快照及人工核查。可空分数与数值 0 含义不同。 |
| sys_role、sys_user、sys_user_role、app_session、audit_log、param_config、data_quality_report、schema_migration | 登录、权限、审计、来源、配置和迁移账本。 |

逐字段及索引的权威定义见 [基础 DDL](../sql/migrations/001_existing_schema.sql)、[动态评分与时间窗口](../sql/migrations/002_dynamic_risk.sql)、[来源与反馈](../sql/migrations/003_quality_and_feedback.sql)、[事件完整性约束](../sql/migrations/004_event_integrity.sql)。迁移程序校验已有迁移文件的摘要，功能变更应新增编号迁移并在两边运行及比对。

## 切换与接口调用

浏览器打开 [公开库登录](http://127.0.0.1:5000/login?source=real) 或 [模拟库登录](http://127.0.0.1:5000/login?source=demo)。登录页也有切换链接。所选数据源在本标签页刷新、前端跳转后保留。账号缓存和令牌按库隔离。打开“数据管理 → 数据来源与清洗记录”可查看采集时间和授权；选择“出行订单”可查看实际流水。完整研判演示使用模拟库。

Flask 在鉴权前选择数据源，每个请求使用选中库的一条连接，事务、查询、写入和审计都留在该库。HTTP 可选头为 `X-Data-Source: demo|real`，未指定头时使用后端 DATA_SOURCE（默认 demo）。响应头回显所选库。无效标识返回 400，令牌用于另一库返回 401，数据库不可用返回连接错误。配置 backend/.env 后需重启 Flask。浏览器选择优先级为有效的 URL 参数、标签页已选值、构建时 VITE_DATA_SOURCE、Flask 提供的默认值、demo。在 Vite 开发服务器上可以在 frontend/.env.local 配置 `VITE_DATA_SOURCE=real`，重启 Vite；已构建的页面使用 URL 切换无需重新构建。数据库密码不放入 VITE 变量。

```powershell
$apiRoot = 'http://127.0.0.1:5000/api'
$publicLogin = Get-Content -Raw .runtime/public-logins.json | ConvertFrom-Json
$headers = @{'X-Data-Source'='real'}
$body = @{username='analyst1';password=$publicLogin.analyst1} | ConvertTo-Json
$login = Invoke-RestMethod "$apiRoot/login" -Method Post -ContentType application/json -Headers $headers -Body $body
$headers.Authorization = 'Bearer ' + $login.data.token
$orders = Invoke-RestMethod "$apiRoot/data/orders?page=1&size=5" -Headers $headers
$orders.data.list | Select-Object order_no,person_id,order_time,completed_at
$id = $orders.data.list[0].person_id
Invoke-RestMethod "$apiRoot/persons/$id/timeline" -Headers $headers
```

接口前缀为 /api。成功返回 `{code:0,message:"ok",data:...}`，错误返回相同外层字段和相应 HTTP 状态。分页结构为 `{list,total,page,size}`，page 从 1 起，size 上限 200。SQL 数值返回 JSON number，日期时间为 UTC+8 字符串，SQL NULL 返回 JSON null。集合无记录返回空数组；单条资源不存在返回 404。写接口需要对应角色，冲突返回 409，无权限返回 403。CSV 导入用 multipart/form-data 的 file 字段，UTF-8 编码，单次最多 10,000 行。

| 接口组 | 现有调用 |
| --- | --- |
| 认证 | POST /login 或 /auth/sessions，DELETE /auth/sessions/current |
| 工作台与风险 | GET /dicts、/overview、/region-risk、/risk-map、/risk-trends、/person-risks、/scores/{id}/features、/persons/{id}/timeline |
| 线索与证据 | GET /clues、/clues/{id}、/clues/{id}/chain、/evidence/subjects、/evidence/events；PATCH /clues/{id}/status，POST /clues/{id}/feedback |
| 版本与批次 | GET /features、/features/{id}、/versions、/batches；PATCH /features/{id}/status、/versions/{id}/publish；POST /weights/recalc、/batches、/batches/{id}/runs（兼容 /run） |
| 评估与运维 | GET /eval/confusion、/eval/samples、/eval/labels、/cases、/audit、/users、/health、/params、/data-quality；PATCH /params/{key} |
| 数据管理 | GET /data（含资源、字段、类型和可写性），GET/POST /data/{resource}，GET/PATCH/DELETE /data/{resource}/{key}，POST /data/{resource}/imports |

## 验证与故障定位

```powershell
backend/.venv/Scripts/python.exe -m backend.public_store verify
$env:RUN_DUAL_DB='1'
backend/.venv/Scripts/python.exe -m pytest -q -s backend/tests/test_dual_store.py
Push-Location frontend
npm run build
npm run test:sources
Pop-Location
```

双源契约测试比对 Flask 注册表，覆盖 46 个方法/路由组合（含兼容别名与 OPTIONS），并对 80 组响应检查状态、JSON 外层、业务字段及类型。使用相同的隔离事务样例走通创建、修改、CSV 导入、删除、批次、线索、核查、标签评估和鉴权。两个数据库的测试事务在连接关闭时回滚，自增序号允许有空隙。合法空值、不同记录数、来源清单和统计值按各库事实保留。浏览器测试覆盖两个登录入口、刷新后保留选择、真实库空风险地图和模拟工作台。

遇到 503 先检查目标端口与连接配置；401 时用所选库的口令登录。verify 报结构差异时检查报出的具体表、视图或例程，补齐同一编号迁移再安装。公开库订单有数据而风险页没有评分是本次来源覆盖的实际结果。可从数据管理核对订单业务号，并从人员流水查看同一匿名乘客的真实出行时间。
