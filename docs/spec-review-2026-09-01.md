# Spec review and build notes — 1 Sep 2026

Review of [v1-build-spec.md](v1-build-spec.md) against the existing scaffold, plus a record of every decision made while building it into this repo. Read this before changing anything the spec is silent on.

## Verdict

The spec is sound and buildable as written: a narrow v1 with one measurement (mean CCI from phone photos), one model (a straight line), one output (a ranked pack list), and a built-in way to prove value (packout labels). The data model, screens and jobs map cleanly onto Django. All of weeks 1 to 5 of the milestone plan are implemented in this repo and covered by tests; weeks 6 to 8 are field work.

Fourteen things needed a decision or a fix. The first three would have bitten in the field.

## Issues found, ranked

1. **ArUco markers on a matte black board cannot be detected.** The detector finds a marker by the contrast between its black border and the surface around it. On a black board the border disappears. Fixed in the board design: every marker sits on a 0.3 inch white pad (`MARKER_QUIET_IN` in `sampling/board.py`, drawn into `hardware/board.svg`). The synthetic-photo tests failed with "no markers detected" until this was added, so it is not theoretical.

2. **The yellow threshold of +2 CCI is probably too high for lemons.** A fully yellow lemon has almost no red (a* near zero), so its CCI sits near zero even when it is unmistakably yellow. In the synthetic check a saturated yellow disc scored about -1 CCI, which the spec's bands call "silver". Expect calibration in weeks 1 to 3 to move the yellow boundary down toward 0 and the silver boundary toward -4. Nothing to change in code: all four boundaries live in the settings table with the spec's initial values.

3. **A row-at-a-time importer would miss the 60-second target on Supabase.** The old scaffold did four or five queries per row. Over a network round trip to Supabase that is minutes for 2,000 rows, not seconds. The receiving importer now resolves plants, growers, rooms and existing lots in a handful of set queries and writes with `bulk_create` / `bulk_update`. A test imports 2,000 rows, then re-imports them with changes, and asserts both finish under 60 seconds (about a second each on SQLite).

4. **The drift model has three undefined cases.** Resolved in `forecast/model.py` and recorded in every prediction's `inputs`:
   - Fitted slope flat or negative (fruit "greening" from noise): the line never crosses yellow. Fall back to the prior drift for the receiving color, anchored at the latest measured CCI, confidence low.
   - Zero scored samples: the spec says use the prior drift but gives no starting CCI. Added `start_cci_*` settings (assumed CCI at receipt per receiving color) so unsampled lots still rank on the board, marked "est." and confidence low.
   - Very slow drift: the yellow date is capped at `max_horizon_days` (default 365) rather than years out.

5. **Stack mismatch with GroveMaster.** The spec asks for Django 5 / Python 3.12 and to copy GroveMaster's conventions. GroveMaster is not on this machine and this repo was already scaffolded on Django 6.1 / Python 3.14 with passing tests, so it stays there. OpenCV 5.0 wheels install fine on 3.14. One Django 6 difference worth knowing: email is configured through `MAILERS`, not `EMAIL_BACKEND`. Downgrading is a settings-level change if parity matters more than the newer version.

6. **Tailwind and HTMX are not used.** The lot picker's live search uses a small local Fetch API helper, avoiding a runtime CDN dependency. Styling is a compact stylesheet in `templates/base.html`, which avoids a Node build step on a Python-only deploy.

7. **Celery and Redis not used.** Three management commands on cron do the two jobs the spec names plus the nightly rebuild: `score_photos` every minute, `build_predictions` nightly, `send_monday_report` Monday 05:30 Pacific. Cron lines are in the README.

8. **The decay flag is effectively "any decay seen".** With 10 fruit per sample, one decayed fruit is 10 percent, far above the 2 percent threshold, and "latest higher than previous" fires on 0 then 1. The UI now describes this as observed decay rather than a precise lot estimate; the pilot protocol requires a larger independent QC sample for low-percent inference.

9. **"Sorted by weeks in storage descending. Recent lots at top" is contradictory.** Implemented as: a "Sampled today" strip at the top of the picker, then every lot longest-in-storage first. Search by lot number filters the whole list.

10. **"Plant is fixed per user" needs a table the spec does not list.** Added `UserProfile(user, plant)`. A foreman is pinned to a plant and sees nothing else (other plants' lots 404). GM and admin users with no plant switch plants with a dropdown; the choice is remembered in the session.

11. **Photos must not be public.** Supabase Storage with signed URLs implies authenticated access. All photos are served through `/capture/photo/<id>/`, which checks login and plant, then streams the file locally or redirects to a one-hour signed URL on Supabase. The scoring job also writes a 320 px thumbnail so the board does not pull full phone photos.

12. **The sampling station needs network coverage.** No offline mode means a failed upload is a lost sample. Confirm wifi or cellular at each plant's station before the week 6 field test.

13. **Reference patch colors are nominal until measured.** The nine patch colors in `sampling/board.py` are print targets. Printers do not hit sRGB values exactly, so measure the finished patches with a colorimeter or spectrophotometer under a D65-compatible illuminant before calibration. A reading from the same uncalibrated phone image would be circular.

14. **No lighting spec.** Added to `hardware/README.md`: 5000 K LED with CRI 90 or better, matte lamination on the patches to kill glare, phone mount about 30 inches above the board so the 24 inch board fills the frame.

## Decisions where the spec was silent

- **Room moves from the receiving file** are dated with the lot's `receive_date`, since Famous does not say when the room changed. The room-moves CSV is the accurate source.
- **A receiving re-import never reopens a packed or dumped lot**; it only refreshes descriptive fields.
- **Packouts are unique on (lot, packed_date)**, so a lot packed over two runs has two rows and a re-upload updates in place. `Lot.packed_date` is the latest pack date seen. `fresh_pct` = fresh cartons / total cartons, computed on save.
- **Duplicate lot rows within one file** are reported as errors ("duplicate of row N") and the later row is ignored, rather than silently letting the last one win.
- **Validation page definitions.** Model/foreman versus actual pack date is labelled schedule alignment because the pack date is a management decision, not a biological ground truth. Fresh percent is aggregated over cartons. Direct `packout_color` and `decay_pct` labels are tracked separately for biological validation.
- **"Already yellow"** (CCI at or above the yellow threshold) gives `predicted_yellow_date` = today and `pack_by_date` seven days in the past, so the lot sorts to the top in red as overdue.
- **Pack-by dates in the past are kept**, not clamped to today, so the board can show "N days overdue".
- **Fruit blobs larger than 2.5 percent of the canvas are dropped** as two touching fruit. The count then comes up short and the foreman sees "retake". A close step in the morphology was removed because it merged neighbouring fruit.
- **Color correction is fitted in linear light** (sRGB de-gammaed), where a camera white-balance error really is a per-channel gain. A gamma-space fit left a 1.7 CCI residual on a test cast; the linear fit brings it under 1.0.
- **Foreman fields are add-only.** The Sample admin makes color, pack-within and decay read-only after creation, carrying over the old scaffold's locked-baseline rule.
- **Block is a text field on Lot**, as in the spec, not the old Block model.
- **Blank CSV templates are header-only**, as the spec says. Column order matches the spec exactly.

## What was dropped from the earlier scaffold

The 18 Aug scaffold predates this spec and covered a broader, single-site data diary. Superseded pieces were moved to `_legacy_scaffold/` (gitignored) rather than deleted; remove the folder when comfortable.

| Old | Now |
|---|---|
| `ColorCheck` + `ForemanPrediction` | `Sample` (foreman color, pack-within weeks, decay count) + `SamplePhoto` |
| `Lot.lot_number` unique globally | `Lot.lot_no` unique per `Plant` |
| `StorageRoom` (global) | `Room` per plant |
| File-drop inbox (`import_inbox`) with Famous / grader / room-log / treatment files | Upload screen with receiving / packout / room-moves CSVs and per-row error reports |
| `GraderReading`, `RoomLog` | Not in v1 (room data is a v1.1 candidate in the spec) |
| `LotTreatment` (wax as a covariate) | Not in v1. Wax remains the key season-two covariate flagged in earlier research; re-add as a fourth CSV when the season-two model is scoped |
| `Block` model | Text field |

## What is built, against the milestones

| Week | Deliverable | Status |
|---|---|---|
| 1 | Repo, models, migrations, auth groups, storage wired, three plants seeded | Done. `setup_roles`, `seed_plants`; Supabase Storage via env vars |
| 2 | Receiving and packout import with error reports, plant board | Done, plus room moves import and templates |
| 3 | Capture flow, photos in storage, background scoring with card detection and CCI | Done. `score_photos`; pipeline tested on synthetic board photos |
| 4 | Drift and prediction job, lot detail chart, settings table | Done. `build_predictions`; server-rendered SVG chart; `ModelSettings` + Settings screen |
| 5 | Monday report, accuracy page, board.svg and hardware list | Done. `send_monday_report`; `/accuracy/`; `hardware/board.svg` + `hardware/README.md` |
| 6–8 | Field test, calibration, rollout | Not started; needs boards printed and a plant chosen |

62 tests cover the importers (including the 2,000-row timing and plant scoping), partial/final inventory, image validation and scoring claims, synthetic photo scoring, audit provenance, voided samples, drift rules, idempotent reports, validation metrics and role-based access.

## Open items that need Bird or Saticoy

- Supabase project: database host and password, a private storage bucket and S3 access keys. Deploy target and GroveMaster's deploy conventions.
- Which code is which site (plant cities are blank), which plant goes first, buffer days, and whether the report goes Monday morning or Sunday night.
- Who exports from Famous, how often, and a sample of their real export so the column mapping can be checked against the templates.
- Boards printed and mounted; patch colors measured; network at each station confirmed.
- Real photos from the station to tune the fruit segmentation thresholds (`SAT_MIN`, `VAL_MIN` in `sampling/scoring.py`) and the stage thresholds.
