ALTER TABLE consume_record ADD CONSTRAINT ck_consume_recorded CHECK(recorded_at>=consume_time), ADD CONSTRAINT ck_consume_active CHECK(is_active IN (0,1));
ALTER TABLE taxi_order ADD CONSTRAINT ck_order_state_time CHECK((order_status=1 AND completed_at IS NOT NULL) OR (order_status IN (2,3) AND completed_at IS NULL)), ADD CONSTRAINT ck_order_recorded CHECK(recorded_at>=COALESCE(completed_at,order_time)), ADD CONSTRAINT ck_order_active CHECK(is_active IN (0,1));
ALTER TABLE vehicle_track ADD CONSTRAINT ck_track_recorded CHECK(recorded_at>=pass_time), ADD CONSTRAINT ck_track_active CHECK(is_active IN (0,1));
ALTER TABLE driver_evidence ADD CONSTRAINT ck_driver_recorded CHECK(recorded_at>=observed_at);
ALTER TABLE risk_score ADD CONSTRAINT ck_score_coverage CHECK(data_coverage BETWEEN 0 AND 1), ADD CONSTRAINT ck_score_blocked CHECK(blocked IN (0,1));
