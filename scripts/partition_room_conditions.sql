-- Partition lots_roomcondition by month (PostgreSQL 12+).
--
-- RoomCondition is the one table that grows without bound: one row per
-- sensor reading per room. At 96 readings a day per room it passes a
-- million rows within a year of a three-plant sensor feed. Range
-- partitioning by recorded_at keeps the exposure aggregates in
-- forecast/features.py (which always filter on a room and a time window)
-- scanning one or two partitions instead of the whole table.
--
-- Run by hand, once, as the schema owner, inside a maintenance window and
-- AFTER `manage.py migrate` is current. Django does not manage partitions;
-- future migrations that alter this table's columns still work because
-- partitioned tables accept ALTER TABLE on the parent. Create next year's
-- partitions before January (see the loop at the bottom, or pg_partman).
--
-- Not needed while readings arrive by CSV import; run it before a live
-- sensor feed goes in.

BEGIN;

-- 1. New partitioned table with the same columns and constraints.
CREATE TABLE lots_roomcondition_new (LIKE lots_roomcondition INCLUDING ALL)
  PARTITION BY RANGE (recorded_at);

-- The unique constraint must include the partition key; Django's
-- unique_room_condition_reading is (room_id, recorded_at, source), which does.

-- 2. Monthly partitions from the earliest reading through the end of next year.
DO $$
DECLARE
  start_month date := date_trunc('month', COALESCE((SELECT min(recorded_at) FROM lots_roomcondition), now()))::date;
  end_month   date := (date_trunc('year', now()) + interval '2 years')::date;
  m date := start_month;
BEGIN
  WHILE m < end_month LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS lots_roomcondition_%s PARTITION OF lots_roomcondition_new FOR VALUES FROM (%L) TO (%L)',
      to_char(m, 'YYYYMM'), m, (m + interval '1 month')::date
    );
    m := (m + interval '1 month')::date;
  END LOOP;
END $$;

-- Catch-all for anything outside the created ranges so inserts never fail.
CREATE TABLE lots_roomcondition_default PARTITION OF lots_roomcondition_new DEFAULT;

-- 3. Copy, swap, keep the sequence.
INSERT INTO lots_roomcondition_new SELECT * FROM lots_roomcondition;
ALTER TABLE lots_roomcondition RENAME TO lots_roomcondition_old;
ALTER TABLE lots_roomcondition_new RENAME TO lots_roomcondition;
ALTER SEQUENCE lots_roomcondition_id_seq OWNED BY lots_roomcondition.id;

-- 4. Re-point the foreign key from Django's migration table names.
-- (No other table references lots_roomcondition, so nothing to re-point.)

COMMIT;

-- 5. After verifying row counts match:
-- DROP TABLE lots_roomcondition_old;
--
-- Each January, add the next year's partitions:
-- DO $$ DECLARE m date := date_trunc('year', now() + interval '1 year')::date;
-- BEGIN FOR i IN 0..11 LOOP
--   EXECUTE format('CREATE TABLE IF NOT EXISTS lots_roomcondition_%s PARTITION OF lots_roomcondition FOR VALUES FROM (%L) TO (%L)',
--     to_char(m, 'YYYYMM'), m, (m + interval '1 month')::date);
--   m := (m + interval '1 month')::date;
-- END LOOP; END $$;
