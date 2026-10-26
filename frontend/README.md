# 前端：多风险特征预警系统

按《前端交接文档》实现的 12 个页面。后端未就绪时用前端内置的模拟数据运行，数据逐行取自 `sql/risk_alert_示例库.sql`。

技术栈：Vue 3 + Vite + Element Plus + ECharts + Vue Router + Pinia。

## 启动

需要 Node.js 18 及以上。

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。

### 演示账号

口令统一为 `123456`，与建库脚本一致。登录页上点账号即可填入。

| 用户名 | 角色 | 能看到的页面 |
|---|---|---|
| analyst1 | 研判员 + 教师 | A1 B1 B2 C1 C2 D1 D2 D3 E1 E2 E4（线索可操作） |
| analyst2 | 研判员 | A1 B1 B2 C1 C2（线索可操作） |
| featop | 特征管理员 | A1 D1 D2 D3 E4（特征、版本、批次可操作） |
| admin | 系统管理员 | A1 D3 E2 E3（批次、参数可操作） |
| teacher | 教师/评审 | 除 E3 外全部，只读 |
| dataop | 数据管理员 | 仅 A1（见缺口 #13） |

`guest` 在示例库里是停用状态，登录会被拒绝。

### 切换到真实后端

修改 `frontend/.env.development`：

```
VITE_API_MODE=real
VITE_API_BASE=http://127.0.0.1:5000
```

改完重启 `npm run dev`。前端在请求头里带 `Authorization: Bearer <token>`，后端需要开启 CORS。

### 模拟数据说明

- **改动会保存在本浏览器**（localStorage），刷新后不会丢。右上角用户菜单 →「重置演示数据」可恢复为示例库初始状态。
- **规则照搬建库脚本**：状态机、`ck_clue_close`、触发器 `trg_feedback_close_clue` / `trg_clue_audit` / `trg_weight_audit`、存储过程 `sp_calc_feature_weight` / `sp_upsert_score`、`uk_version_current` 都在 `src/api/mock/server.js` 里按同样的规则实现。
- **演示时钟**：示例数据的日期在 2026 年 11 月。模拟服务记录"当前时间"时，取电脑时间与"最近一条审计记录之后 1 分钟"中较晚的那个，避免新记录早于示例数据。
- **研判引擎（接口 16）是简化版**，只用于演示"执行中 → 结果"：
  - 时间窗统一用批次数据窗，没有逐特征使用 `time_window_min`；
  - 样本量 = 归集到的流水条数。

  正式算法以后端为准（《前端交接文档》第七节）。

## 答辩演示路线

1. 用 `analyst1` 登录，打开**首页**：数字卡、热力图、最新线索。
2. 点热力图里"老城餐饮街 · 周末 · 23 点"进入 **B2**，回答"为什么提示"：
   - 逐条特征判定；
   - 公式 `1.1693 + 2.9285 + 1.9274 = 6.0252 ≈ 6.03`。
3. 打开**线索列表**，点 `CL2026110704`（核查中）走一遍 **C2** 闭环：
   - 点「排除」，填写核查方式和说明，勾选被否定的特征，提交；
   - 线索变为"已排除"，核查记录里出现被否定的特征。
4. 打开**特征清单**，看双口径：训练源 `case_info` 与研判源分列，中间有竖线分隔。进入被否定的特征，「核查否定记录」里能看到刚才那条。
5. 打开**评估报告**（E1），回答"怎么证明有效"：混淆矩阵 3/1/0/6，精确率 0.75，召回率 1.00，误报率 0.14，F1 0.86。
6. 换 `featop` 登录，在**版本与批次**创建批次并执行研判。也可以重新执行失败的 `B2026110706`：它使用的草稿版本没有权重，会再次失败并说明原因。
7. 页脚的"数据健康"小绿灯：鼠标悬停可看 4 项检查结果。

## 目录

```
src/
  api/index.js           请求封装（mock / real 同一路径）+ 24 个接口
  api/mock/seed.js       示例库 26 张表、259 行数据
  api/mock/server.js     模拟后端：路由、视图、触发器、存储过程、研判引擎
  constants/enums.js     枚举中文映射（页面不出现裸数字）
  constants/permissions.js  角色 → 页面 / 操作 权限矩阵
  components/            布局、等级/状态标签、特征判定表、线索抽屉、核查表单、图表、健康灯
  views/                 12 个页面 + 登录 + 无权访问
```

## 与交接文档的对应

| 交接文档要求 | 实现位置 |
|---|---|
| 12 个页面、路由 | `src/router/index.js`（C2 用抽屉挂在 `/clues/:clueId`） |
| 枚举中文映射 | `src/constants/enums.js` |
| 按角色隐藏菜单与按钮（不是禁用） | `src/constants/permissions.js`、`AppLayout.vue`、各页面 `auth.can()` |
| 未登录跳登录页、401 统一跳转 | `src/router/index.js`、`src/main.js` |
| B2 命中高亮、`is_missing` 显示"数据不足"、总分公式 | `components/FeatureJudgeTable.vue` |
| C2 只显示合法流转按钮、核查时勾选被否定的特征 | `components/ClueDrawer.vue`、`components/FeedbackDialog.vue` |
| D1 训练源 / 研判源并排，用竖线分隔 | `views/FeatureListView.vue` |
| E1 指标取接口返回值，分母为 0 显示"—" | `views/EvalView.vue` |
| 加载中 / 空数据 / 报错三种状态 | `components/AsyncState.vue` |
| 日期半开区间传参 | `utils/format.js` 的 `halfOpenRange` |
| 页脚声明 + 数据健康灯 | `components/AppLayout.vue`、`components/HealthLight.vue` |
| 不出现身份证、手机号、车牌明文 | 模拟库里不存姓名、手机号、车牌；个人对象只显示编号 |

## 文档缺口与矛盾（请后端 / 数据库同学确认）

| # | 问题 | 前端的处理 / 建议 |
|---|---|---|
| 1 | 24 个接口里没有登录接口，但第十节要求未登录跳转登录页 | 前端按 `POST /api/login` 调用：请求体 `{username, password}`，返回 `{token, user: {user_id, username, real_name, roles}}`。请后端补上 |
| 2 | 系统管理员"不直接看线索"，但 A1 有"最新线索 Top5" | 对管理员、数据管理员、特征管理员隐藏线索区块，改为显示可进入的模块 |
| 3 | 枚举表缺 `check_method`、`feature_cat`、`value_type`、`area_type`、`op_type` 等 | 按建库脚本字段注释补齐 |
| 4 | 接口 4 的 SQL 用中文 `status_name` 过滤，而参数是数字 `status` | 前端传数字，建议 SQL 改为 `clue_status = ?` |
| 5 | 接口 19（审计）的 SQL 用 `BETWEEN`，与 5.1 的半开区间约定矛盾 | 前端传半开区间 `from` / `to`，建议 SQL 改为 `op_time >= ? AND op_time < ?` |
| 6 | 接口 1 没有热力图和 Top5 所需的数据 | A1 另调接口 2 和接口 4；接口 4 多加参数 `order=latest`（按生成时间倒序） |
| 7 | 视图缺少前端跳转和筛选要用的字段 | 建议：`v_region_risk` 加 `score_id`、`risk_level`、`day_type`（B1 → B2 跳转、按等级筛选）；`v_clue_list` 加 `clue_status`、`score_id`、`object_type`、`object_id`、`risk_level`（个人线索没有区域，需要显示对象编号） |
| 8 | 区域、规则等下拉选项没有接口 | 前端调用 `GET /api/dicts`，返回 `{areas, rules, history_cutoff}`。请后端补上 |
| 9 | 部分接口返回字段不够页面用 | 前端额外使用的字段：<br>· 接口 9：`negations`（核查否定记录）、`versions`<br>· 接口 11：`weight_cnt`、`published_by_name`<br>· 接口 14：`rule_name`、`area_name`、`operator_name`<br>· 接口 16：`skipped_cnt`、`message`<br>· 接口 1：`clue_checking`<br>· 接口 23：`history_cutoff`、`case_info_total` |
| 10 | 接口 21 的 SQL 按 `param_group` 排序，但 `param_config` 表没有这一列 | 前端按 `param_key` 排序 |
| 11 | 第七节研判第 2 步写 `start_at`，但 `judge_batch` 表没有这一列 | 不影响前端，请后端注意 |
| 12 | 接口 7 说演示时"评估页误报率变化"，但第八节的评估 SQL 用 `risk_score.is_clue` 判定，与核查结论无关，提交"不属实"后误报率**不会变** | 前端按第八节的 SQL 实现。需要组里决定：改演示话术，还是改评估口径 |
| 13 | 数据管理员（R_DATA）的"信息库明细 / 导入质量报告"不在 12 个页面里 | 数据管理员目前只能看 A1 和页脚健康检查 |
| 14 | 评估报告只给教师看（第四节），特征管理员调权时看不到 | 暂按文档执行；如需开放，改 `PAGE_ROLES.eval` |
| 15 | 接口 1 的示例 `clue_open: 1` 与示例数据不符：按 SQL 统计，待核查为 0、核查中为 1 | 首页"待核查"按 SQL 统计 `clue_status=0`，另外单独显示"核查中"数量 |
| 16 | "直接排除"该走接口 6（状态改为 3）还是接口 7 | 前端走接口 7（核查结论 = 不属实），这样能留下排除理由和被否定的特征，状态由触发器推进 |
