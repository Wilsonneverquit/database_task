# 库表归属与字段作用说明（explain.md）

> 配套文档：[数据库设计思路方案.md](数据库设计思路方案.md)｜建库脚本：[sql/risk_alert_示例库.sql](sql/risk_alert_示例库.sql)
> 位置：全部表建在**一个库 `risk_alert`** 里，按"五组"管理。其中**案例库、特征库、信息库**是本项目的三库；研判线索库与安全支撑库是为闭环、评估和权限服务的辅助库。
>
> **本版结构**：26 张表 / 45 个外键 / 65 个 CHECK / 3 个触发器 / 2 个存储过程 / 3 个视图。
> 字符集 `utf8mb4`，排序规则 `utf8mb4_0900_as_cs`（编码字段区分大小写，`'A01'` 与 `'a01'` 不是同一个键），引擎 InnoDB。
>
> **本版相对上一版改了什么**（全部是审查提的问题）：
> | # | 问题 | 本版的处理 |
> | --- | --- | --- |
> | 1 | `hit_features` 把多条特征塞进一个字符串，违反 1NF | 拆成 `risk_score_feature` 明细表，一条特征一行 |
> | 2 | `object_id` 把"区域#日期类型#小时"拼成一个字段 | 改成 **STORED 生成列**，不可能与三个来源列不一致 |
> | 3 | 误报回写时定位不到具体特征，闭环断开 | 新增 `clue_feedback_feature`，把被否定的特征记下来 |
> | 4 | 重跑要"删旧写新"，会毁掉已核查线索 | 改成**按对象 upsert，已核查的跳过**，不删任何数据 |
> | 5 | 核查反馈不改线索状态，靠人肉同步 | 触发器 `trg_feedback_close_clue` 自动推进状态并写关闭时间 |
> | 6 | `p1/p0/lift`、`occur_hour` 等派生列靠人维护 | 全部改为 **STORED 生成列** |
> | 7 | `vehicle_track.area_id` 是冗余但没人保证它正确 | `gate_id` 改成"区域-序号"结构，CHECK 强制前缀 = 区域 |
> | 8 | 对象类型与区域字段、线索状态与关闭时间无约束 | 补跨列 CHECK |
> | 9 | 审计 `user_id` 只记 NULL，追不到人 | 新增 `operator_tag`，触发器取会话变量 `@app_user_id` |
> | 10 | 索引缺口、版本唯一性、编码大小写、数值无上界 | 补 3 个索引、唯一键、`_as_cs` 排序规则、上界 CHECK |

---

## 目录

1. [先看全局：四层数据流 + 一条时间轴](#一先看全局四层数据流--一条时间轴)
2. [26 张表归属总表](#二26-张表归属总表)
3. [案例库（5 张）](#三案例库5-张)
4. [特征库（5 张）](#四特征库5-张)
5. [信息库（4 张）](#五信息库4-张)
6. [研判线索库（7 张）](#六研判线索库7-张)
7. [安全支撑库（5 张）](#七安全支撑库5-张)
8. [约束清单：纪律是怎么写进结构的](#八约束清单纪律是怎么写进结构的)
9. [重跑与闭环：两条最容易讲错的地方](#九重跑与闭环两条最容易讲错的地方)
10. [三库靠哪些字段串起来](#十三库靠哪些字段串起来)
11. [最容易混淆的字段](#十一最容易混淆的字段)
12. [明确不做的三件事](#十二明确不做的三件事)
13. [附录：验收 SQL](#附录验收-sql)

---

## 一、先看全局：四层数据流 + 一条时间轴

### 1.1 五组表的分工

| 库 | 一句话定位 | 数据从哪来 | 谁用它 |
| --- | --- | --- | --- |
| **案例库** | 存"已经发生过的事实"，是规律的来源 | 只存 `history_cutoff` 之前的历史案件 + 对照人群，一次性载入 | 特征提炼（算 P1、P0）、历史档案特征 |
| **特征库** | 存"从案例里总结出来的经验"，是可配置的规则 | 由案例库统计得到，人工审核发布 | 研判引擎（取权重、阈值、取数口径） |
| **信息库** | 存"每天产生的日常数据"，是被扫描的输入 | 按日导入，持续增长；历史段与观察段都有 | 研判引擎（做特征匹配） |
| 研判线索库 | 存研判的**结果**：批次、评分、命中明细、线索、反馈，外加评估标签 | 研判过程写入 + 观察段埋案 | 看板、线索核查、效果评估 |
| 安全支撑库 | 存用户、角色、审计、参数 | 系统初始化 | 全系统（权限、留痕、口径） |

一句话记：**案例库出经验 → 特征库存经验 → 信息库被经验扫描 → 线索库存结果 → 评估标签给答案。**

### 1.2 一条时间轴（全库唯一的时点）

```
2026-09-01 ──────── 2026-10-31 │ 2026-11-01 ──────── 2026-11-30
        历史段（写 case_info）    │   观察段（只写信息库 + eval_label）
                                  ↑ history_cutoff
```

| 段 | 写什么 | 不写什么 | 用来干什么 |
| --- | --- | --- | --- |
| 历史段 | `case_info`、`control_person`、信息库流水 | —— | 统计 P1/P0，提炼权重 |
| 观察段 | 信息库流水、`eval_label` | **不写 `case_info`** | 模拟现实世界，研判对象都在这里 |

**边界只写一次**：`param_config.history_cutoff`。`v_case_history` 视图按它过滤，研判用的特征只能读到"边界之前"的案件。

**滚动闭环**：评估完成 → 观察段案件并入 `case_info` → `UPDATE param_config SET param_value='2026-12-01'` → 观察段变成历史段，进入下一轮。系统的"经验"是随时间往前滚的，不是一次性灌进去的。

### 1.3 一张图看清数据流

```
案例库 ──统计──> 特征库 ──权重/阈值/取数口径──┐
                                               ├──> 研判引擎 ──> 研判线索库 ──> 人工核查
信息库（历史段+观察段）──流水──────────────────┘        │
      ▲                                                  │
      └──── 反馈回流：核查结论 → 被否定的特征 → 新版本权重 ──┘

安全支撑库（用户/角色/审计/参数）横切所有库；它不反向引用任何业务数据。
```

---

## 二、26 张表归属总表

| # | 表名 | 所属库 | 中文名 | 这张表干什么 |
| --- | --- | --- | --- | --- |
| 1 | area_info | **案例库** | 区域表 | 定义研判的空间单元，其他表都往它上面挂 |
| 2 | place_info | **案例库** | 场所表 | 定义饭店/KTV/酒吧等消费场所，消费流水往它上面挂 |
| 3 | person_info | **案例库** | 人员表 | 三库共用的人员主数据，全系统靠它把"人"串起来 |
| 4 | case_info | **案例库** | 案件表 | 存历史酒驾案件，特征提炼的唯一事实来源 |
| 5 | control_person | **案例库** | 对照人群表 | 存"同期同区域没酒驾的人"，用来算对照组出现率 P0 |
| 6 | feature_def | **特征库** | 特征定义表 | 定义有哪些风险特征、统计从哪取数、研判从哪取数 |
| 7 | feature_version | **特征库** | 特征库版本表 | 管理权重版本，草稿→发布→归档，同类型只能有一个在用版本 |
| 8 | feature_weight | **特征库** | 特征权重表 | 存命中数与权重；P1/P0/提升度是生成列 |
| 9 | judge_rule | **特征库** | 研判规则表 | 存阈值、最小样本、最小命中数等研判口径 |
| 10 | rule_feature | **特征库** | 规则-特征关联表 | 一条规则由哪几条特征组成（多对多） |
| 11 | vehicle_owner | **信息库** | 车辆车主表 | 车辆主数据，把卡口轨迹和"人"对上 |
| 12 | consume_record | **信息库** | 消费流水表 | 餐饮娱乐消费记录，"场所饮酒"特征的输入 |
| 13 | taxi_order | **信息库** | 出行订单表 | 网约车/代驾订单，"无代驾"和反例特征的输入 |
| 14 | vehicle_track | **信息库** | 卡口过车表 | 车辆通过卡口的记录，"自行驾车离开"特征的输入 |
| 15 | judge_batch | 研判线索库 | 研判批次表 | 一次研判=一个批次，管控状态、可重跑 |
| 16 | risk_score | 研判线索库 | 评分表 | 每个对象的得分与等级，对象标识是生成列 |
| 17 | **risk_score_feature** | 研判线索库 | **评分命中明细表** | **每个对象 × 每条被评估的特征一行，解决 1NF** |
| 18 | risk_clue | 研判线索库 | 风险线索表 | 只存状态机，事实通过 score_id 追溯到评分与明细 |
| 19 | clue_feedback | 研判线索库 | 核查反馈表 | 存人工核查结论，插入即触发线索状态推进 |
| 20 | **clue_feedback_feature** | 研判线索库 | **反馈特征明细表** | **记录哪条特征被核查否定，闭环回写用** |
| 21 | eval_label | 研判线索库 | 评估标签表 | 观察段埋案，只在评估时 join，研判过程绝不读取 |
| 22 | sys_user | 安全支撑库 | 用户表 | 账号，所有"谁做的"都指向它 |
| 23 | sys_role | 安全支撑库 | 角色表 | 五类角色的定义 |
| 24 | sys_user_role | 安全支撑库 | 用户角色表 | 用户和角色的多对多关系 |
| 25 | audit_log | 安全支撑库 | 审计日志表 | 关键操作留痕：谁 + 什么时候 + 改了什么 |
| 26 | param_config | 安全支撑库 | 参数配置表 | 口径参数，含 `history_cutoff` 时间边界 |

> **三库 = 第 1~10 张 + 第 11~14 张**：案例库 5 张、特征库 5 张、信息库 4 张，共 14 张。
> **辅助 12 张**：研判线索库 7 张（结果 4 张 + 明细 2 张 + 评估 1 张）+ 安全支撑库 5 张。
>
> 与开题文档"23 张表"的差额（+3）说明：`risk_score_feature`、`clue_feedback_feature` 是为了修复 1NF 与闭环断点新加的；`eval_label` 是为了评估可信度新加的。表多了 3 张，但每一张都在回答一个原来答不上来的问题。

---

## 三、案例库（5 张）

### 3.1 area_info —— 区域表（约 20 条）

**作用**：定义"区域"这个研判单元。整个系统的研判对象是"某区域 + 某时段"，区域表就是那个"某区域"。人员的家、场所的位置、案件发生地、卡口的位置，最终都归到一个 `area_id` 上。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| area_id | VARCHAR(12) PK | 区域唯一标识。全库的空间主键，被场所、人员、案件、对照、订单、卡口、批次、评分 8 处引用 |
| area_name | VARCHAR(60) | 区域名称，界面与报表上的展示值（虚构） |
| area_type | TINYINT CK 1~4 | 1 城市道路 2 商圈 3 乡镇 4 高速出入口。可分组看"哪类区域风险高" |
| parent_area_id | VARCHAR(12) FK 自关联 | 上级区域，支持"街道 → 片区"逐级汇总 |
| lng | DECIMAL(10,6) CK ±180 | 区域中心点经度（虚构坐标），供前端风险地图定位用 |
| lat | DECIMAL(10,6) CK ±90 | 区域中心点纬度（虚构坐标），供前端风险地图定位用 |
| is_active | TINYINT | 1 启用 0 停用。停用后不再产生新数据，历史外键仍然成立 |
| created_at | DATETIME | 创建时间，追溯"这批数据什么时候进库" |

### 3.2 place_info —— 场所表（约 200 条）

**作用**：定义"在哪消费"。"在饭店/KTV/酒吧消费"这条特征要判断消费发生在哪类场所，靠的就是这张表的 `place_type`。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| place_id | VARCHAR(16) PK | 场所唯一标识。被案件表（案发前场所）、消费流水表引用 |
| place_name | VARCHAR(80) | 场所名称，展示用（虚构） |
| place_type | TINYINT CK 1~4 | 1 饭店 2 KTV 3 酒吧 4 其他。**特征 F002 的判定依据** |
| area_id | VARCHAR(12) FK | 所属区域。消费流水本身不存区域，按区域汇总时从场所反查 |
| address | VARCHAR(200) | 地址，只到路段，供展示；不存门牌号（最小必要） |
| is_active | TINYINT | 1 启用 0 停用。场所关停后不再挂新流水 |

> 索引 `idx_place_area(area_id, place_type)`：区域级特征要按"区域 + 场所类型"聚合。

### 3.3 person_info —— 人员表（约 5000 条）

**作用**：三库共用的**人员主数据**。案件、消费、订单、个人线索全部靠 `person_id` 指向同一个人，这是"三库对得上"的第一块基石。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| person_id | VARCHAR(16) PK | 人员唯一标识（P0001）。**全系统串联"人"的唯一钥匙**，信息库所有 `person_id` 必须来自这里 |
| person_name | VARCHAR(40) | 姓名，虚构或占位，只用于展示 |
| gender | TINYINT CK 0~2 | 0 未知 1 男 2 女。人口学统计用，不参与打分 |
| birth_year | SMALLINT CK 1900~2020 | 出生年份。只存年份就能算年龄段，又不违反最小必要 |
| phone_hash | CHAR(64) UK | 手机号加盐散列，**不存明文**。唯一约束保证一个号只对应一条人员记录 |
| home_area_id | VARCHAR(12) FK | 居住区域。**特征 F005"离家较远"的基准点** |
| person_type | TINYINT CK 1~3 | 1 案件涉事人员 2 对照人员 3 研判对象 |
| created_at | DATETIME | 入库时间 |

> 有意不设：身份证号、住址门牌、真实手机号 —— 合规上没必要，字段上也少一堆。

### 3.4 case_info —— 案件表（约 1000 条）

**作用**：存历史酒驾案件事实，是**特征提炼的唯一事实来源**。所有特征的 P1 都是拿这张表的人和时间去信息库"回看"，看命中了没有。

> **只存历史段**：`occur_time < history_cutoff`。观察段案件不进这里，只进 `eval_label`。**研判阶段任何特征都不得读它**——只能用 `v_case_history`。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| case_id | VARCHAR(20) PK | 案件编号。一条案件 = 一个统计样本 |
| occur_time | DATETIME | 案发时间，精确到分钟。"案发前 N 小时"的取数窗口都以它为基准 |
| **occur_hour** | **TINYINT 生成列** | `HOUR(occur_time)`，STORED。**物理上不可能与 occur_time 不一致**，且可直接建索引 |
| area_id | VARCHAR(12) FK | 案发区域，"区域 + 时段"研判的维度 |
| place_id | VARCHAR(16) FK 可空 | 案发前消费的场所，用于核对"场所消费"特征是否成立 |
| person_id | VARCHAR(16) FK | 涉事人员。从案件找到人，再拿人去找消费、订单、车辆 |
| vehicle_id | VARCHAR(16) FK 可空 | 涉事车辆。**把案件和卡口轨迹连起来的桥** |
| driver_confirmed | TINYINT CK 0/1 | 1 已人工确认"驾驶人 = 车主"；0 只有车辆归属。**用来标注"以车代人"的误差**，研判不读 |
| case_type | TINYINT CK 1~3 | 1 饮酒后驾驶 2 醉酒驾驶 3 酒驾肇事 |
| alcohol_value | DECIMAL(5,1) CK 0<v≤500 | 血液酒精含量 mg/100mL。上界 500 拦住明显不可能的录入 |
| distance_home | DECIMAL(6,2) CK 0~200 | 案发地到住所距离。**只作展示与统计，不再被特征读取**（F005 已换成"跨区域"口径） |
| dispose_status | TINYINT CK 0~3 | 0 待处置 1 已处罚 2 已移送 3 其他 |
| created_at | DATETIME | 入库时间 |

> 为什么 `occur_hour` 用生成列而不是普通冗余列：普通列谁都能写错，写错了没有任何约束拦得住；生成列由数据库算，`UPDATE occur_time` 时自动跟着变。

### 3.5 control_person —— 对照人群表（约 3000 条）

**作用**：存"同期、同区域、**没有**酒驾"的人。算特征出现率时，案例组算 P1，这张表算 P0。**没有对照组，权重就没有意义**——因为"深夜在 KTV 消费"在普通人群里也很常见。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| control_id | BIGINT PK 自增 | 流水主键 |
| person_id | VARCHAR(16) FK | 被选作对照的人员 |
| area_id | VARCHAR(12) FK | 对照时所在区域，保证"同期同区域"可比 |
| sample_date | DATE | 对照日期，与案件日期对应，避免拿冬天比夏天 |
| hour_slot | TINYINT CK 0~23 | 对照时段，保证"同时段"可比 |
| match_type | TINYINT CK 1~3 | 1 同期同区域 2 同期同类 3 随机抽取，说明 P0 的构成 |

> `UNIQUE(person_id, sample_date, hour_slot)`：同人同日同时段只算一次，防止对照组被重复计数把 P0 拉偏。
>
> **一条纪律**：被选进对照的人，必须在信息库里有对应流水。否则他算 F002 时返回的是"无数据"而不是"没命中"，会系统性低估 P0。示例库里 P0007/P0008/P0009 都在历史段留了消费记录，就是为了避开这个坑。

---

## 四、特征库（5 张）

### 4.1 feature_def —— 特征定义表（约 6~25 条）

**作用**：把"经验"变成数据。一条特征回答四个问题：叫什么、**统计时**从哪取数、**研判时**从哪取数、什么情况算命中。

> **双口径是本项目最关键的一处设计。**
> - `src_table` = **训练口径**，统计 P1/P0 时用，可以是 `case_info`；
> - `match_src` = **研判口径**，匹配时必须能从信息库或历史视图算出来；
> - CHECK `ck_feature_match_src` 把白名单钉死：只能是 `consume_record / taxi_order / vehicle_track / person_info / place_info / v_case_history`。**写 `case_info` 直接报 `ERROR 3819`**（已实测）。
>
> 这样"研判不许读答案"从"组员要记得"变成"数据库不允许"。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| feature_id | VARCHAR(16) PK | 特征编号（F001）。被权重表、规则关联表、明细表引用 |
| feature_code | VARCHAR(40) UK | 英文编码（如 NIGHT_VENUE）。程序里用编码引用，改中文名不影响代码 |
| feature_name | VARCHAR(80) | 特征名称，界面、线索理由、答辩材料上的展示值 |
| risk_type | TINYINT | 1 酒驾（预留扩展）。开题文档"可迁移到其他风险场景"的落点 |
| feature_cat | TINYINT CK 1~5 | 1 时空 2 消费 3 出行 4 行为 5 反例 |
| direction | TINYINT CK 1/2 | 1 正向（命中加分）2 反向（命中扣分） |
| object_scope | TINYINT CK 1~3 | 1 只用于区域时段 2 只用于个人 3 两者都适用。规则配置据此筛特征 |
| value_type | TINYINT CK 1~4 | 1 布尔 2 数值阈值 3 枚举 4 频次。区域级特征多为数值阈值型 |
| **src_table** | VARCHAR(64) | **训练口径**：统计 p1/p0 的取数表，统一写 `case_info` |
| **match_src** | VARCHAR(64) CK 白名单 | **研判口径**：匹配取数表；NULL 表示同 src_table |
| match_expr | VARCHAR(500) | 匹配口径的文字说明，写清"什么算命中"。程序按它实现，答辩按它讲 |
| time_window_min | INT | 取数窗口（分钟）。有的看案发前 3 小时，有的看该小时整段 |
| min_sample | INT | 样本量下限。低于这个数只登记不算权重，防止 3 个样本算出 ±3 |
| status | TINYINT CK 0/1 | 1 启用 0 停用。停用不改历史结果，只影响下一轮研判 |
| description | VARCHAR(255) | 一句话口径说明 |

**当前 8 条特征的双口径一览**

| 特征 | 名称 | 对象 | 训练源 | 研判源 | 口径 |
| --- | --- | --- | --- | --- | --- |
| F001 | 夜间酒水场所集中度 | 区域时段 | case_info | consume_record | 该区域该小时含酒水场所数 ≥ 2 |
| F002 | 场所含酒水消费 | 两者 | case_info | consume_record | 窗口内 `has_alcohol = 1` |
| F003 | 无网约车/代驾订单 | 个人 | case_info | taxi_order | 窗口内 NOT EXISTS 已完成订单 |
| F004 | 自行驾车驶出 | 区域时段 | case_info | vehicle_track | 该区域该小时驶出车辆数 ≥ 5 |
| F005 | 离家较远 | 个人 | case_info | person_info | 消费场所区域 ≠ 居住区域 |
| F006 | 有代驾订单（反例） | 个人 | case_info | taxi_order | 存在已完成的 `order_type = 2` |
| F008 | 历史涉案 | 个人 | case_info | v_case_history | 90 天内历史案件数 ≥ 1 |
| F009 | 历史醉驾 | 个人 | case_info | v_case_history | 历史 `alcohol_value ≥ 80` |

> **为什么删掉原来两条**：
> - F007「周末时段」：研判对象本身就是"区域#日期类型#小时"，"是不是周末"是对象定义的一部分，命中恒真，等于给所有对象无条件加分；
> - F010「无任何消费」：与"数据缺失"混在一起，分不清"确实没消费"和"数据没采到"。
>
> **为什么换掉三条口径**：F001/F004 原来是"有没有人深夜活动/有没有车驶出"这种个体布尔，在区域粒度上没有区分度，改成"场所数/驶出车辆数"这种可比较的计数；F005 原来读 `case_info.distance_home`（结果表），改成从 `person_info.home_area_id` 与 `place_info.area_id` 判断跨区域。

### 4.2 feature_version —— 特征库版本表

**作用**：权重会变（核查反馈会修正它），不能直接覆盖。这张表用"版本"管理：改权重就生成新版本，旧版本留着，既能回滚，也能解释"当时那条线索是按哪版算的"。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| version_id | VARCHAR(20) PK | 版本唯一标识（V20261001_01） |
| risk_type | TINYINT | 1 酒驾。与 version_no 一起构成唯一键 |
| version_no | VARCHAR(20) UK(risk_type, version_no) | 给人看的版本号（1.0 / 2.1），同类型内唯一 |
| publish_status | TINYINT CK 0~2 | 0 草稿 1 已发布 2 已归档 |
| **current_flag** | **TINYINT 生成列** | `IF(publish_status=1,1,NULL)` + `UNIQUE(risk_type,current_flag)`。**保证同一风险类型只能有一个已发布版本**（实测插第二个会报 `ERROR 1062`） |
| based_case_cnt | INT | 算这版权重用了多少起案件。数字越大，权重越可信 |
| based_ctrl_cnt | INT | 用了多少条对照样本 |
| calc_at | DATETIME | 权重计算时间。复现实验、写评估报告要对得上 |
| published_by | VARCHAR(20) FK | 谁发布的，责任可追溯 |
| remark | VARCHAR(255) | 本版改了什么 |
| created_at | DATETIME | 创建时间 |

### 4.3 feature_weight —— 特征权重表

**作用**：这张表是整个项目"不拍脑袋定规则"的证据。每条特征的命中数、出现率、提升度、权重都摆在这里，任何人都能用同一份数据复算出同样的权重。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| weight_id | BIGINT PK 自增 | 流水主键 |
| version_id | VARCHAR(20) FK | 属于哪一版权重 |
| feature_id | VARCHAR(16) FK | 是哪一条特征 |
| case_hit | INT CK ≤case_total | 案例组命中这条特征的样本数 |
| case_total | INT | 案例组样本总数（分母） |
| ctrl_hit | INT CK ≤ctrl_total | 对照组命中数 |
| ctrl_total | INT | 对照组样本总数 |
| **p1** | **DECIMAL(6,4) 生成列** | `case_hit / case_total`，STORED。改命中数自动重算，不可能不一致 |
| **p0** | **DECIMAL(6,4) 生成列** | `ctrl_hit / ctrl_total`，STORED |
| **lift** | **DECIMAL(8,4) 生成列** | `p1 / p0`，STORED。答辩讲"这条特征为什么有用"就看它 |
| **weight** | DECIMAL(6,4) CK -3~3 | 对数几率权重，含 +0.5 平滑、截断 ±3。**由 `sp_calc_feature_weight` 写入**，不是手填 |
| is_valid | TINYINT CK 0/1 | 1 参与研判 0 样本不足。为 0 时研判按 0 分处理，不污染总分 |
| calc_at | DATETIME | 计算时间 |

> `UNIQUE(version_id, feature_id)`：同一版本里一条特征只能有一行权重。
>
> **为什么 p1/p0/lift 用生成列而 weight 用存储过程**：前三个是同一行内的纯算术，能用生成列表达；`weight` 带 `+0.5` 平滑与 ±3 截断，公式较长且需要配合 `is_valid` 判断，放进列定义可读性太差，所以保留存储过程。但它的输入（四个命中数）和输出都在同一行，仍然可复算。

### 4.4 judge_rule —— 研判规则表（约 2~8 条）

**作用**：光有特征还不够，得说清"几分算中、几分算高、样本少到什么程度不输出"。改阈值改这里，不改代码。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| rule_id | VARCHAR(16) PK | 规则编号（R001） |
| rule_name | VARCHAR(80) | 规则名称，展示用 |
| risk_type | TINYINT | 1 酒驾。便于同一套规则表装多种风险 |
| version_id | VARCHAR(20) FK | 这条规则绑哪一版权重 |
| judge_object | TINYINT CK 1/2 | 1 判"区域 + 时段" 2 判"个人" |
| min_sample | INT CK ≥0 | 归集样本量下限。样本太少不输出，防小样本误报 |
| min_hit_cnt | INT CK ≥1 | 最少命中几条特征才算数，防"只中一条就报警" |
| low_threshold | DECIMAL(6,2) | 低/中分界，默认 3 |
| high_threshold | DECIMAL(6,2) CK > low | 中/高分界，默认 6 |
| counter_block | TINYINT | 1 反例特征命中时直接不生成线索；0 只扣分不阻断 |
| status | TINYINT CK 0/1 | 1 启用 0 停用 |
| remark | VARCHAR(255) | 规则说明，答辩讲口径用 |
| created_at | DATETIME | 创建时间 |

### 4.5 rule_feature —— 规则-特征关联表

**作用**：一条规则包含多条特征，一条特征也可能被多条规则用，是典型的多对多。没有它，规则和特征接不上，"命中理由"也就无法复算。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| rule_id | VARCHAR(16) PK+FK | 哪条规则 |
| feature_id | VARCHAR(16) PK+FK | 哪条特征 |
| is_required | TINYINT CK 0/1 | 1 强特征：没命中就不出线索；0 一般特征：只参与加分 |
| sort_no | INT | 展示与计算的顺序，保证线索理由按固定次序输出 |

### 4.6 v_case_history —— 历史案件视图（时点边界的唯一出口）

**作用**：把"历史"这件事从纪律变成结构。历史类特征（F008 历史涉案、F009 历史醉驾）只能读这个视图，视图自己把 `history_cutoff` 之后的案件滤掉。

```sql
CREATE VIEW v_case_history AS
SELECT c.case_id, c.occur_time, c.area_id, c.person_id,
       c.case_type, c.alcohol_value, c.driver_confirmed, ...
FROM case_info c
JOIN param_config p ON p.param_key = 'history_cutoff'
WHERE c.occur_time < CAST(p.param_value AS DATETIME);
```

**为什么用视图而不是加字段**：

- 时点边界只写一次。若改成 `as_of_rule` 字段，十条研判 SQL 每条都得记得写 `< :t0`，漏一条就是泄漏；
- 边界改起来只改一行参数，`UPDATE param_config` 即可完成滚动；
- 实测：往 `case_info` 插一条 2026-11-15 的案件，`case_info` 变 11 行，`v_case_history` 仍是 10 行——边界是物理成立的，不是靠人记得。

| 配套参数 | 值 | 作用 |
| --- | --- | --- |
| `param_config.history_cutoff` | `2026-11-01 00:00:00` | 历史段/观察段的分界线，全库唯一的时点来源 |

---

## 五、信息库（4 张）

> 信息库是**唯一横跨两段的数据**：历史段（2026-10 及以前）用于算 P1/P0，观察段（2026-11 起）用于研判打分。两段都只有流水，都没有案件记录。观察段就是现实世界的切片——系统在这里做研判，但不知道答案。

### 5.1 vehicle_owner —— 车辆车主表

**作用**：信息库的车辆主数据。卡口记录只有"某辆车过了卡口"，要落到"某个人"，必须靠这张表把车和人对应起来。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| vehicle_id | VARCHAR(16) PK | 车辆唯一标识（V0001）。被案件表、卡口流水表引用 |
| plate_hash | CHAR(64) UK | 车牌加盐散列，不存明文；唯一约束防止同一车牌建两条 |
| plate_mask | VARCHAR(16) | 脱敏展示值（浙A\*\*\*8） |
| owner_person_id | VARCHAR(16) FK | 车主是谁。**"车 → 人"的桥梁**，没有它卡口记录落不到人身上 |
| vehicle_type | TINYINT CK 1~4 | 1 小型 2 大型 3 摩托 4 其他 |
| is_active | TINYINT | 1 有效 0 注销。注销后历史轨迹仍保留，外键不受影响 |

> ⚠ **这里只表示"车是谁的"，不表示"当时是谁在开"**。所以 F004 只在区域级使用（数车辆），个人级规则 R002 不含 F004；`case_info.driver_confirmed` 用来标注哪些案件的驾驶人经过人工确认。

### 5.2 consume_record —— 消费流水表（约 5 万条）

**作用**：信息库里最基础的一类数据。"案发前在饭店/KTV 喝酒"这个判断，全靠这张表。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| consume_id | BIGINT PK 自增 | 流水主键 |
| record_no | VARCHAR(32) UK | 业务流水号，**导入去重**：同一批 CSV 重复导入不会插两条 |
| person_id | VARCHAR(16) FK | 谁消费的。按人取"窗口内的消费" |
| place_id | VARCHAR(16) FK | 在哪消费。反查场所类型和所属区域 |
| consume_time | DATETIME | 什么时候消费。判断是否落在特征窗口内 |
| amount | DECIMAL(10,2) CK 0~100000 | 消费金额，也做数据质量校验 |
| has_alcohol | TINYINT CK 0/1 | 1 含酒水。**"场所饮酒"特征最直接的一列** |

> 索引 `(person_id, consume_time)`、`(place_id, consume_time)`：前者按人取窗口，后者按场所做区域聚合。

### 5.3 taxi_order —— 出行订单表（约 3 万条）

**作用**：既提供正向证据（打了网约车 = 没自己开），又提供**反例证据**（叫了代驾 = 风险大幅下降）。这张表是误报率能不能降下来的关键。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| order_id | BIGINT PK 自增 | 流水主键 |
| order_no | VARCHAR(32) UK | 订单号，导入去重 |
| person_id | VARCHAR(16) FK | 谁下的单 |
| order_type | TINYINT CK 1/2 | **1 网约车 2 代驾**。代驾是反例特征；网约车是"没自己开车"的证据 |
| order_time | DATETIME | 下单时间，判断是否在窗口内 |
| start_area_id | VARCHAR(12) FK | 从哪个区域出发 |
| end_area_id | VARCHAR(12) FK | 到哪个区域，配合出发地判断"是不是回家了" |
| order_status | TINYINT CK 1~3 | 1 已完成 2 取消 3 进行中。**只有已完成才算命中**，取消单不能用来证明"他没开车" |

### 5.4 vehicle_track —— 卡口过车表（约 10 万条）

**作用**：信息库里数据量最大的一类，也是判"自行驾车离开"的依据。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| track_id | BIGINT PK 自增 | 流水主键 |
| record_no | VARCHAR(32) UK | 抓拍流水号，导入去重 |
| vehicle_id | VARCHAR(16) FK | 哪辆车经过。按车取轨迹 |
| gate_id | VARCHAR(16) | 卡口编号，结构固定为 **`区域编号-序号`**（如 `A02-G01`） |
| area_id | VARCHAR(12) FK | 卡口所属区域。**有意冗余**，区域时段研判直接按它分组，省一次关联 |
| pass_time | DATETIME | 过车时间，判断距案发多久 |
| direction | TINYINT CK 1/2 | 1 驶入区域 2 驶出区域（**相对区域**）。"驶出"才是"自行驾车离开"的依据 |

> **冗余是怎么保证不写错的**：`CHECK (area_id = SUBSTRING_INDEX(gate_id,'-',1))`。写 `gate_id='A02-G09'` 却填 `area_id='A01'` 会直接报 `ERROR 3819`（已实测）。不加这条约束，冗余列就是一颗定时炸弹。
>
> 本方案没有单独的"卡口维表"（那会变成第 27 张表），所以用编号结构承担"卡口 → 区域"的映射。

---

## 六、研判线索库（7 张）

### 6.1 judge_batch —— 研判批次表

**作用**：把"一次研判"当成一个可管理的任务。可重跑、可看状态、可记耗时，也是性能实验取数的地方。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| batch_id | VARCHAR(24) PK | 批次编号（B2026110701）。评分和线索都挂在它下面 |
| rule_id | VARCHAR(16) FK | 这次用哪条规则 |
| version_id | VARCHAR(20) FK | 这次用哪版权重（快照），事后能复现"当时是怎么算的" |
| judge_object | TINYINT CK 1/2 | 1 区域时段 2 个人 |
| data_start / data_end | DATETIME CK end>start | 研判数据窗口。**必须落在观察段** |
| area_id | VARCHAR(12) FK 可空 | 只判某个区域；为空 = 全部区域 |
| run_status | TINYINT CK 0~3 | 0 待执行 1 执行中 2 成功 3 失败。**防止重复启动** |
| run_no | INT | 已执行次数，重跑一次加一 |
| object_cnt | INT CK ≥0 | 本批对象数 |
| clue_cnt | INT CK ≥0 | 本批线索数 |
| duration_ms | INT CK：成功必须非空 | 执行耗时。性能实验（有无索引、现算 vs 预计算）直接取这个数 |
| operator_id | VARCHAR(20) FK | 谁发起的研判 |
| created_at | DATETIME | 创建时间 |

> `CHECK (run_status <> 2 OR duration_ms IS NOT NULL)`：成功的批次必须记了耗时，否则性能实验的数据是空的。

### 6.2 risk_score —— 评分表

**作用**：研判的中间结果。每个对象一条，存它的分、等级和是否出了线索。**线索是从这里筛出来的**，评分本身也留着，便于回答"为什么这条没出线索"。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| score_id | BIGINT PK 自增 | 流水主键，被线索表、明细表引用 |
| batch_id | VARCHAR(24) FK | 属于哪一批 |
| rule_id / version_id | FK | 规则与权重版本快照 |
| object_type | TINYINT CK 1/2 | 1 区域时段 2 个人 |
| area_id | VARCHAR(12) FK 可空 | 区域。个人对象为空 |
| day_type | TINYINT CK 1/2 可空 | 1 工作日 2 周末 |
| hour_slot | TINYINT CK 0~23 可空 | 时段 |
| person_id | VARCHAR(16) FK 可空 | 个人对象的人员编号 |
| **object_id** | **VARCHAR(64) 生成列** | `区域#日期类型#小时` 或 `人员编号`。**STORED 生成列，不可能与上述四列不一致** |
| sample_size | INT | 这个对象归集到多少条记录。太少不可信 |
| total_score | DECIMAL(8,2) | 总分 = 命中特征权重之和（可由明细复算） |
| risk_level | TINYINT CK 1~3 | 1 低 2 中 3 高，看板和线索排序都用它 |
| is_clue | TINYINT CK 0/1 | 1 已生成线索 0 未达标 |
| created_at | DATETIME | 生成时间 |

> **两条跨列 CHECK**（这是原来最大的漏洞）：
> - `ck_score_region_fields`：区域时段对象必须有区域/日期类型/小时，否则这个对象根本无法解释；
> - `ck_score_person_field`：个人对象必须有人。
>
> **`UNIQUE(batch_id, object_type, object_id)`**：全库最重要的约束，配合 upsert 保证重跑不产生重复评分。

### 6.3 risk_score_feature —— 评分命中明细表（关键新增）

**作用**：把"命中了哪几条特征、各占多少分"从字符串拆成结构化的行。**这是修复 1NF 的那一刀**。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| score_id | BIGINT PK+FK | 属于哪条评分 |
| feature_id | VARCHAR(16) PK+FK | 哪条特征 |
| is_hit | TINYINT CK 0/1 | 1 命中 0 未命中 |
| weight | DECIMAL(6,4) CK ±3 | **评分时该特征的权重快照**。权重日后变化，不影响这条历史记录 |
| hit_value | DECIMAL(10,2) | 命中值：布尔型 = 1/0，数值型 = 实际计数（如场所数 2、驶出车辆数 5） |
| is_missing | TINYINT CK 0/1 | 1 数据缺失（既不是命中，也不是干净的未命中） |

**为什么必须拆开**：

| 字符串写法（旧） | 明细表（新） |
| --- | --- |
| `'F001:+1.17;F002:+2.93'` | 两行，各带 feature_id / weight / hit_value |
| 无法外键约束，特征编号写错数据库不知道 | `FK(feature_id)` 直接拦住 |
| 统计"哪个特征最常命中"只能 `LIKE '%F01%'` | `GROUP BY feature_id` 就行 |
| 误报回写时定位不到具体特征 | `clue_feedback_feature` 能精确指向 |
| 分不清"没命中"和"数据缺失" | `is_missing` 一列说清 |

> **注意**：表里记录的是**所有被评估的特征**，包括未命中的。只记命中的话，就无法回答"这条规则评估了 3 条特征还是 6 条特征"。

### 6.4 risk_clue —— 风险线索表

**作用**：真正推给研判员看的东西，是一台**状态机**。线索的分数、理由、特征都通过 `score_id` 追溯到评分与明细，这里不再重复存一份。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| clue_id | VARCHAR(24) PK | 线索编号（CL2026110701），业务上对外的主键 |
| batch_id | VARCHAR(24) FK | 来自哪一批研判 |
| score_id | BIGINT FK **UK** | 来自哪条评分。**1:1**，线索的全部事实都在评分与明细里 |
| version_id | VARCHAR(20) FK | 用的哪版权重，回答"依据的权重从哪来" |
| clue_status | TINYINT CK 0~3 | 0 待核查 1 核查中 2 已确认 3 已排除 |
| assignee_id | VARCHAR(20) FK | 承办人，按人看待办 |
| create_at | DATETIME | 线索生成时间 |
| close_at | DATETIME | 关闭时间。**CHECK 强制：已确认/已排除必须有关闭时间，未关闭的不许有** |

> **为什么把原来的 8 个快照列删了**：旧版 `risk_clue` 里存了 `object_id / area_id / hour_slot / risk_level / total_score / hit_features`，这些全部由 `score_id` 决定，属于传递依赖，两处不一致时没人知道该信哪个。现在只留状态机，展示交给 `v_clue_list` 视图 join。
>
> **那"冻结"怎么办**：冻结不是靠复制一份，而是靠**重跑不覆盖已核查对象**（见 9.1）。评分行不动，线索的事实自然就不动。

### 6.5 clue_feedback —— 核查反馈表

**作用**：闭环的最后一环。人工核查的结论回写到这里，"不属实"的线索成为误报样本，进入下一轮权重修正。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| feedback_id | BIGINT PK 自增 | 流水主键。一条线索可能核查多次（转派、复核），所以不能拿 clue_id 当主键 |
| clue_id | VARCHAR(24) FK | 对应哪条线索 |
| check_result | TINYINT CK 1~3 | 1 属实 2 不属实 3 无法核实。**误报率 = 不属实 / 已核查总数**，全靠这一列 |
| check_method | TINYINT CK 1~3 | 1 电话 2 现场 3 数据复核，说明结论的可信程度 |
| check_remark | VARCHAR(500) | 核查结论的文字说明 |
| checker_id | VARCHAR(20) FK | 谁核的，责任追溯 |
| check_time | DATETIME | 核查时间 |
| weight_applied | TINYINT CK 0/1 | 1 已纳入下一轮权重修正。防止同一条反馈被重复计算两次 |

> **插入即触发**：`trg_feedback_close_clue` 会把对应线索改成已确认(2)/已排除(3)，并写入 `close_at`。示例库里线索的状态不是手填的，而是插反馈时由触发器自动推进的。

### 6.6 clue_feedback_feature —— 反馈特征明细表（关键新增）

**作用**：记录**这次误报到底是哪条特征骗了系统**。没有这张表，"误报回写权重"就是一句空话——你拿什么去调整 P1？

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| feedback_id | BIGINT PK+FK | 哪条反馈 |
| feature_id | VARCHAR(16) PK+FK | 哪条特征 |
| is_wrong | TINYINT CK 0/1 | 1 该特征被核查否定 |

**闭环 SQL**（下一轮据此降权）：

```sql
SELECT f.feature_id, f.feature_name, COUNT(*) AS 被否定次数
FROM clue_feedback_feature cff
JOIN feature_def f ON f.feature_id = cff.feature_id
WHERE cff.is_wrong = 1
GROUP BY f.feature_id, f.feature_name;
```

> 示例库中那条误报（`CL2026110702`）否定了 F001 与 F002——"有酒水消费"这条证据单独不足以判风险。下一轮重算时，这两条特征的 `case_hit` 应当被扣减，权重自然下降。

### 6.7 eval_label —— 评估标签表（观察段的"埋案"）

**作用**：观察段编造的案件不写进 `case_info`，只写在这里，作为评估时的"标准答案"。研判过程绝不读它，`LEFT JOIN` 只发生在最后算指标那一步。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| label_id | BIGINT PK 自增 | 流水主键 |
| object_type | TINYINT CK 1/2 | 1 区域时段 2 个人，与 `risk_score.object_type` 对齐 |
| object_id | VARCHAR(64) UK | 与 `risk_score.object_id` 同格式（`A02#2#23`、`P0002`） |
| sample_type | TINYINT CK 1~3 | **1 正样本 2 干扰样本 3 对照样本**。没有干扰样本，误报率就是假的 |
| label | TINYINT CK 0/1 | 1 该对象确有酒驾 0 无。与 `is_clue` 交叉出 TP/FP/FN/TN |
| case_cnt | INT | 该对象内真实案件数。区域时段对象可能多于 1 起 |
| created_at | DATETIME | 埋案时间 |

> **`UNIQUE(object_type, object_id)`**：一个对象一条标签，评估时才不会重复计数。
>
> **权限隔离**：表放在同一个 `risk_alert` 库里，不另开 schema。研判员角色只 `GRANT` 到 `v_clue_list`、`v_region_risk` 两个视图，**没有任何基表权限**，`eval_label` 自然不可见。
>
> 示例库的结果：TP=3、FP=1、FN=0、TN=6 → 精确率 0.75、召回率 1.00、误报率 1/7 ≈ 0.14。

---

## 七、安全支撑库（5 张）

### 7.1 sys_user —— 用户表

**作用**：所有"谁做的"最终都指向这里：线索承办人、批次操作人、审计操作人、权重发布人。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| user_id | VARCHAR(20) PK | 用户唯一标识（U0001）。被 4 处引用 |
| username | VARCHAR(40) UK | 登录名。**排序规则区分大小写**，`Analyst1` 与 `analyst1` 是两个账号 |
| password_hash | VARCHAR(128) | `SHA2(salt + 明文, 256)`，不存明文 |
| salt | CHAR(16) | 随机盐值，防彩虹表 |
| real_name | VARCHAR(40) | 真实姓名，内部管理用，对外脱敏 |
| status | TINYINT CK 1~3 | 1 正常 2 停用 3 锁定（连续失败达阈值自动锁） |
| created_at | DATETIME | 创建时间 |

### 7.2 sys_role —— 角色表

**作用**：定义五类角色，是权限分配的别名。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| role_id | VARCHAR(16) PK | R_ANALYST，被用户角色表引用 |
| role_name | VARCHAR(40) UK | 研判员 / 数据管理员 / 特征管理员 / 系统管理员 / 教师 |
| role_desc | VARCHAR(200) | 职责说明，写清能看什么、能改什么 |
| status | TINYINT CK 0/1 | 1 启用 0 停用 |

### 7.3 sys_user_role —— 用户角色表

**作用**：用户和角色的多对多关系（一个人可兼多个角色，例如研判员兼教师）。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| user_id | VARCHAR(20) PK+FK | 哪个用户 |
| role_id | VARCHAR(16) PK+FK | 什么角色 |
| granted_at | DATETIME | 授权时间，权限变更可追溯 |

### 7.4 audit_log —— 审计日志表

**作用**：关键写入留痕。线索状态变更、权重调整由触发器自动写入，能回答"**谁**在什么时候把什么改成了什么"。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| log_id | BIGINT PK 自增 | 流水主键 |
| user_id | VARCHAR(20) FK 可空 | 操作人。由会话变量 `@app_user_id` 解析，解析不到为空 |
| **operator_tag** | VARCHAR(40) | **会话操作人标识**。解析不到时记 `'system'`，**保证审计永远有一条可追的线索**，不会只剩 NULL |
| op_type | TINYINT CK 1~8 | 1 登录 2 查询 3 新增 4 修改 5 删除 6 导出 7 研判 8 授权 |
| table_name | VARCHAR(64) | 动了哪张表 |
| record_pk | VARCHAR(64) | 动了哪条记录（存主键值） |
| op_desc | VARCHAR(255) | 人能读的一句话 |
| op_time | DATETIME | 什么时候，**建索引** |

> 索引 `(user_id, op_time)`：按人查操作史，不再全表扫。
>
> **为什么 `audit_log` 不建指向业务表的外键**：一张日志表要背 26 个外键，而且删业务记录会连带删审计——而审计恰恰最不该被业务删除影响。

### 7.5 param_config —— 参数配置表

**作用**：生成脚本和研判程序**读同一份参数**，这是"三库口径一致"的制度保障。改比例、改阈值不用改代码。

| 字段 | 类型 / 键 | 作用 |
| --- | --- | --- |
| param_id | INT PK 自增 | 流水主键 |
| param_key | VARCHAR(60) UK | 参数名（如 `pos_sample_rate`），程序按它取值 |
| param_value | VARCHAR(200) | 参数值。统一按字符串存，按 type 解析 |
| param_type | TINYINT CK 1~4 | 1 整型 2 小数 3 字符串 4 布尔 |
| param_desc | VARCHAR(255) | 含义与取值范围，防止后人改错 |
| updated_at | DATETIME | 最后修改时间，改参数也要能追溯 |

> **`history_cutoff` 就在这张表里**：`v_case_history` 从它读时间边界，全库只有一个时点来源。改一行参数就能滚动时间轴，比改十处 SQL 可靠。

---

## 八、约束清单：纪律是怎么写进结构的

这一节是整份文档的"答辩骨架"：每一个设计缺陷，都对应一条数据库层面的拦截，而不是一句口头约定。

| # | 原来会出的问题 | 结构手段 | 落在哪 |
| --- | --- | --- | --- |
| 1 | 研判偷偷读了结果表（循环论证） | CHECK 白名单 | `ck_feature_match_src` |
| 2 | 把手表/观察段的案件混进案例库 | 视图 + 参数 | `v_case_history` + `history_cutoff` |
| 3 | 命中明细存字符串，违反 1NF | 明细表 | `risk_score_feature` |
| 4 | `object_id` 与来源列不一致 | STORED 生成列 | `risk_score.object_id` |
| 5 | 派生列（p1/p0/lift）与命中数不一致 | STORED 生成列 | `feature_weight.p1/p0/lift` |
| 6 | `occur_hour` 手填写错 | STORED 生成列 | `case_info.occur_hour` |
| 7 | 同一规则集有多个"已发布"版本 | 生成列 + 唯一键 | `uk_version_current` |
| 8 | 卡口区域冗余列写错 | CHECK 结构约束 | `ck_track_area_match` |
| 9 | 区域时段对象缺字段却照常入库 | 跨列 CHECK | `ck_score_region_fields` |
| 10 | 线索已确认却没有关闭时间 | 跨列 CHECK | `ck_clue_close` |
| 11 | 批次成功却没记耗时 | 跨列 CHECK | `ck_batch_duration` |
| 12 | 审计只记 NULL，追不到人 | 触发器 + 会话变量 | `trg_clue_audit.operator_tag` |
| 13 | 反馈不改线索状态，靠人肉同步 | 触发器 | `trg_feedback_close_clue` |
| 14 | 重跑重复评分/线索 | 唯一键 + upsert | `uk_batch_object` + `sp_upsert_score` |
| 15 | 重跑删掉已核查结论 | 过程内跳过逻辑 | `sp_upsert_score` |
| 16 | 编码字段 `A01`/`a01` 被当成同一个 | 排序规则 | `utf8mb4_0900_as_cs` |
| 17 | 酒精值、距离、金额录入明显不可能的数 | 上界 CHECK | `ck_case_alcohol` 等 |

**一个反例演示**（答辩可以直接跑）：

```sql
UPDATE feature_def SET match_src = 'case_info' WHERE feature_id = 'F003';
-- ERROR 3819: Check constraint 'ck_feature_match_src' is violated.
```

---

## 九、重跑与闭环：两条最容易讲错的地方

### 9.1 重跑不是"删旧写新"，是"按对象 upsert，已核查的跳过"

**旧做法的问题**：`DELETE FROM risk_score WHERE batch_id=...` 再重插。看起来干净，但会连带删掉已核查线索和它的核查结论——而核查结论是整个系统最有价值的数据，是权重迭代的输入。而且实测下来，外键是 `NO ACTION`，这条 DELETE 根本执行不了。

**现在的做法**：`sp_upsert_score`

```
1. 先查这个对象是否已有线索，且状态是 已确认(2)/已排除(3)
2. 是 → 直接返回，什么都不做
3. 否 → INSERT ... ON DUPLICATE KEY UPDATE 覆盖分数与命中开关
```

实测结果：

| 场景 | 重跑前 | 重跑后 | 说明 |
| --- | --- | --- | --- |
| A02（线索已确认） | 6.15 | **6.15** | 被跳过，核查结论不受影响 |
| A05（无线索） | 2.93 | **9.99**（测试值） | 正常覆盖 |

**为什么这样就"冻结"了**：评分行不动 → 明细行不动 → `v_clue_list` 展示的分数和理由就不动。不需要在 `risk_clue` 里再存一份快照。

### 9.2 闭环是"触发器推状态 + 明细定位特征"

```
线索生成 → 人工核查 → 插入 clue_feedback
                          │
                          ├─ 触发器 trg_feedback_close_clue
                          │     → risk_clue.clue_status = 2/3，写 close_at
                          │     → 顺带触发 trg_clue_audit 写审计
                          │
                          └─ 插入 clue_feedback_feature
                                → 记录哪条特征被否定
                                → 下一轮 sp_calc_feature_weight 据此调 case_hit
```

实测：插入 3 条反馈后，线索状态自动变成 `2,3,2`，`close_at` 自动写入，审计表自动多出 3 条记录（`user_id` 和 `operator_tag` 都正确）。

---

## 十、三库靠哪些字段串起来

只要记住这几条连接，三库就是"一个整体"而不是三张皮：

| 连接 | 字段 | 说明 |
| --- | --- | --- |
| 人 | `person_info.person_id` | 案件、消费、订单、对照、个人线索都指向它，**最重要的一条** |
| 区域 | `area_info.area_id` | 场所、人员住址、案件、订单起终点、卡口、评分都指向它 |
| 场所 | `place_info.place_id` | 案件（案发前场所）与消费流水共用 |
| 车辆 | `vehicle_owner.vehicle_id` | 案件与卡口流水共用，"车 → 人"的桥梁是 `owner_person_id` |
| 特征 | `feature_def.feature_id` | 权重表、规则关联表、命中明细表都引用它 |
| 权重版本 | `feature_version.version_id` | 权重、规则、批次、评分、线索都挂版本，保证可复现 |
| 规则 | `judge_rule.rule_id` | 规则关联特征、批次、评分 |
| 批次 | `judge_batch.batch_id` | 串起评分与线索，一次研判一条链 |
| **对象** | `risk_score.object_id` | **生成列**，把区域/日期类型/小时或人员编号合成一个稳定标识 |
| **时间** | `param_config.history_cutoff` | 全库唯一时点：案例库只存它之前的案件 |

**必须守住的三条**：

1. 信息库所有 `person_id` 必须能在 `person_info` 找到，`area_id` 必须能在 `area_info` 找到——导入后跑孤儿检查；
2. `feature_def.match_src` 不能出现 `case_info`——CHECK 已经拦住，写入直接报错；
3. 观察段流水的时间必须 ≥ `history_cutoff`，历史段案件必须 < 它——否则时间轴失效。

---

## 十一、最容易混淆的字段

| 看着像 | 区别 |
| --- | --- |
| `person_type` vs `person_id` | 前者是"这个人算哪类样本"（案件人员 / 对照 / 待研判），后者是"是谁" |
| `object_type` vs `object_id` | 前者说"判的是什么"（区域时段还是个人），后者是那个东西的具体标识（生成列） |
| **`src_table` vs `match_src`** | **前者是统计 P1/P0 时从哪取数（可用 case_info），后者是研判匹配时从哪取数（只能是信息库或 v_case_history）。混用就是循环论证** |
| **`case_info` vs `v_case_history`** | 前者是基表，能塞进任何日期的案件；后者是视图，只返回 `history_cutoff` 之前的。**研判只许读后者** |
| `p1` vs `case_hit` | p1 是比率（生成列，自动算），case_hit 是绝对条数。两个都留，权重才可复算 |
| `weight` vs `lift` | lift 是"这条特征偏风险多少倍"（给人看），weight 是"评分时加多少分"（给程序用） |
| **`risk_score.total_score` vs `risk_score_feature.weight`** | 前者是结果汇总，后者是每条特征的权重快照。**后者才是可复算的来源** |
| **`risk_score` vs `risk_clue`** | 前者是研判结果（每个对象都有），后者是达到阈值后的**状态机**（只有出的线索才有） |
| `clue_feedback` vs `clue_feedback_feature` | 前者记"这条线索真不真"，后者记"哪条特征骗了我" |
| `hit_features`（已删除） | 旧版用字符串存，本版已拆成 `risk_score_feature`。视图里的 `hit_features` 是 `GROUP_CONCAT` 出来的展示列，不是存储 |
| `direction`（卡口） vs `direction`（特征） | 卡口的是"驶入/驶出区域"，特征的是"正向/反向特征"，同名不同义 |
| `has_alcohol` vs `alcohol_value` | 前者是消费流水"含不含酒水"，后者是案件"血液酒精含量"，一个是行为证据一个是结果证据 |
| `order_type` vs `order_status` | 前者是网约车/代驾，后者是已完成/取消；**判断"有无代驾"必须两个条件都看** |
| `is_valid` vs `status` | is_valid 是"这条权重能不能用"（样本不足就废掉），status 是"这条记录还启不启用" |
| `is_hit` vs `is_missing` | 前者"命中了没有"，后者"数据缺不缺"。**缺失不能当未命中计入分母** |
| `history_cutoff` vs `data_start/data_end` | 前者是案例库/观察段的分界（全局唯一），后者是某次研判的数据窗口（每批不同，必须落在观察段内） |

---

## 十二、明确不做的三件事

诚实列出边界，比含糊带过更容易通过答辩：

| 不做的事 | 为什么 | 影响与替代 |
| --- | --- | --- |
| **一案多人（同车人）** | 需要再加一张 `case_person` 关联表，超出 26 张表的范围 | 当前 `case_info.person_id` 只记一名涉事人员；报告里说明这是简化 |
| **以车代人（精确到驾驶人）** | 卡口只能识车，不能识人；借车、家人代开都会误判 | F004 只在区域级使用（数车辆），个人规则 R002 不含 F004；`driver_confirmed` 标注哪些案件经过人工确认 |
| **缺失样本的全量处理** | 完整做法要对每个特征做"可计算性"判定，并在分母里剔除缺失样本 | 已提供 `risk_score_feature.is_missing` 字段与口径说明；示例数据里对照人员都补了流水，避免踩坑 |

另外两条"选做"已在本版完成，不再列入：特征版本一键回滚、阈值敏感性实验的取数 SQL。

---

## 附录：验收 SQL

```sql
-- 1. 没有任何特征的研判口径指向案件原表  → 0 行
SELECT feature_id FROM feature_def WHERE match_src = 'case_info';

-- 2. 案例库里没有观察段数据  → 0
SELECT COUNT(*) FROM case_info
 WHERE occur_time >= (SELECT CAST(param_value AS DATETIME) FROM param_config
                      WHERE param_key = 'history_cutoff');

-- 3. 评估集干扰样本占比 ≥ 30%  → 0.40
SELECT SUM(sample_type = 2) / COUNT(*) FROM eval_label;

-- 4. 总分与明细可复算  → 两列相等
SELECT s.score_id, s.total_score,
       (SELECT ROUND(SUM(x.weight), 2) FROM risk_score_feature x
         WHERE x.score_id = s.score_id AND x.is_hit = 1) AS 明细加权和
FROM risk_score s;

-- 5. 混淆矩阵  → TP=3 FP=1 FN=0 TN=6
SELECT SUM(l.label = 1 AND IFNULL(s.is_clue,0) = 1) AS TP,
       SUM(l.label = 0 AND IFNULL(s.is_clue,0) = 1) AS FP,
       SUM(l.label = 1 AND IFNULL(s.is_clue,0) = 0) AS FN,
       SUM(l.label = 0 AND IFNULL(s.is_clue,0) = 0) AS TN
FROM eval_label l
LEFT JOIN risk_score s ON s.object_type = l.object_type AND s.object_id = l.object_id;

-- 6. 闭环：哪条特征被核查否定  → F001、F002 各 1 次
SELECT f.feature_id, f.feature_name, COUNT(*) AS 被否定次数
FROM clue_feedback_feature cff
JOIN feature_def f ON f.feature_id = cff.feature_id
WHERE cff.is_wrong = 1
GROUP BY f.feature_id, f.feature_name;
```

**约束自测（应当全部报错）**

```sql
UPDATE feature_def SET match_src = 'case_info' WHERE feature_id = 'F003';
-- ERROR 3819: Check constraint 'ck_feature_match_src' is violated.

INSERT INTO vehicle_track (record_no, vehicle_id, gate_id, area_id, pass_time, direction)
VALUES ('VTX','V0001','A02-G09','A01','2026-11-10 10:00:00',2);
-- ERROR 3819: Check constraint 'ck_track_area_match' is violated.

UPDATE risk_clue SET clue_status = 2 WHERE clue_id = 'CL2026110704';
-- ERROR 3819: Check constraint 'ck_clue_close' is violated.

INSERT INTO risk_score (batch_id, rule_id, version_id, object_type, area_id, day_type, hour_slot)
VALUES ('B2026110707','R001','V20261001_01',1,'A09',1,NULL);
-- ERROR 3819: Check constraint 'ck_score_region_fields' is violated.

INSERT INTO feature_version (version_id, risk_type, version_no, publish_status, published_by)
VALUES ('V20261101_03',1,'2.1',1,'U0009');
-- ERROR 1062: Duplicate entry '1-1' for key 'feature_version.uk_version_current'
```

---

## 附录：示例库规模（26 张表，6477 行）

| 组 | 行数 |
| --- | --- |
| 安全支撑库 | sys_role 5、sys_user 10、sys_user_role 10、audit_log 107、param_config 10 |
| 案例库 | area_info 12、place_info 30、person_info 546、vehicle_owner 187、case_info 200、control_person 400 |
| 信息库 | consume_record 1344、taxi_order 361、vehicle_track 2018 |
| 特征库 | feature_def 8、feature_version 3、feature_weight 8、judge_rule 3、rule_feature 12 |
| 研判线索库 | judge_batch 43、risk_score 178、risk_score_feature 681、risk_clue 78、clue_feedback 60、clue_feedback_feature 41、eval_label 122 |

> 数据由 `tools/gen_demo_data.py` 按"以案生数 + 两段切分"生成，固定随机种子，可复算。
> 数据分两批生成，各自独立随机源：第一批 3219 行（v2.1），第二批 3258 行（本次追加），第一批**逐行未改**。
> 规模口径：**200 起历史案件（7–10 月，两批各 100 起）+ 400 条对照样本**，现行权重仍按首批 100 起 / 200 条统计（`based_case_cnt` 可查）；
> 观察段 8 个夜晚共 129 个区域时段对象，其中 48 条达到线索阈值；
> 另有个人研判批次，49 个对象出 30 条线索。合计 78 条线索，覆盖待核查/核查中/已确认/已排除四种状态。
> 每一项派生值（P1/P0/lift、总分、混淆矩阵）都能用库里的数据复算，没有手填数。

---

*本文档与 [sql/risk_alert_示例库.sql](sql/risk_alert_示例库.sql) 严格对应，字段名、类型、约束均已在 MySQL 8.4 上实测通过。*
