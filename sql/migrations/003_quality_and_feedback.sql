CREATE TABLE data_quality_report (
 report_id BIGINT AUTO_INCREMENT PRIMARY KEY,
 source_name VARCHAR(120) NOT NULL,
 report_json JSON NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE version_feedback (
 version_id VARCHAR(20) NOT NULL,
 feedback_id BIGINT NOT NULL,
 PRIMARY KEY(version_id,feedback_id),
 FOREIGN KEY(version_id) REFERENCES feature_version(version_id),
 FOREIGN KEY(feedback_id) REFERENCES clue_feedback(feedback_id)
) ENGINE=InnoDB;
