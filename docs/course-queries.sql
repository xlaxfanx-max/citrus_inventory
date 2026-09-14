-- Ten business questions against the Citrus Inventory schema.
--
-- Written for the Database Theory & Design group-project format: each query
-- states the question, joins the tables it needs (queries 1, 2, 4, 5, 6, 7
-- and 9 join three or more), and closes with how to read the output and
-- what the packinghouse should do about it. Standard SQL that runs on
-- PostgreSQL 12+ and SQLite; the only dialect note is on query 6.
--
-- Table names are Django's: <app>_<model>. The dw_* tables are the reporting
-- star schema built by `manage.py build_warehouse`.
--
-- Verify locally:
--   python manage.py migrate && python manage.py seed_demo --with-users
--   python manage.py build_warehouse
--   python scripts/run_queries.py docs/course-queries.sql

-- ---------------------------------------------------------------------------
-- 1. What is on the board right now, by plant and color stage?
--    Tables: lots_lot, lots_plant, forecast_prediction (latest row per lot
--    via a window function in a CTE).
-- ---------------------------------------------------------------------------
WITH latest AS (
    SELECT p.*,
           ROW_NUMBER() OVER (PARTITION BY p.lot_id ORDER BY p.as_of_date DESC, p.id DESC) AS rn
    FROM forecast_prediction p
)
SELECT pl.code AS plant,
       COALESCE(latest.stage, 'none') AS stage,
       COUNT(*) AS lots,
       SUM(COALESCE(l.bins_received, 0)) AS bins_received,
       MIN(latest.pack_by_date) AS earliest_pack_by
FROM lots_lot l
JOIN lots_plant pl ON pl.id = l.plant_id
LEFT JOIN latest ON latest.lot_id = l.id AND latest.rn = 1
WHERE l.status = 'in_storage'
GROUP BY pl.code, COALESCE(latest.stage, 'none')
ORDER BY pl.code, stage;
-- Reading: one row per plant and stage. A large Y (yellow) count with an
-- earliest pack-by in the past is fruit the house is already late on.
-- Recommendation: staff the pack line for the plant whose yellow bins are
-- highest before taking new receipts into that plant's storage rooms.

-- ---------------------------------------------------------------------------
-- 2. Which growers' fruit shows the most decay in storage?
--    Tables: lots_grower, lots_lot, sampling_sample. HAVING keeps growers
--    with enough samples to judge.
-- ---------------------------------------------------------------------------
SELECT g.sunkist_grower_no,
       g.name AS grower,
       COUNT(s.id) AS samples,
       SUM(s.decay_count) AS decayed_fruit,
       SUM(s.fruit_count) AS inspected_fruit,
       ROUND(100.0 * SUM(s.decay_count) / SUM(s.fruit_count), 2) AS decay_pct
FROM lots_grower g
JOIN lots_lot l ON l.grower_id = g.id
JOIN sampling_sample s ON s.lot_id = l.id AND NOT s.is_void AND s.purpose = 'routine'
GROUP BY g.id, g.sunkist_grower_no, g.name
HAVING COUNT(s.id) >= 3
ORDER BY decay_pct DESC, samples DESC;
-- Reading: decay percent across all routine samples per grower, only where
-- three or more samples exist. Anything above the house flag (2 %) or the
-- USDA 3 % destination tolerance is a grower whose lots should be packed
-- earlier. Recommendation: shorten the target storage weeks for the top two
-- growers and record decay type on their samples to tell sour rot from mold.

-- ---------------------------------------------------------------------------
-- 3. Does receiving color predict fresh packout?
--    Tables: lots_lot, lots_packout. fresh_pct is a generated column.
-- ---------------------------------------------------------------------------
SELECT l.variety,
       l.receiving_color,
       COUNT(po.id) AS packout_runs,
       ROUND(AVG(po.fresh_pct), 1) AS avg_fresh_pct,
       MIN(po.fresh_pct) AS worst_fresh_pct,
       SUM(po.cartons_total) AS cartons
FROM lots_lot l
JOIN lots_packout po ON po.lot_id = l.id
GROUP BY l.variety, l.receiving_color
ORDER BY l.variety, l.receiving_color;
-- Reading: average share of cartons that went fresh (fancy, choice,
-- standard) rather than to products, split by variety and the color the
-- fruit arrived at. Recommendation: if dark-green receipts pack out worse
-- than silver, the storage program is holding green fruit too long; set a
-- separate pack-by buffer for DG lots in model settings.

-- ---------------------------------------------------------------------------
-- 4. How late against the forecast did each plant pack, month by month?
--    Tables: dw_fact_packout, dw_dim_lot, dw_dim_plant, dw_dim_date (star
--    schema; the lateness was computed once at load time).
-- ---------------------------------------------------------------------------
SELECT pl.code AS plant,
       d.year,
       d.month,
       COUNT(*) AS runs,
       ROUND(AVG(f.days_after_pack_by), 1) AS avg_days_late,
       SUM(CASE WHEN f.days_after_pack_by > 0 THEN 1 ELSE 0 END) AS late_runs,
       ROUND(AVG(f.fresh_pct), 1) AS avg_fresh_pct
FROM dw_fact_packout f
JOIN dw_dim_lot lot ON lot.lot_key = f.lot_id
JOIN dw_dim_plant pl ON pl.plant_key = lot.plant_id
JOIN dw_dim_date d ON d.date_key = f.packed_date_id
WHERE f.days_after_pack_by IS NOT NULL
GROUP BY pl.code, d.year, d.month
ORDER BY pl.code, d.year, d.month;
-- Reading: positive avg_days_late means the plant packed after the model's
-- pack-by date on average; late_runs counts how many runs were late at all.
-- Recommendation: compare avg_fresh_pct between late and on-time months. If
-- late months pack out worse, the forecast is worth acting on and the plan
-- lock should move earlier in the week.

-- ---------------------------------------------------------------------------
-- 5. What does management do with the recommendations, and why?
--    Tables: forecast_plandecision, forecast_planrecommendation,
--    forecast_packplan, lots_plant (four tables).
-- ---------------------------------------------------------------------------
SELECT pl.code AS plant,
       COALESCE(NULLIF(pp.market_regime, ''), 'not set') AS market,
       d.status,
       COALESCE(NULLIF(d.reason, ''), '-') AS reason,
       COUNT(*) AS decisions
FROM forecast_plandecision d
JOIN forecast_planrecommendation r ON r.id = d.recommendation_id
JOIN forecast_packplan pp ON pp.id = r.plan_id
JOIN lots_plant pl ON pl.id = pp.plant_id
GROUP BY pl.code, COALESCE(NULLIF(pp.market_regime, ''), 'not set'), d.status, COALESCE(NULLIF(d.reason, ''), '-')
ORDER BY pl.code, market, decisions DESC;
-- Reading: the decision record broken down by the market the GM declared
-- that week. Deferrals for "customer_order" in a tight market are healthy;
-- deferrals for "quality_disagree" in every market are a model problem.
-- Recommendation: review any reason that exceeds a third of a plant's
-- deferrals with the GM before changing model thresholds.

-- ---------------------------------------------------------------------------
-- 6. Which in-storage lots have never been sampled, or not in 10 days?
--    Tables: lots_lot, lots_plant, lots_room, sampling_sample (LEFT JOIN
--    finds the zero-activity lots the board must chase).
-- ---------------------------------------------------------------------------
SELECT pl.code AS plant,
       l.lot_no,
       COALESCE(r.name, 'no room') AS room,
       l.receive_date,
       MAX(s.sampled_at) AS last_sampled_at,
       COUNT(s.id) AS samples
FROM lots_lot l
JOIN lots_plant pl ON pl.id = l.plant_id
LEFT JOIN lots_room r ON r.id = l.current_room_id
LEFT JOIN sampling_sample s ON s.lot_id = l.id AND NOT s.is_void
WHERE l.status = 'in_storage'
GROUP BY pl.code, l.lot_no, r.name, l.receive_date
HAVING COUNT(s.id) = 0 OR MAX(s.sampled_at) < CURRENT_TIMESTAMP - INTERVAL '10 days'
ORDER BY last_sampled_at, l.receive_date;
-- Reading: every active lot with no routine sample in the last ten days
-- (the model's sample_overdue_days). Recommendation: this is the foreman's
-- morning route; lots with zero samples go first because the forecast for
-- them rests only on receiving color.
-- Dialect: SQLite has no INTERVAL; use
--   MAX(s.sampled_at) < datetime('now', '-10 days')
-- (scripts/run_queries.py rewrites this automatically on SQLite).

-- ---------------------------------------------------------------------------
-- 7. How uniform is the color inside each lot? (per-fruit rows)
--    Tables: sampling_fruitmeasurement, sampling_samplephoto,
--    sampling_sample, lots_lot (four tables).
-- ---------------------------------------------------------------------------
SELECT l.lot_no,
       DATE(s.sampled_at) AS sampled_on,
       COUNT(fm.id) AS fruit,
       ROUND(AVG(fm.cci), 2) AS mean_cci,
       ROUND(MIN(fm.cci), 2) AS greenest,
       ROUND(MAX(fm.cci), 2) AS yellowest,
       SUM(CASE WHEN fm.cci > 2.0 THEN 1 ELSE 0 END) AS fruit_past_yellow
FROM sampling_fruitmeasurement fm
JOIN sampling_samplephoto ph ON ph.id = fm.photo_id
JOIN sampling_sample s ON s.id = ph.sample_id
JOIN lots_lot l ON l.id = s.lot_id
WHERE ph.status = 'scored' AND ph.quality_ok AND fm.cci IS NOT NULL
GROUP BY l.lot_no, DATE(s.sampled_at)
HAVING COUNT(fm.id) >= 5
ORDER BY (MAX(fm.cci) - MIN(fm.cci)) DESC
LIMIT 15;
-- Reading: the spread between the greenest and yellowest fruit in one
-- photo. A lot whose mean is silver but already has several fruit past the
-- yellow threshold will grade mixed at the packline. Recommendation: pack
-- mixed lots ahead of uniform ones at the same mean, and consider a
-- pre-grade pass for lots in the top five of this list.

-- ---------------------------------------------------------------------------
-- 8. Which rooms are holding the oldest fruit, and how warm are they?
--    Tables: lots_room, lots_plant, lots_lot. Storage days use the reporting
--    dimension so no date arithmetic is needed in the query.
-- ---------------------------------------------------------------------------
SELECT pl.code AS plant,
       r.name AS room,
       r.target_temp_f,
       COUNT(l.id) AS lots,
       SUM(COALESCE(l.bins_received, 0)) AS bins,
       MAX(dl.days_in_storage) AS oldest_days,
       ROUND(AVG(dl.days_in_storage), 0) AS avg_days
FROM lots_room r
JOIN lots_plant pl ON pl.id = r.plant_id
LEFT JOIN lots_lot l ON l.current_room_id = r.id AND l.status = 'in_storage'
LEFT JOIN dw_dim_lot dl ON dl.lot_key = l.id
GROUP BY pl.code, r.name, r.target_temp_f
ORDER BY oldest_days DESC;
-- Reading: rooms sorted by the age of their oldest lot, with the setpoint
-- alongside. A room at 55 F or above with fruit past eight weeks is the
-- rot-risk clock the board flags. Recommendation: move the oldest lots in
-- warm rooms to the coolest available room, or pack them this week.

-- ---------------------------------------------------------------------------
-- 9. Who changed lot quantities, and through what path?
--    Tables: lots_lotchange, lots_lot, auth_user (three tables; LEFT JOIN
--    keeps import-driven changes that have no user).
-- ---------------------------------------------------------------------------
SELECT c.changed_at,
       l.lot_no,
       c.field,
       c.old_value,
       c.new_value,
       COALESCE(u.username, '(import or job)') AS changed_by,
       c.source
FROM lots_lotchange c
JOIN lots_lot l ON l.id = c.lot_id
LEFT JOIN auth_user u ON u.id = c.changed_by_id
WHERE c.field IN ('bins_received', 'status', 'packed_date', 'receive_date')
ORDER BY c.changed_at DESC
LIMIT 25;
-- Reading: the audit trail for the fields that drive inventory and pool
-- accounting. Recommendation: any change to receive_date or bins_received
-- after a lot has been sampled should be reviewed by the GM, since it moves
-- the lot's storage age and on-hand balance.

-- ---------------------------------------------------------------------------
-- 10. Where is the data incomplete? (a data-quality scorecard)
--     Set operation: UNION ALL of independent checks over four tables.
-- ---------------------------------------------------------------------------
SELECT 'lots without bins_received' AS issue, COUNT(*) AS n
FROM lots_lot WHERE bins_received IS NULL
UNION ALL
SELECT 'in-storage lots with no room', COUNT(*)
FROM lots_lot WHERE status = 'in_storage' AND current_room_id IS NULL
UNION ALL
SELECT 'packouts without bins_packed', COUNT(*)
FROM lots_packout WHERE bins_packed IS NULL
UNION ALL
SELECT 'voided samples', COUNT(*)
FROM sampling_sample WHERE is_void
UNION ALL
SELECT 'photos that failed scoring', COUNT(*)
FROM sampling_samplephoto WHERE status = 'failed'
UNION ALL
SELECT 'rooms without a setpoint', COUNT(*)
FROM lots_room WHERE target_temp_f IS NULL
ORDER BY n DESC;
-- Reading: each row is a gap that weakens a forecast or an inventory
-- balance. Recommendation: the two largest counts become the next import
-- fix; rooms without a setpoint are a five-minute admin task that turns on
-- the temperature-aware prior for every lot in them.
