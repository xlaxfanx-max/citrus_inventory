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

## Left as is, with reasons

- **Per-fruit CCI arrays on SamplePhoto** and the nine-patch calibration JSON are repeating groups. A `FruitMeasurement` table would allow percentile work in SQL, but the scoring pipeline writes and re-reads these arrays as a unit and re-scoring replaces them wholesale. Revisit when a query needs per-fruit rows.
- **Wide defect and carton columns** on Sample and Packout, and per-color priors on ModelSettings, are repeating groups normalizable into lookup tables. They stay wide for a fixed capture form and fast reads. Adding a defect type is a migration, which is acceptable at this scale.
- **Reporting views and a star schema.** Prediction, Packout and PlanDecision are facts; Lot, Plant and date are dimensions. Views over these would make future migrations brittle on both engines (PostgreSQL blocks column type changes under a view; SQLite invalidates views on table rebuilds). Build the analytics layer as a separate reporting schema or export once the validation dataset stabilizes.
- **RoomCondition partitioning.** The one table that will reach millions of rows. Partition by month in PostgreSQL before sensor feeds go live; not needed for CSV-imported readings.
- **Audit history on Lot edits.** Samples, plans and decisions are append-only, but direct edits to a Lot are not versioned. A history table is the next governance step.

## Verification

Test suite: 140 tests pass on SQLite, including seven new tests covering the CHECK constraint, PROTECT on users and lot dependents, the recipient table, form validation, generated columns after a raw UPDATE, and the SQL bin balance against the Python property. The generated-column DDL was verified on SQLite only; the PostgreSQL expression uses CAST to double precision, ROUND to numeric and CASE, all immutable, but staging should run `migrate` before production.
