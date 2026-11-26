ALTER TABLE sys_user MODIFY password_hash VARCHAR(255) NOT NULL;
ALTER TABLE consume_record ADD recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, ADD is_active TINYINT NOT NULL DEFAULT 1;
ALTER TABLE taxi_order ADD completed_at DATETIME NULL, ADD recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, ADD is_active TINYINT NOT NULL DEFAULT 1, ADD CONSTRAINT ck_order_complete CHECK (completed_at IS NULL OR completed_at >= order_time);
ALTER TABLE vehicle_track ADD recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, ADD is_active TINYINT NOT NULL DEFAULT 1;
ALTER TABLE case_info ADD is_active TINYINT NOT NULL DEFAULT 1;
ALTER TABLE person_info ADD is_active TINYINT NOT NULL DEFAULT 1;
ALTER TABLE feature_version ADD algorithm_version VARCHAR(40) NOT NULL DEFAULT 'continuous-v1', ADD baseline_json JSON NULL;
ALTER TABLE judge_rule ADD config_json JSON NULL;
ALTER TABLE judge_batch ADD started_at DATETIME NULL, ADD error_message VARCHAR(500) NULL;
ALTER TABLE risk_score ADD window_start DATETIME NOT NULL DEFAULT '2026-11-01 00:00:00', ADD window_end DATETIME NOT NULL DEFAULT '2026-11-01 01:00:00', ADD algorithm_version VARCHAR(40) NOT NULL DEFAULT 'continuous-v1', ADD data_coverage DECIMAL(5,4) NOT NULL DEFAULT 1, ADD blocked TINYINT NOT NULL DEFAULT 0, ADD episode_key VARCHAR(64) NULL, MODIFY total_score DECIMAL(8,2) NULL, MODIFY risk_level TINYINT NULL;
ALTER TABLE risk_score DROP INDEX uk_batch_object, DROP COLUMN object_id;
ALTER TABLE risk_score ADD object_id VARCHAR(64) GENERATED ALWAYS AS (CASE WHEN object_type=1 THEN CONCAT(area_id,'#',YEAR(window_start),LPAD(MONTH(window_start),2,'0'),LPAD(DAY(window_start),2,'0'),LPAD(HOUR(window_start),2,'0')) ELSE person_id END) STORED, ADD UNIQUE KEY uk_batch_object(batch_id,object_type,object_id,window_start), ADD KEY idx_score_window(object_type,window_start,area_id), ADD CONSTRAINT ck_score_index CHECK (total_score IS NULL OR total_score BETWEEN 0 AND 100), ADD CONSTRAINT ck_score_window CHECK (window_end > window_start);
ALTER TABLE risk_score_feature ADD raw_value DECIMAL(14,4) NULL, ADD normalized_value DECIMAL(8,5) NULL, ADD contribution DECIMAL(8,4) NOT NULL DEFAULT 0, ADD evidence_json JSON NULL;
ALTER TABLE eval_label DROP INDEX uk_eval, ADD window_start DATETIME NOT NULL, ADD window_end DATETIME NOT NULL, ADD UNIQUE KEY uk_eval(object_type,object_id,window_start), ADD CONSTRAINT ck_eval_window CHECK (window_end > window_start);
CREATE TABLE app_session (
 token_hash CHAR(64) PRIMARY KEY,
 user_id VARCHAR(20) NOT NULL,
 expires_at DATETIME NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (user_id) REFERENCES sys_user(user_id),
 KEY idx_session_expiry(expires_at)
) ENGINE=InnoDB;
CREATE TABLE ingest_window (
 ingest_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 source_type VARCHAR(20) NOT NULL,
 window_start DATETIME NOT NULL,
 window_end DATETIME NOT NULL,
 available_at DATETIME NOT NULL,
 coverage DECIMAL(5,4) NOT NULL DEFAULT 1,
 CHECK (source_type IN ('consume','order','track')),
 CHECK (window_end>window_start), CHECK (coverage BETWEEN 0 AND 1),
 KEY idx_ingest_window(source_type,window_start,window_end)
) ENGINE=InnoDB;
CREATE TABLE driver_evidence (
 evidence_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 track_id BIGINT NOT NULL UNIQUE,
 person_id VARCHAR(16) NOT NULL,
 source_type VARCHAR(40) NOT NULL,
 observed_at DATETIME NOT NULL,
 recorded_at DATETIME NOT NULL,
 FOREIGN KEY (track_id) REFERENCES vehicle_track(track_id),
 FOREIGN KEY (person_id) REFERENCES person_info(person_id),
 CHECK (source_type IN ('manual_verification','synthetic_observation'))
) ENGINE=InnoDB;
CREATE TABLE clue_chain (
 chain_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 clue_id VARCHAR(24) NOT NULL,
 person_id VARCHAR(16) NULL,
 episode_key VARCHAR(64) NOT NULL,
 algorithm_version VARCHAR(40) NOT NULL,
 snapshot_at DATETIME NOT NULL,
 FOREIGN KEY (clue_id) REFERENCES risk_clue(clue_id),
 FOREIGN KEY (person_id) REFERENCES person_info(person_id),
 UNIQUE KEY uk_chain_episode(clue_id,episode_key)
) ENGINE=InnoDB;
CREATE TABLE chain_node (
 node_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 chain_id BIGINT NOT NULL,
 node_type VARCHAR(30) NOT NULL,
 event_at DATETIME NOT NULL,
 title VARCHAR(120) NOT NULL,
 explanation VARCHAR(500) NOT NULL,
 certainty VARCHAR(20) NOT NULL,
 consume_id BIGINT NULL,
 order_id BIGINT NULL,
 track_id BIGINT NULL,
 score_id BIGINT NULL,
 FOREIGN KEY (chain_id) REFERENCES clue_chain(chain_id) ON DELETE CASCADE,
 FOREIGN KEY (consume_id) REFERENCES consume_record(consume_id),
 FOREIGN KEY (order_id) REFERENCES taxi_order(order_id),
 FOREIGN KEY (track_id) REFERENCES vehicle_track(track_id),
 FOREIGN KEY (score_id) REFERENCES risk_score(score_id),
 CHECK (certainty IN ('record','association','confirmed','counterexample','missing')),
 KEY idx_node_time(chain_id,event_at)
) ENGINE=InnoDB;
CREATE TABLE chain_edge (
 edge_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 from_node BIGINT NOT NULL,
 to_node BIGINT NOT NULL,
 relation_type VARCHAR(40) NOT NULL,
 reason VARCHAR(255) NOT NULL,
 FOREIGN KEY (from_node) REFERENCES chain_node(node_id) ON DELETE CASCADE,
 FOREIGN KEY (to_node) REFERENCES chain_node(node_id) ON DELETE CASCADE,
 UNIQUE KEY uk_edge(from_node,to_node), CHECK(from_node<>to_node)
) ENGINE=InnoDB;
CREATE OR REPLACE VIEW v_case_history AS
SELECT c.* FROM case_info c JOIN param_config p ON p.param_key='history_cutoff'
WHERE c.occur_time < CAST(p.param_value AS DATETIME) AND c.is_active=1;
CREATE OR REPLACE VIEW v_region_risk AS
SELECT s.*,a.area_name,CASE s.day_type WHEN 1 THEN '工作日' ELSE '周末' END day_type_name,
CASE s.risk_level WHEN 1 THEN '低' WHEN 2 THEN '中' WHEN 3 THEN '高' ELSE '数据不足' END risk_level_name,
(SELECT COUNT(*) FROM risk_score_feature f WHERE f.score_id=s.score_id AND f.is_hit=1) hit_cnt,
(SELECT GROUP_CONCAT(CONCAT(f.feature_id,':',f.contribution) ORDER BY f.feature_id SEPARATOR ';') FROM risk_score_feature f WHERE f.score_id=s.score_id AND f.is_hit=1) hit_features
FROM risk_score s JOIN area_info a ON a.area_id=s.area_id WHERE s.object_type=1;
CREATE OR REPLACE VIEW v_clue_list AS
SELECT c.*,s.object_type,s.object_id,s.area_id,a.area_name,s.hour_slot,s.window_start,s.window_end,s.total_score,s.risk_level,
CASE s.risk_level WHEN 1 THEN '低' WHEN 2 THEN '中' ELSE '高' END risk_level_name,
CASE c.clue_status WHEN 0 THEN '待核查' WHEN 1 THEN '核查中' WHEN 2 THEN '已确认' ELSE '已排除' END status_name,
u.real_name assignee_name,
(SELECT GROUP_CONCAT(CONCAT(f.feature_id,':',f.contribution) ORDER BY f.feature_id SEPARATOR ';') FROM risk_score_feature f WHERE f.score_id=s.score_id AND f.is_hit=1) hit_features
FROM risk_clue c JOIN risk_score s ON s.score_id=c.score_id LEFT JOIN area_info a ON a.area_id=s.area_id LEFT JOIN sys_user u ON u.user_id=c.assignee_id;
DROP PROCEDURE IF EXISTS sp_upsert_score;
DELIMITER $$
CREATE PROCEDURE sp_finalize_score(IN p_score BIGINT)
BEGIN
 UPDATE risk_score s
 SET s.total_score=IF(s.total_score IS NULL,NULL,ROUND(LEAST(100,GREATEST(0,(SELECT COALESCE(SUM(f.contribution),0) FROM risk_score_feature f WHERE f.score_id=p_score))),2))
 WHERE s.score_id=p_score;
 UPDATE risk_score s JOIN judge_rule r ON r.rule_id=s.rule_id
 SET s.risk_level=IF(s.total_score IS NULL,NULL,CASE WHEN s.total_score<r.low_threshold THEN 1 WHEN s.total_score<r.high_threshold THEN 2 ELSE 3 END)
 WHERE s.score_id=p_score;
END$$
DELIMITER ;
