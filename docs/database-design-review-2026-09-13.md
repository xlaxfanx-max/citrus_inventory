# Database design review, 13 September 2026

How the schema measures against the Database Theory and Design syllabus
(conceptual model, relational model, normalization, physical design, SQL,
data platforms), what changed on this date in response, and what was
deliberately left as is.

## Conformance by course layer

| Layer | Standing | Evidence |
|---|---|---|
| Foundations | Conforms | Samples, room readings and packouts are data; predictions and the ranked plan are information. Field help text acts as the metadata repository. CSV import with per-row error reports answers "why not spreadsheets" and veracity. |
| Conceptual model | Conforms | Entities are singular types. Two associative entities (PlanRecommendation, LotRoomMove), one 1:1 (UserProfile), one subtype (routine versus holdout Sample). ERD now in [erd.md](erd.md). |
| Relational model | Conforms | Every relationship converted correctly. The one first-normal-form violation, comma-separated report recipients, is now a table. |
| Normalization | 3NF with documented snapshots | See the normal form notes in the ERD. |
| Physical design | Strong | Integer widths sized to range, NUMERIC for counts and temperatures, FLOAT only for measured statistics, composite indexes on the access paths, CHECK constraints at the database, STORED generated columns for derived carton totals. |
| SQL | Improving | No raw SQL. Per-lot bin balance now computed with SUM and COUNT in the board query. DCL added through `scripts/db_roles.sql`. |
| Data platforms | OLTP only | Prediction is fact-shaped; the analytics layer is still queried from transactional tables. |

## Changes made

1. **ERD.** [erd.md](erd.md) draws the twenty entities in crow's foot notation with cardinality, participation, delete rules and normal form notes.
2. **First normal form.** `Plant.report_recipients` (comma-separated text) became the `PlantReportRecipient` table, unique on (plant, email), validated per address. The settings page still edits one text box; the form writes rows. Migration `lots 0007` copies existing addresses.
3. **Delete rules.** Every foreign key to Lot, Plant or User is now PROTECT. Previously lot children cascaded, plans and report deliveries cascaded from Plant, and user attribution on samples, moves, imports, plans and decisions was SET NULL. Users are deactivated instead of deleted. CASCADE remains only for weak entities. The demo reset command deletes dependents in order before hard-deleting lots.
4. **CHECK constraint.** Harvest date not after receive date is now enforced by the database, not only by `clean()`.
5. **Naming.** `LotRoomMove.moved_at` (a date) is now `moved_on`; the `_at` suffix is reserved for timestamps. The CSV column keeps its name because it accepts either a date or a timestamp.
6. **Generated columns.** `Packout.cartons_total` and `fresh_pct` are STORED generated columns. They cannot disagree with the carton counts, even after a raw UPDATE.
7. **SQL aggregation.** `Lot.objects.with_bin_balance()` computes packed bins with SUM and COUNT; the board query uses it and the Python property reads the annotation when present.
8. **DCL.** `scripts/db_roles.sql` creates owner, application and read-only analyst roles, and revokes DELETE on lot and history tables from the application role.
9. **Corrected finding.** `PlanDecision.market_regime` was flagged as a transitive dependency. It is not: the plan's regime is editable after publish, so the copy is a true snapshot. The model now says so.

## Second pass, same day

10. **Per-fruit rows.** `FruitMeasurement` holds one row per fruit per scored photo (CIELAB and CCI), written by `SamplePhoto.mark_scored` and backfilled by `sampling 0008`. The JSON arrays remain the pipeline's raw record.
11. **Lot edit history.** `LotChange` records every changed field on a lot with the acting user (from `lots.audit`, set by middleware for web requests) and the path: web, import kind, packout reconciliation. Bulk import paths log explicitly.
12. **Reporting star schema.** The `warehouse` app holds `dw_dim_date`, `dw_dim_plant`, `dw_dim_lot` and three fact tables (prediction, packout, decision), rebuilt in full by `manage.py build_warehouse`. Packout lateness against the forecast in force at the time is computed once at load. Tables, not views, so operational migrations stay unaffected.
13. **Partitioning script.** `scripts/partition_room_conditions.sql` converts the room-readings table to monthly range partitions on PostgreSQL. Run by hand before a live sensor feed.
14. **Ten business queries.** `docs/course-queries.sql`, seven of which join three or more tables, each with a reading and a recommendation. Verified against the seeded demo database with `scripts/run_queries.py`.
15. **Review blockers from 10 September.** The drift model now integrates the temperature factor over recorded room history for the elapsed term and applies the current room only from today forward (model version v1.3), so a room move without a new sample leaves `cci_now` unchanged. Stale forecasts keep their date on the board, greyed with the sample age, and still count toward bins due; urgency and pack actions still require usable evidence. The release script rebuilds predictions so a model version bump cannot blank the board.

## Left as is, with reasons

- **Wide defect and carton columns** on Sample and Packout, and per-color priors on ModelSettings, are repeating groups normalizable into lookup tables. They stay wide for a fixed capture form and fast reads. Adding a defect type is a migration, which is acceptable at this scale.
- **Nine-patch calibration JSON** on BoardCalibration stays as JSON; it is validated as a unit and never queried per patch.
- **Hold budget for lots already yellow** (F2 in the 10 September review) was built on 14 September as model v1.4; see [hold-budget-model.md](hold-budget-model.md).

## Verification

Test suite: 150 tests pass on SQLite, including new tests for the CHECK constraint, PROTECT on users and lot dependents, the recipient table, form validation, generated columns after a raw UPDATE, the SQL bin balance, the exposure-integrated prior, stale-date degradation on the board, fruit measurement rows, lot change logging, and the warehouse rebuild. The generated-column DDL and the partitioning script were verified on SQLite and by inspection only; staging should run `migrate` on PostgreSQL before production.
