USE risk_alert;

SELECT '-- 1. 各表行数 --' AS x;
SELECT 'sys_role' t, COUNT(*) n FROM sys_role UNION ALL
SELECT 'sys_user', COUNT(*) FROM sys_user UNION ALL
SELECT 'sys_user_role', COUNT(*) FROM sys_user_role UNION ALL
SELECT 'param_config', COUNT(*) FROM param_config UNION ALL
SELECT 'area_info', COUNT(*) FROM area_info UNION ALL
SELECT 'place_info', COUNT(*) FROM place_info UNION ALL
SELECT 'person_info', COUNT(*) FROM person_info UNION ALL
SELECT 'vehicle_owner', COUNT(*) FROM vehicle_owner UNION ALL
SELECT 'case_info', COUNT(*) FROM case_info UNION ALL
SELECT 'control_person', COUNT(*) FROM control_person UNION ALL
SELECT 'consume_record', COUNT(*) FROM consume_record UNION ALL
SELECT 'taxi_order', COUNT(*) FROM taxi_order UNION ALL
SELECT 'vehicle_track', COUNT(*) FROM vehicle_track UNION ALL
SELECT 'feature_def', COUNT(*) FROM feature_def UNION ALL
SELECT 'feature_version', COUNT(*) FROM feature_version UNION ALL
SELECT 'feature_weight', COUNT(*) FROM feature_weight UNION ALL
SELECT 'judge_rule', COUNT(*) FROM judge_rule UNION ALL
SELECT 'rule_feature', COUNT(*) FROM rule_feature UNION ALL
SELECT 'judge_batch', COUNT(*) FROM judge_batch UNION ALL
SELECT 'risk_score', COUNT(*) FROM risk_score UNION ALL
SELECT 'risk_score_feature', COUNT(*) FROM risk_score_feature UNION ALL
SELECT 'risk_clue', COUNT(*) FROM risk_clue UNION ALL
SELECT 'clue_feedback', COUNT(*) FROM clue_feedback UNION ALL
SELECT 'clue_feedback_feature', COUNT(*) FROM clue_feedback_feature UNION ALL
SELECT 'eval_label', COUNT(*) FROM eval_label UNION ALL
SELECT 'audit_log', COUNT(*) FROM audit_log;

SELECT '-- 2. 关键约束/一致性检查（全部应 0）--' AS x;
SELECT (SELECT COUNT(*) FROM feature_def WHERE match_src='case_info') AS bad_match_src,
       (SELECT COUNT(*) FROM case_info WHERE occur_time >= (SELECT CAST(param_value AS DATETIME)
            FROM param_config WHERE param_key='history_cutoff')) AS case_after_cutoff,
       (SELECT COUNT(*) FROM consume_record c LEFT JOIN person_info p USING(person_id)
            WHERE p.person_id IS NULL) AS orphan_person,
       (SELECT COUNT(*) FROM consume_record c LEFT JOIN place_info pl USING(place_id)
            LEFT JOIN area_info a ON a.area_id=pl.area_id WHERE a.area_id IS NULL) AS orphan_place,
       (SELECT COUNT(*) FROM judge_batch b WHERE b.object_cnt <>
            (SELECT COUNT(*) FROM risk_score s WHERE s.batch_id=b.batch_id)) AS batch_cnt_bad;

SELECT '-- 3. 总分与命中明细复算不一致（应 0）--' AS x;
SELECT COUNT(*) AS mismatch FROM (
  SELECT s.score_id, s.total_score,
         (SELECT ROUND(SUM(x.weight),2) FROM risk_score_feature x
           WHERE x.score_id=s.score_id AND x.is_hit=1) calc
  FROM risk_score s) t WHERE ABS(total_score - IFNULL(calc,0)) > 0.005;

SELECT '-- 4. 权重可由四个命中数复算（应 0）--' AS x;
SELECT COUNT(*) AS bad FROM feature_weight w
 WHERE ABS(w.weight - ROUND(LN(((w.case_hit+0.475)/(w.case_total-w.case_hit+0.475))
      / ((w.ctrl_hit+0.475)/(w.ctrl_total-w.ctrl_hit+0.475))),4)) > 0.02;

SELECT '-- 5. 混淆矩阵与精确率 --' AS x;
SELECT SUM(l.label=1 AND IFNULL(s.is_clue,0)=1) TP, SUM(l.label=0 AND IFNULL(s.is_clue,0)=1) FP,
       SUM(l.label=1 AND IFNULL(s.is_clue,0)=0) FN, SUM(l.label=0 AND IFNULL(s.is_clue,0)=0) TN,
       ROUND(SUM(l.label=1 AND IFNULL(s.is_clue,0)=1)/SUM(IFNULL(s.is_clue,0)=1),3) prec,
       ROUND(SUM(l.label=1 AND IFNULL(s.is_clue,0)=1)/SUM(l.label=1),3) rec,
       ROUND(SUM(l.label=0 AND IFNULL(s.is_clue,0)=1)/SUM(l.label=0),3) fpr
FROM eval_label l LEFT JOIN risk_score s
  ON s.object_type=l.object_type AND s.object_id=l.object_id;

SELECT '-- 6. 线索与评分 1:1、状态机闭环 --' AS x;
SELECT (SELECT COUNT(*) FROM risk_clue) clues,
       (SELECT COUNT(*) FROM risk_score WHERE is_clue=1) score_is_clue,
       (SELECT COUNT(DISTINCT score_id) FROM risk_clue) distinct_score,
       (SELECT COUNT(*) FROM risk_clue WHERE clue_status IN (2,3) AND close_at IS NULL) closed_no_time;

SELECT '-- 7. 触发器留痕（核查反馈 → 状态推进 + 审计）--' AS x;
SELECT (SELECT COUNT(*) FROM audit_log WHERE table_name='risk_clue' AND op_type=4) clue_audit,
       (SELECT COUNT(*) FROM clue_feedback) feedbacks,
       (SELECT COUNT(*) FROM risk_clue WHERE clue_status IN (2,3)) closed_clues;

SELECT '-- 8. 两批数据的时间覆盖 --' AS x;
SELECT 'case 07~08' k, COUNT(*) n, MIN(occur_time) mn, MAX(occur_time) mx FROM case_info WHERE occur_time < '2026-09-01'
UNION ALL SELECT 'case 09~10', COUNT(*), MIN(occur_time), MAX(occur_time) FROM case_info WHERE occur_time >= '2026-09-01'
UNION ALL SELECT 'consume 07~08', COUNT(*), MIN(consume_time), MAX(consume_time) FROM consume_record WHERE consume_time < '2026-09-01'
UNION ALL SELECT 'consume 09~11', COUNT(*), MIN(consume_time), MAX(consume_time) FROM consume_record WHERE consume_time >= '2026-09-01' AND consume_time < '2026-12-01'
UNION ALL SELECT 'consume 12', COUNT(*), MIN(consume_time), MAX(consume_time) FROM consume_record WHERE consume_time >= '2026-12-01';

SELECT '-- 9. 评分/线索按批次归属 --' AS x;
SELECT CASE WHEN batch_id < 'B20261201' THEN '第一批' ELSE '第二批' END grp,
       COUNT(*) scores, SUM(is_clue) clues, ROUND(AVG(total_score),2) avg_score,
       MIN(total_score) mn, MAX(total_score) mx
FROM risk_score GROUP BY grp;

SELECT '-- 10. 视图可用 --' AS x;
SELECT (SELECT COUNT(*) FROM v_region_risk) region_rows,
       (SELECT COUNT(*) FROM v_clue_list) clue_rows;

SELECT '-- 11. 存储过程幂等 --' AS x;
CREATE TEMPORARY TABLE w_before AS SELECT version_id, feature_id, weight FROM feature_weight;
CALL sp_calc_feature_weight('V20261001_01');
SELECT COUNT(*) AS weight_changed FROM w_before b
  JOIN feature_weight w USING(version_id, feature_id) WHERE b.weight <> w.weight;

SELECT '-- 12. 演示对象仍在 --' AS x;
SELECT score_id, object_id, total_score, risk_level, is_clue FROM risk_score WHERE object_id='A02#2#23';
SELECT clue_id, clue_status, close_at FROM risk_clue WHERE clue_id LIKE 'CL202611070%' ORDER BY clue_id;
