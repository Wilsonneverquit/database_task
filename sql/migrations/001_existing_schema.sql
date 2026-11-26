-- Existing 26-table schema only; no DROP DATABASE and no old synthetic data.
CREATE TABLE sys_role (
  role_id    VARCHAR(16)  NOT NULL COMMENT '角色编号',
  role_name  VARCHAR(40)  NOT NULL COMMENT '角色名称',
  role_desc  VARCHAR(200)          COMMENT '职责说明',
  status     TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  PRIMARY KEY (role_id),
  UNIQUE KEY uk_role_name (role_name),
  CONSTRAINT ck_role_status CHECK (status IN (0,1))
) ENGINE=InnoDB COMMENT='角色表';

CREATE TABLE sys_user (
  user_id       VARCHAR(20)  NOT NULL COMMENT '用户编号',
  username      VARCHAR(40)  NOT NULL COMMENT '登录名（区分大小写）',
  password_hash VARCHAR(128) NOT NULL COMMENT 'SHA2(salt+口令,256)',
  salt          CHAR(16)     NOT NULL COMMENT '盐值',
  real_name     VARCHAR(40)           COMMENT '姓名',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '1正常 2停用 3锁定',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_username (username),
  CONSTRAINT ck_user_status CHECK (status IN (1,2,3))
) ENGINE=InnoDB COMMENT='用户表';

CREATE TABLE sys_user_role (
  user_id    VARCHAR(20) NOT NULL COMMENT '用户',
  role_id    VARCHAR(16) NOT NULL COMMENT '角色',
  granted_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
  PRIMARY KEY (user_id, role_id),
  CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES sys_user (user_id),
  CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES sys_role (role_id)
) ENGINE=InnoDB COMMENT='用户角色表';

CREATE TABLE audit_log (
  log_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '日志号',
  user_id      VARCHAR(20)           COMMENT '操作人（会话变量解析不到时为空）',
  operator_tag VARCHAR(40)           COMMENT '会话操作人标识 @app_user_id，取不到记 system',
  op_type      TINYINT      NOT NULL COMMENT '1登录 2查询 3新增 4修改 5删除 6导出 7研判 8授权',
  table_name   VARCHAR(64)           COMMENT '被操作表',
  record_pk    VARCHAR(64)           COMMENT '被操作记录主键',
  op_desc      VARCHAR(255)          COMMENT '描述',
  op_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
  PRIMARY KEY (log_id),
  KEY idx_audit_time (op_time),
  KEY idx_audit_user (user_id, op_time),
  CONSTRAINT ck_audit_optype CHECK (op_type BETWEEN 1 AND 8),
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES sys_user (user_id)
) ENGINE=InnoDB COMMENT='审计日志表：谁 + 什么时候 + 改了什么';

CREATE TABLE param_config (
  param_id    INT          NOT NULL AUTO_INCREMENT COMMENT '流水号',
  param_key   VARCHAR(60)  NOT NULL COMMENT '参数名',
  param_value VARCHAR(200) NOT NULL COMMENT '参数值',
  param_type  TINYINT      NOT NULL DEFAULT 3 COMMENT '1整型 2小数 3字符串 4布尔',
  param_desc  VARCHAR(255)          COMMENT '含义',
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (param_id),
  UNIQUE KEY uk_param_key (param_key),
  CONSTRAINT ck_param_type CHECK (param_type BETWEEN 1 AND 4)
) ENGINE=InnoDB COMMENT='参数配置表（含 history_cutoff 时间边界）';

CREATE TABLE area_info (
  area_id        VARCHAR(12) NOT NULL COMMENT '区域编号',
  area_name      VARCHAR(60) NOT NULL COMMENT '区域名称（虚构）',
  area_type      TINYINT     NOT NULL DEFAULT 1 COMMENT '1城市道路 2商圈 3乡镇 4高速出入口',
  parent_area_id VARCHAR(12)          COMMENT '上级区域',
  lng            DECIMAL(10,6) NOT NULL COMMENT '中心点经度（虚构坐标，仅用于前端地图展示）',
  lat            DECIMAL(10,6) NOT NULL COMMENT '中心点纬度（虚构坐标，仅用于前端地图展示）',
  is_active      TINYINT     NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (area_id),
  CONSTRAINT ck_area_type CHECK (area_type BETWEEN 1 AND 4),
  CONSTRAINT ck_area_coord CHECK (lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90),
  CONSTRAINT fk_area_parent FOREIGN KEY (parent_area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='区域表';

CREATE TABLE place_info (
  place_id   VARCHAR(16) NOT NULL COMMENT '场所编号',
  place_name VARCHAR(80) NOT NULL COMMENT '场所名称（虚构）',
  place_type TINYINT     NOT NULL DEFAULT 1 COMMENT '1饭店 2KTV 3酒吧 4其他',
  area_id    VARCHAR(12) NOT NULL COMMENT '所属区域',
  address    VARCHAR(200)         COMMENT '地址（虚构）',
  is_active  TINYINT     NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  PRIMARY KEY (place_id),
  KEY idx_place_area (area_id, place_type),
  CONSTRAINT ck_place_type CHECK (place_type BETWEEN 1 AND 4),
  CONSTRAINT fk_place_area FOREIGN KEY (area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='场所表';

CREATE TABLE person_info (
  person_id    VARCHAR(16) NOT NULL COMMENT '人员编号（三库统一编码）',
  person_name  VARCHAR(40) NOT NULL COMMENT '姓名（虚构）',
  gender       TINYINT     NOT NULL DEFAULT 0 COMMENT '0未知 1男 2女',
  birth_year   SMALLINT             COMMENT '出生年份',
  phone_hash   CHAR(64)             COMMENT '手机号散列',
  home_area_id VARCHAR(12)          COMMENT '居住区域（算"离家较远"的基准点）',
  person_type  TINYINT     NOT NULL DEFAULT 1 COMMENT '1案件涉事人 2对照人 3研判对象',
  created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (person_id),
  UNIQUE KEY uk_person_phone (phone_hash),
  KEY idx_person_home (home_area_id),
  CONSTRAINT ck_person_gender CHECK (gender IN (0,1,2)),
  CONSTRAINT ck_person_type CHECK (person_type IN (1,2,3)),
  CONSTRAINT ck_person_birth CHECK (birth_year IS NULL OR birth_year BETWEEN 1900 AND 2020),
  CONSTRAINT fk_person_area FOREIGN KEY (home_area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='人员表';

CREATE TABLE vehicle_owner (
  vehicle_id     VARCHAR(16) NOT NULL COMMENT '车辆编号',
  plate_hash     CHAR(64)    NOT NULL COMMENT '车牌散列',
  plate_mask     VARCHAR(16) NOT NULL COMMENT '车牌展示值',
  owner_person_id VARCHAR(16) NOT NULL COMMENT '车主',
  vehicle_type   TINYINT     NOT NULL DEFAULT 1 COMMENT '1小型 2大型 3摩托 4其他',
  is_active      TINYINT     NOT NULL DEFAULT 1 COMMENT '1有效 0注销',
  PRIMARY KEY (vehicle_id),
  UNIQUE KEY uk_plate (plate_hash),
  KEY idx_vehicle_owner (owner_person_id),
  CONSTRAINT ck_vehicle_type CHECK (vehicle_type BETWEEN 1 AND 4),
  CONSTRAINT fk_vehicle_owner FOREIGN KEY (owner_person_id) REFERENCES person_info (person_id)
) ENGINE=InnoDB COMMENT='车辆车主表';

CREATE TABLE case_info (
  case_id         VARCHAR(20)  NOT NULL COMMENT '案件编号',
  occur_time      DATETIME     NOT NULL COMMENT '案发时间（必须早于 history_cutoff）',
  occur_hour      TINYINT      GENERATED ALWAYS AS (HOUR(occur_time)) STORED
                               COMMENT '案发小时：生成列，物理上不可能与 occur_time 不一致',
  area_id         VARCHAR(12)  NOT NULL COMMENT '案发区域',
  place_id        VARCHAR(16)           COMMENT '案发前消费场所（可空）',
  person_id       VARCHAR(16)  NOT NULL COMMENT '涉事人员',
  vehicle_id      VARCHAR(16)           COMMENT '涉事车辆（可空）',
  driver_confirmed TINYINT     NOT NULL DEFAULT 0 COMMENT '1已人工确认驾驶人=车主；0仅有车辆归属',
  case_type       TINYINT      NOT NULL DEFAULT 1 COMMENT '1饮酒驾驶 2醉酒驾驶 3酒驾肇事',
  alcohol_value   DECIMAL(5,1) NOT NULL COMMENT '血液酒精含量 mg/100mL',
  distance_home   DECIMAL(6,2)          COMMENT '距住所公里（仅展示/统计，不被特征读取）',
  dispose_status  TINYINT      NOT NULL DEFAULT 0 COMMENT '0待处置 1已处罚 2已移送',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (case_id),
  KEY idx_case_time_area (occur_time, area_id),
  KEY idx_case_person (person_id, occur_time),
  KEY idx_case_hour (occur_hour),
  CONSTRAINT ck_case_alcohol CHECK (alcohol_value > 0 AND alcohol_value <= 500),
  CONSTRAINT ck_case_distance CHECK (distance_home IS NULL OR (distance_home >= 0 AND distance_home <= 200)),
  CONSTRAINT ck_case_type CHECK (case_type BETWEEN 1 AND 3),
  CONSTRAINT ck_case_dispose CHECK (dispose_status BETWEEN 0 AND 3),
  CONSTRAINT ck_case_driver CHECK (driver_confirmed IN (0,1)),
  CONSTRAINT fk_case_area FOREIGN KEY (area_id) REFERENCES area_info (area_id),
  CONSTRAINT fk_case_place FOREIGN KEY (place_id) REFERENCES place_info (place_id),
  CONSTRAINT fk_case_person FOREIGN KEY (person_id) REFERENCES person_info (person_id),
  CONSTRAINT fk_case_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicle_owner (vehicle_id)
) ENGINE=InnoDB COMMENT='案件表：只存历史段（occur_time < history_cutoff）';

CREATE TABLE control_person (
  control_id  BIGINT      NOT NULL AUTO_INCREMENT COMMENT '流水号',
  person_id   VARCHAR(16) NOT NULL COMMENT '对照人员',
  area_id     VARCHAR(12) NOT NULL COMMENT '对照区域',
  sample_date DATE        NOT NULL COMMENT '对照日期',
  hour_slot   TINYINT     NOT NULL COMMENT '对照时段 0-23',
  match_type  TINYINT     NOT NULL DEFAULT 1 COMMENT '1同期同区域 2同期同类 3随机',
  PRIMARY KEY (control_id),
  UNIQUE KEY uk_control (person_id, sample_date, hour_slot),
  KEY idx_control_area (area_id, sample_date, hour_slot),
  CONSTRAINT ck_control_hour CHECK (hour_slot BETWEEN 0 AND 23),
  CONSTRAINT ck_control_match CHECK (match_type IN (1,2,3)),
  CONSTRAINT fk_control_person FOREIGN KEY (person_id) REFERENCES person_info (person_id),
  CONSTRAINT fk_control_area FOREIGN KEY (area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='对照人群表：算 p0 的分组，只取历史段';

CREATE TABLE consume_record (
  consume_id   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '流水号',
  record_no    VARCHAR(32)  NOT NULL COMMENT '业务流水号',
  person_id    VARCHAR(16)  NOT NULL COMMENT '消费者',
  place_id     VARCHAR(16)  NOT NULL COMMENT '场所',
  consume_time DATETIME     NOT NULL COMMENT '消费时间',
  amount       DECIMAL(10,2) NOT NULL COMMENT '金额（元）',
  has_alcohol  TINYINT      NOT NULL DEFAULT 0 COMMENT '1含酒水',
  PRIMARY KEY (consume_id),
  UNIQUE KEY uk_consume_no (record_no),
  KEY idx_consume_person (person_id, consume_time),
  KEY idx_consume_place (place_id, consume_time),
  CONSTRAINT ck_consume_amount CHECK (amount >= 0 AND amount <= 100000),
  CONSTRAINT ck_consume_alcohol CHECK (has_alcohol IN (0,1)),
  CONSTRAINT fk_consume_person FOREIGN KEY (person_id) REFERENCES person_info (person_id),
  CONSTRAINT fk_consume_place FOREIGN KEY (place_id) REFERENCES place_info (place_id)
) ENGINE=InnoDB COMMENT='消费流水表（历史段+观察段都有）';

CREATE TABLE taxi_order (
  order_id      BIGINT      NOT NULL AUTO_INCREMENT COMMENT '流水号',
  order_no      VARCHAR(32) NOT NULL COMMENT '订单号',
  person_id     VARCHAR(16) NOT NULL COMMENT '下单人',
  order_type    TINYINT     NOT NULL DEFAULT 1 COMMENT '1网约车 2代驾',
  order_time    DATETIME    NOT NULL COMMENT '下单时间',
  start_area_id VARCHAR(12)          COMMENT '出发区域',
  end_area_id   VARCHAR(12)          COMMENT '到达区域',
  order_status  TINYINT     NOT NULL DEFAULT 1 COMMENT '1已完成 2取消 3进行中',
  PRIMARY KEY (order_id),
  UNIQUE KEY uk_order_no (order_no),
  KEY idx_taxi_person (person_id, order_time),
  KEY idx_taxi_type (order_type, order_time),
  CONSTRAINT ck_taxi_type CHECK (order_type IN (1,2)),
  CONSTRAINT ck_taxi_status CHECK (order_status BETWEEN 1 AND 3),
  CONSTRAINT fk_taxi_person FOREIGN KEY (person_id) REFERENCES person_info (person_id),
  CONSTRAINT fk_taxi_sarea FOREIGN KEY (start_area_id) REFERENCES area_info (area_id),
  CONSTRAINT fk_taxi_earea FOREIGN KEY (end_area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='出行订单表（网约车+代驾）';

CREATE TABLE vehicle_track (
  track_id   BIGINT      NOT NULL AUTO_INCREMENT COMMENT '流水号',
  record_no  VARCHAR(32) NOT NULL COMMENT '抓拍流水号',
  vehicle_id VARCHAR(16) NOT NULL COMMENT '车辆',
  gate_id    VARCHAR(16) NOT NULL COMMENT '卡口编号，结构为 区域编号-卡口序号（如 A02-G01）',
  area_id    VARCHAR(12) NOT NULL COMMENT '卡口所属区域（冗余，由 gate_id 前缀决定，CHECK 锁死）',
  pass_time  DATETIME    NOT NULL COMMENT '过车时间',
  direction  TINYINT     NOT NULL DEFAULT 1 COMMENT '1驶入区域 2驶出区域',
  PRIMARY KEY (track_id),
  UNIQUE KEY uk_track_no (record_no),
  KEY idx_track_vehicle (vehicle_id, pass_time),
  KEY idx_track_area (area_id, pass_time),
  KEY idx_track_gate (gate_id, pass_time),
  CONSTRAINT ck_track_direction CHECK (direction IN (1,2)),
  -- 冗余不能手填错：区域必须等于卡口编号的前缀
  CONSTRAINT ck_track_area_match CHECK (area_id = SUBSTRING_INDEX(gate_id, '-', 1)),
  CONSTRAINT fk_track_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicle_owner (vehicle_id),
  CONSTRAINT fk_track_area FOREIGN KEY (area_id) REFERENCES area_info (area_id)
) ENGINE=InnoDB COMMENT='卡口过车表';

CREATE TABLE feature_def (
  feature_id      VARCHAR(16)  NOT NULL COMMENT '特征编号',
  feature_code    VARCHAR(40)  NOT NULL COMMENT '英文编码',
  feature_name    VARCHAR(80)  NOT NULL COMMENT '特征名称',
  risk_type       TINYINT      NOT NULL DEFAULT 1 COMMENT '风险类型：1酒驾（预留扩展）',
  feature_cat     TINYINT      NOT NULL DEFAULT 1 COMMENT '1时空 2消费 3出行 4行为 5反例',
  direction       TINYINT      NOT NULL DEFAULT 1 COMMENT '1正向 2反向',
  object_scope    TINYINT      NOT NULL DEFAULT 3 COMMENT '1区域时段 2个人 3两者',
  value_type      TINYINT      NOT NULL DEFAULT 1 COMMENT '1布尔 2数值阈值 3枚举 4频次',
  src_table       VARCHAR(64)  NOT NULL COMMENT '训练口径：统计 p1/p0 的取数表（用 case_info）',
  match_src       VARCHAR(64)           COMMENT '研判口径：匹配取数表；NULL=同 src_table；白名单见 CHECK',
  match_expr      VARCHAR(500)          COMMENT '匹配口径说明（什么算命中）',
  time_window_min INT          NOT NULL DEFAULT 180 COMMENT '取数窗口（分钟）',
  min_sample      INT          NOT NULL DEFAULT 5 COMMENT '样本下限',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  description     VARCHAR(255)          COMMENT '口径说明',
  PRIMARY KEY (feature_id),
  UNIQUE KEY uk_feature_code (feature_code),
  KEY idx_feature_cat (feature_cat),
  CONSTRAINT ck_feature_cat CHECK (feature_cat BETWEEN 1 AND 5),
  CONSTRAINT ck_feature_dir CHECK (direction IN (1,2)),
  CONSTRAINT ck_feature_scope CHECK (object_scope IN (1,2,3)),
  CONSTRAINT ck_feature_valtype CHECK (value_type BETWEEN 1 AND 4),
  CONSTRAINT ck_feature_status CHECK (status IN (0,1)),
  -- 方案 C 的关键约束：研判取数表只能是信息库表或历史视图，case_info 原表进不来
  CONSTRAINT ck_feature_match_src CHECK (
    match_src IS NULL OR match_src IN
      ('consume_record','taxi_order','vehicle_track','person_info','place_info','v_case_history'))
) ENGINE=InnoDB COMMENT='特征定义表：双口径（src_table 训练 / match_src 研判）';

CREATE TABLE feature_version (
  version_id     VARCHAR(20) NOT NULL COMMENT '版本编号',
  risk_type      TINYINT     NOT NULL DEFAULT 1 COMMENT '风险类型：1酒驾',
  version_no     VARCHAR(20) NOT NULL COMMENT '版本号',
  publish_status TINYINT     NOT NULL DEFAULT 0 COMMENT '0草稿 1已发布 2已归档',
  current_flag   TINYINT     GENERATED ALWAYS AS (IF(publish_status = 1, 1, NULL)) STORED
                             COMMENT '已发布标记：配合唯一键保证同风险类型只有一个在用版本',
  based_case_cnt INT         NOT NULL DEFAULT 0 COMMENT '统计用案件数',
  based_ctrl_cnt INT         NOT NULL DEFAULT 0 COMMENT '统计用对照数',
  calc_at        DATETIME             COMMENT '权重计算时间',
  published_by   VARCHAR(20)          COMMENT '发布人',
  remark         VARCHAR(255)         COMMENT '版本说明',
  created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (version_id),
  UNIQUE KEY uk_version_no (risk_type, version_no),
  UNIQUE KEY uk_version_current (risk_type, current_flag),
  CONSTRAINT ck_version_status CHECK (publish_status IN (0,1,2)),
  CONSTRAINT fk_version_pub FOREIGN KEY (published_by) REFERENCES sys_user (user_id)
) ENGINE=InnoDB COMMENT='特征库版本表：同一风险类型只能有一个已发布版本';

CREATE TABLE feature_weight (
  weight_id  BIGINT      NOT NULL AUTO_INCREMENT COMMENT '流水号',
  version_id VARCHAR(20) NOT NULL COMMENT '版本',
  feature_id VARCHAR(16) NOT NULL COMMENT '特征',
  case_hit   INT         NOT NULL DEFAULT 0 COMMENT '案例组命中数',
  case_total INT         NOT NULL DEFAULT 0 COMMENT '案例组总数',
  ctrl_hit   INT         NOT NULL DEFAULT 0 COMMENT '对照组命中数',
  ctrl_total INT         NOT NULL DEFAULT 0 COMMENT '对照组总数',
  p1         DECIMAL(6,4) GENERATED ALWAYS AS
             (IF(case_total > 0, ROUND(case_hit / case_total, 4), 0)) STORED
             COMMENT '案例组出现率：生成列，改命中数自动重算',
  p0         DECIMAL(6,4) GENERATED ALWAYS AS
             (IF(ctrl_total > 0, ROUND(ctrl_hit / ctrl_total, 4), 0)) STORED
             COMMENT '对照组出现率：生成列',
  lift       DECIMAL(8,4) GENERATED ALWAYS AS
             (IF(p0 > 0, ROUND(p1 / p0, 4), NULL)) STORED
             COMMENT '提升度 = p1/p0：生成列',
  weight     DECIMAL(6,4) NOT NULL COMMENT '对数几率权重（-3~3，含 +0.5 平滑），由 sp_calc_feature_weight 写入',
  is_valid   TINYINT     NOT NULL DEFAULT 1 COMMENT '1参与研判 0样本不足',
  calc_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间',
  PRIMARY KEY (weight_id),
  UNIQUE KEY uk_weight (version_id, feature_id),
  KEY idx_weight_feature (feature_id),
  CONSTRAINT ck_weight_hit1 CHECK (case_hit <= case_total),
  CONSTRAINT ck_weight_hit0 CHECK (ctrl_hit <= ctrl_total),
  CONSTRAINT ck_weight CHECK (weight BETWEEN -3 AND 3),
  CONSTRAINT ck_weight_valid CHECK (is_valid IN (0,1)),
  CONSTRAINT fk_weight_version FOREIGN KEY (version_id) REFERENCES feature_version (version_id),
  CONSTRAINT fk_weight_feature FOREIGN KEY (feature_id) REFERENCES feature_def (feature_id)
) ENGINE=InnoDB COMMENT='特征权重表：p1/p0/lift 为生成列，weight 由存储过程计算';

CREATE TABLE judge_rule (
  rule_id        VARCHAR(16)  NOT NULL COMMENT '规则编号',
  rule_name      VARCHAR(80)  NOT NULL COMMENT '规则名称',
  risk_type      TINYINT      NOT NULL DEFAULT 1 COMMENT '风险类型：1酒驾',
  version_id     VARCHAR(20)  NOT NULL COMMENT '权重版本',
  judge_object   TINYINT      NOT NULL DEFAULT 1 COMMENT '1区域时段 2个人',
  min_sample     INT          NOT NULL DEFAULT 20 COMMENT '样本量下限',
  min_hit_cnt    INT          NOT NULL DEFAULT 2 COMMENT '最少命中特征数',
  low_threshold  DECIMAL(6,2) NOT NULL DEFAULT 3.00 COMMENT '低/中分界',
  high_threshold DECIMAL(6,2) NOT NULL DEFAULT 6.00 COMMENT '中/高分界',
  counter_block  TINYINT      NOT NULL DEFAULT 1 COMMENT '1反例命中不生成线索',
  status         TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  remark         VARCHAR(255)          COMMENT '说明',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (rule_id),
  KEY idx_rule_object (judge_object, status),
  CONSTRAINT ck_rule_object CHECK (judge_object IN (1,2)),
  CONSTRAINT ck_rule_hit CHECK (min_hit_cnt >= 1),
  CONSTRAINT ck_rule_sample CHECK (min_sample >= 0),
  CONSTRAINT ck_rule_thr CHECK (high_threshold > low_threshold),
  CONSTRAINT ck_rule_status CHECK (status IN (0,1)),
  CONSTRAINT fk_rule_version FOREIGN KEY (version_id) REFERENCES feature_version (version_id)
) ENGINE=InnoDB COMMENT='研判规则表';

CREATE TABLE rule_feature (
  rule_id     VARCHAR(16) NOT NULL COMMENT '规则',
  feature_id  VARCHAR(16) NOT NULL COMMENT '特征',
  is_required TINYINT     NOT NULL DEFAULT 0 COMMENT '1强特征',
  sort_no     INT         NOT NULL DEFAULT 0 COMMENT '展示顺序',
  PRIMARY KEY (rule_id, feature_id),
  KEY idx_rf_feature (feature_id),
  CONSTRAINT ck_rf_required CHECK (is_required IN (0,1)),
  CONSTRAINT fk_rf_rule FOREIGN KEY (rule_id) REFERENCES judge_rule (rule_id),
  CONSTRAINT fk_rf_feature FOREIGN KEY (feature_id) REFERENCES feature_def (feature_id)
) ENGINE=InnoDB COMMENT='规则特征关联表';

CREATE TABLE judge_batch (
  batch_id     VARCHAR(24) NOT NULL COMMENT '批次编号',
  rule_id      VARCHAR(16) NOT NULL COMMENT '规则',
  version_id   VARCHAR(20) NOT NULL COMMENT '权重版本',
  judge_object TINYINT     NOT NULL DEFAULT 1 COMMENT '1区域时段 2个人',
  data_start   DATETIME    NOT NULL COMMENT '数据窗起（必须在观察段）',
  data_end     DATETIME    NOT NULL COMMENT '数据窗止',
  area_id      VARCHAR(12)          COMMENT '限定区域（空=全部）',
  run_status   TINYINT     NOT NULL DEFAULT 0 COMMENT '0待执行 1执行中 2成功 3失败',
  run_no       INT         NOT NULL DEFAULT 0 COMMENT '执行次数',
  object_cnt   INT         NOT NULL DEFAULT 0 COMMENT '本批对象数',
  clue_cnt     INT         NOT NULL DEFAULT 0 COMMENT '本批线索数',
  duration_ms  INT                  COMMENT '耗时（毫秒）',
  operator_id  VARCHAR(20)          COMMENT '操作人',
  created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (batch_id),
  KEY idx_batch_status (run_status, created_at),
  KEY idx_batch_area (area_id, data_start),
  CONSTRAINT ck_batch_window CHECK (data_end > data_start),
  CONSTRAINT ck_batch_status CHECK (run_status BETWEEN 0 AND 3),
  CONSTRAINT ck_batch_object CHECK (judge_object IN (1,2)),
  -- 成功的批次必须记了耗时，否则性能实验取不到数
  CONSTRAINT ck_batch_duration CHECK (run_status <> 2 OR duration_ms IS NOT NULL),
  CONSTRAINT ck_batch_count CHECK (object_cnt >= 0 AND clue_cnt >= 0),
  CONSTRAINT fk_batch_rule FOREIGN KEY (rule_id) REFERENCES judge_rule (rule_id),
  CONSTRAINT fk_batch_version FOREIGN KEY (version_id) REFERENCES feature_version (version_id),
  CONSTRAINT fk_batch_area FOREIGN KEY (area_id) REFERENCES area_info (area_id),
  CONSTRAINT fk_batch_operator FOREIGN KEY (operator_id) REFERENCES sys_user (user_id)
) ENGINE=InnoDB COMMENT='研判批次表';

CREATE TABLE risk_score (
  score_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '流水号',
  batch_id     VARCHAR(24)  NOT NULL COMMENT '批次',
  rule_id      VARCHAR(16)  NOT NULL COMMENT '规则快照',
  version_id   VARCHAR(20)  NOT NULL COMMENT '权重版本快照',
  object_type  TINYINT      NOT NULL COMMENT '1区域时段 2个人',
  area_id      VARCHAR(12)           COMMENT '区域（个人对象可空）',
  day_type     TINYINT               COMMENT '1工作日 2周末',
  hour_slot    TINYINT               COMMENT '时段 0-23',
  person_id    VARCHAR(16)           COMMENT '个人对象的人员编号',
  object_id    VARCHAR(64)  GENERATED ALWAYS AS (
                 CASE WHEN object_type = 1
                      THEN CONCAT(area_id, '#', day_type, '#', LPAD(hour_slot, 2, '0'))
                      ELSE person_id END) STORED
                             COMMENT '对象标识：生成列，不可能与 area/day/hour/person 不一致',
  sample_size  INT          NOT NULL DEFAULT 0 COMMENT '归集记录数',
  total_score  DECIMAL(8,2) NOT NULL DEFAULT 0 COMMENT '总分 = 命中特征权重之和',
  risk_level   TINYINT      NOT NULL DEFAULT 1 COMMENT '1低 2中 3高',
  is_clue      TINYINT      NOT NULL DEFAULT 0 COMMENT '1已生成线索',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
  PRIMARY KEY (score_id),
  UNIQUE KEY uk_batch_object (batch_id, object_type, object_id),
  KEY idx_score_level (batch_id, risk_level),
  KEY idx_score_area (area_id, hour_slot),
  KEY idx_score_person (person_id),
  CONSTRAINT ck_score_object CHECK (object_type IN (1,2)),
  CONSTRAINT ck_score_level CHECK (risk_level IN (1,2,3)),
  CONSTRAINT ck_score_clue CHECK (is_clue IN (0,1)),
  CONSTRAINT ck_score_daytype CHECK (day_type IS NULL OR day_type IN (1,2)),
  CONSTRAINT ck_score_hour CHECK (hour_slot IS NULL OR hour_slot BETWEEN 0 AND 23),
  -- 区域时段对象必须有区域/日期类型/小时；个人对象必须有人
  CONSTRAINT ck_score_region_fields CHECK (
    object_type = 2 OR (area_id IS NOT NULL AND day_type IS NOT NULL AND hour_slot IS NOT NULL)),
  CONSTRAINT ck_score_person_field CHECK (object_type = 1 OR person_id IS NOT NULL),
  CONSTRAINT fk_score_batch FOREIGN KEY (batch_id) REFERENCES judge_batch (batch_id),
  CONSTRAINT fk_score_area FOREIGN KEY (area_id) REFERENCES area_info (area_id),
  CONSTRAINT fk_score_person FOREIGN KEY (person_id) REFERENCES person_info (person_id),
  CONSTRAINT fk_score_rule FOREIGN KEY (rule_id) REFERENCES judge_rule (rule_id),
  CONSTRAINT fk_score_version FOREIGN KEY (version_id) REFERENCES feature_version (version_id)
) ENGINE=InnoDB COMMENT='评分表：object_id 为生成列；命中明细在 risk_score_feature';

CREATE TABLE risk_score_feature (
  score_id   BIGINT      NOT NULL COMMENT '评分',
  feature_id VARCHAR(16) NOT NULL COMMENT '特征',
  is_hit     TINYINT     NOT NULL COMMENT '1命中 0未命中',
  weight     DECIMAL(6,4) NOT NULL COMMENT '评分时该特征的权重快照（权重日后变化不影响历史）',
  hit_value  DECIMAL(10,2)         COMMENT '命中值：布尔型=1/0，数值型=实际计数',
  is_missing TINYINT     NOT NULL DEFAULT 0 COMMENT '1数据缺失（既非命中也不是干净的未命中）',
  PRIMARY KEY (score_id, feature_id),
  KEY idx_ssf_feature (feature_id),
  CONSTRAINT ck_ssf_hit CHECK (is_hit IN (0,1)),
  CONSTRAINT ck_ssf_missing CHECK (is_missing IN (0,1)),
  CONSTRAINT ck_ssf_weight CHECK (weight BETWEEN -3 AND 3),
  CONSTRAINT fk_ssf_score FOREIGN KEY (score_id) REFERENCES risk_score (score_id)
      ON DELETE CASCADE,
  CONSTRAINT fk_ssf_feature FOREIGN KEY (feature_id) REFERENCES feature_def (feature_id)
) ENGINE=InnoDB COMMENT='评分命中明细表：解决 hit_features 存字符串的 1NF 问题';

CREATE TABLE risk_clue (
  clue_id     VARCHAR(24) NOT NULL COMMENT '线索编号',
  batch_id    VARCHAR(24) NOT NULL COMMENT '来源批次',
  score_id    BIGINT      NOT NULL COMMENT '来源评分（1:1，线索的全部事实都在评分与明细里）',
  version_id  VARCHAR(20) NOT NULL COMMENT '权重版本',
  clue_status TINYINT     NOT NULL DEFAULT 0 COMMENT '0待核查 1核查中 2已确认 3已排除',
  assignee_id VARCHAR(20)          COMMENT '承办人',
  create_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
  close_at    DATETIME             COMMENT '关闭时间',
  PRIMARY KEY (clue_id),
  UNIQUE KEY uk_clue_score (score_id),
  KEY idx_clue_status (clue_status, create_at),
  KEY idx_clue_assignee (assignee_id, clue_status),
  KEY idx_clue_batch (batch_id),
  CONSTRAINT ck_clue_status CHECK (clue_status BETWEEN 0 AND 3),
  -- 已确认/已排除必须有关闭时间；未关闭的不许有
  CONSTRAINT ck_clue_close CHECK ((clue_status IN (2,3)) = (close_at IS NOT NULL)),
  CONSTRAINT fk_clue_batch FOREIGN KEY (batch_id) REFERENCES judge_batch (batch_id),
  CONSTRAINT fk_clue_score FOREIGN KEY (score_id) REFERENCES risk_score (score_id),
  CONSTRAINT fk_clue_version FOREIGN KEY (version_id) REFERENCES feature_version (version_id),
  CONSTRAINT fk_clue_assignee FOREIGN KEY (assignee_id) REFERENCES sys_user (user_id)
) ENGINE=InnoDB COMMENT='风险线索表：只存状态机，事实通过 score_id 追溯到评分与明细';

CREATE TABLE clue_feedback (
  feedback_id    BIGINT       NOT NULL AUTO_INCREMENT COMMENT '流水号',
  clue_id        VARCHAR(24)  NOT NULL COMMENT '线索',
  check_result   TINYINT      NOT NULL COMMENT '1属实 2不属实 3无法核实',
  check_method   TINYINT      NOT NULL DEFAULT 1 COMMENT '1电话 2现场 3数据复核',
  check_remark   VARCHAR(500)          COMMENT '结论说明',
  checker_id     VARCHAR(20)  NOT NULL COMMENT '核查人',
  check_time     DATETIME     NOT NULL COMMENT '核查时间',
  weight_applied TINYINT      NOT NULL DEFAULT 0 COMMENT '1已纳入下轮权重',
  PRIMARY KEY (feedback_id),
  KEY idx_fb_clue (clue_id),
  KEY idx_fb_time (check_time),
  CONSTRAINT ck_fb_result CHECK (check_result IN (1,2,3)),
  CONSTRAINT ck_fb_method CHECK (check_method IN (1,2,3)),
  CONSTRAINT ck_fb_applied CHECK (weight_applied IN (0,1)),
  CONSTRAINT fk_fb_clue FOREIGN KEY (clue_id) REFERENCES risk_clue (clue_id),
  CONSTRAINT fk_fb_checker FOREIGN KEY (checker_id) REFERENCES sys_user (user_id)
) ENGINE=InnoDB COMMENT='核查反馈表：插入后由触发器自动改线索状态';

CREATE TABLE clue_feedback_feature (
  feedback_id BIGINT      NOT NULL COMMENT '反馈',
  feature_id  VARCHAR(16) NOT NULL COMMENT '被否定的特征',
  is_wrong    TINYINT     NOT NULL DEFAULT 1 COMMENT '1该特征被证伪',
  PRIMARY KEY (feedback_id, feature_id),
  KEY idx_cff_feature (feature_id),
  CONSTRAINT ck_cff_wrong CHECK (is_wrong IN (0,1)),
  CONSTRAINT fk_cff_fb FOREIGN KEY (feedback_id) REFERENCES clue_feedback (feedback_id)
      ON DELETE CASCADE,
  CONSTRAINT fk_cff_feature FOREIGN KEY (feature_id) REFERENCES feature_def (feature_id)
) ENGINE=InnoDB COMMENT='反馈特征明细表：闭环回写时定位到具体特征';

CREATE TABLE eval_label (
  label_id    BIGINT      NOT NULL AUTO_INCREMENT COMMENT '流水号',
  object_type TINYINT     NOT NULL COMMENT '1区域时段 2个人',
  object_id   VARCHAR(64) NOT NULL COMMENT '与 risk_score.object_id 同格式',
  sample_type TINYINT     NOT NULL COMMENT '1正样本 2干扰样本 3对照样本',
  label       TINYINT     NOT NULL COMMENT '1该对象确有酒驾 0无',
  case_cnt    INT         NOT NULL DEFAULT 0 COMMENT '该对象内真实案件数',
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '埋案时间',
  PRIMARY KEY (label_id),
  UNIQUE KEY uk_eval (object_type, object_id),
  KEY idx_eval_type (sample_type),
  CONSTRAINT ck_eval_type CHECK (sample_type IN (1,2,3)),
  CONSTRAINT ck_eval_label CHECK (label IN (0,1)),
  CONSTRAINT ck_eval_object CHECK (object_type IN (1,2))
) ENGINE=InnoDB COMMENT='评估标签表：观察段埋案，仅评估用，研判员无权限';

CREATE OR REPLACE VIEW v_case_history AS
SELECT c.case_id, c.occur_time, c.area_id, c.place_id, c.person_id, c.vehicle_id,
       c.case_type, c.alcohol_value, c.distance_home, c.driver_confirmed, c.dispose_status
FROM case_info c
JOIN param_config p ON p.param_key = 'history_cutoff'
WHERE c.occur_time < CAST(p.param_value AS DATETIME);

-- =============================================================================
--  三、视图、触发器与存储过程（先建，数据插入时即可触发）
-- =============================================================================

CREATE OR REPLACE VIEW v_region_risk AS
SELECT s.batch_id,
       s.area_id,
       a.area_name,
       CASE s.day_type WHEN 1 THEN '工作日' ELSE '周末' END AS day_type_name,
       s.hour_slot,
       s.sample_size,
       (SELECT COUNT(*) FROM risk_score_feature x
         WHERE x.score_id = s.score_id AND x.is_hit = 1) AS hit_cnt,
       s.total_score,
       CASE s.risk_level WHEN 1 THEN '低' WHEN 2 THEN '中' ELSE '高' END AS risk_level_name,
       (SELECT GROUP_CONCAT(CONCAT(x.feature_id, ':', IF(x.weight > 0, '+', ''), x.weight)
                            ORDER BY x.feature_id SEPARATOR ';')
          FROM risk_score_feature x
         WHERE x.score_id = s.score_id AND x.is_hit = 1) AS hit_features,
       s.is_clue
FROM risk_score s
LEFT JOIN area_info a ON a.area_id = s.area_id
WHERE s.object_type = 1;

CREATE OR REPLACE VIEW v_clue_list AS
SELECT c.clue_id,
       s.area_id,
       a.area_name,
       s.hour_slot,
       CASE s.risk_level WHEN 1 THEN '低' WHEN 2 THEN '中' ELSE '高' END AS risk_level_name,
       s.total_score,
       (SELECT GROUP_CONCAT(CONCAT(x.feature_id, ':', IF(x.weight > 0, '+', ''), x.weight)
                            ORDER BY x.feature_id SEPARATOR ';')
          FROM risk_score_feature x
         WHERE x.score_id = s.score_id AND x.is_hit = 1) AS hit_features,
       CASE c.clue_status WHEN 0 THEN '待核查' WHEN 1 THEN '核查中'
                          WHEN 2 THEN '已确认' ELSE '已排除' END AS status_name,
       u.real_name AS assignee_name,
       c.create_at,
       c.close_at
FROM risk_clue c
JOIN risk_score s     ON s.score_id = c.score_id
LEFT JOIN area_info a ON a.area_id = s.area_id
LEFT JOIN sys_user u  ON u.user_id = c.assignee_id;

DELIMITER $$

-- 1) 线索状态变更自动留痕（取会话变量，取不到记 system）
CREATE TRIGGER trg_clue_audit
AFTER UPDATE ON risk_clue
FOR EACH ROW
BEGIN
  DECLARE v_user VARCHAR(20);
  SELECT u.user_id INTO v_user FROM sys_user u WHERE u.user_id = @app_user_id;
  IF OLD.clue_status <> NEW.clue_status THEN
    INSERT INTO audit_log (user_id, operator_tag, op_type, table_name, record_pk, op_desc)
    VALUES (v_user, IFNULL(@app_user_id,'system'), 4, 'risk_clue', NEW.clue_id,
            CONCAT('线索状态变更：', OLD.clue_status, ' → ', NEW.clue_status));
  END IF;
END$$

-- 2) 权重变更自动留痕
CREATE TRIGGER trg_weight_audit
AFTER UPDATE ON feature_weight
FOR EACH ROW
BEGIN
  IF OLD.weight <> NEW.weight THEN
    INSERT INTO audit_log (user_id, operator_tag, op_type, table_name, record_pk, op_desc)
    VALUES ((SELECT u.user_id FROM sys_user u WHERE u.user_id = @app_user_id),
            IFNULL(@app_user_id,'system'), 4, 'feature_weight',
            CONCAT(NEW.version_id,'/',NEW.feature_id),
            CONCAT('权重变更：', OLD.weight, ' → ', NEW.weight));
  END IF;
END$$

-- 3) 核查反馈插入后，自动把线索状态推进到已确认/已排除，并写关闭时间
CREATE TRIGGER trg_feedback_close_clue
AFTER INSERT ON clue_feedback
FOR EACH ROW
BEGIN
  IF NEW.check_result IN (1,2) THEN
    UPDATE risk_clue
       SET clue_status = IF(NEW.check_result = 1, 2, 3),
           close_at    = NEW.check_time
     WHERE clue_id = NEW.clue_id;
  END IF;
END$$

-- 4) 权重计算：只写 weight，p1/p0/lift 由生成列自动维护
CREATE PROCEDURE sp_calc_feature_weight(IN p_version_id VARCHAR(20))
BEGIN
  UPDATE feature_weight
     SET weight = CASE WHEN is_valid = 0 THEN 0 ELSE
           LEAST(3, GREATEST(-3, ROUND(
             LN( ((case_hit + 0.5) / (case_total - case_hit + 0.5))
               / ((ctrl_hit + 0.5) / (ctrl_total - ctrl_hit + 0.5)) ), 4)))
         END,
         calc_at = NOW()
   WHERE version_id = p_version_id;

  UPDATE feature_version
     SET based_case_cnt = (SELECT IFNULL(MAX(case_total),0) FROM feature_weight WHERE version_id = p_version_id),
         based_ctrl_cnt = (SELECT IFNULL(MAX(ctrl_total),0) FROM feature_weight WHERE version_id = p_version_id),
         calc_at = NOW()
   WHERE version_id = p_version_id;
END$$

-- 5) 批次重跑：按对象 upsert，已核查（已确认/已排除）的对象一律跳过
DROP PROCEDURE IF EXISTS sp_upsert_score$$
CREATE PROCEDURE sp_upsert_score(
  IN p_score_id BIGINT, IN p_batch_id VARCHAR(24), IN p_rule_id VARCHAR(16),
  IN p_version_id VARCHAR(20), IN p_object_type TINYINT,
  IN p_area_id VARCHAR(12), IN p_day_type TINYINT, IN p_hour_slot TINYINT,
  IN p_person_id VARCHAR(16), IN p_sample_size INT,
  IN p_total_score DECIMAL(8,2), IN p_risk_level TINYINT, IN p_is_clue TINYINT)
BEGIN
  DECLARE v_checked TINYINT DEFAULT 0;

  -- 该对象若已有线索且已核查，则不覆盖
  SELECT COUNT(*) INTO v_checked
    FROM risk_clue c JOIN risk_score s ON s.score_id = c.score_id
   WHERE s.batch_id = p_batch_id AND s.object_type = p_object_type
     AND s.object_id = CASE WHEN p_object_type = 1
            THEN CONCAT(p_area_id,'#',p_day_type,'#',LPAD(p_hour_slot,2,'0'))
            ELSE p_person_id END
     AND c.clue_status IN (2,3);

  IF v_checked = 0 THEN
    INSERT INTO risk_score
      (score_id, batch_id, rule_id, version_id, object_type, area_id, day_type, hour_slot,
       person_id, sample_size, total_score, risk_level, is_clue)
    VALUES
      (p_score_id, p_batch_id, p_rule_id, p_version_id, p_object_type, p_area_id, p_day_type,
       p_hour_slot, p_person_id, p_sample_size, p_total_score, p_risk_level, p_is_clue)
    ON DUPLICATE KEY UPDATE
      total_score = VALUES(total_score), risk_level = VALUES(risk_level),
      sample_size = VALUES(sample_size), is_clue = VALUES(is_clue);
  END IF;
END$$

DELIMITER ;
