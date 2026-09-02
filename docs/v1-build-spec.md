# Saticoy lemon storage tracker, v1 build spec

Handoff for Claude Code. 1 Sep 2026. Target: live at one Saticoy plant by mid October 2026, all three plants by early November.

> This is the governing product spec for v1, saved verbatim as received. Review notes, decisions and deviations are in [spec-review-2026-09-01.md](spec-review-2026-09-01.md).

## What we are building and why

Saticoy Lemon Association stores lemons for weeks to months across three Ventura County plants. Lots drift from green to silver to yellow in storage and some decay. Today a foreman decides by eye which lots to pack first. When a lot crosses to yellow or shows decay before it is packed, it downgrades from fresh to products, and fresh is worth roughly ten times products.

v1 tracks color and decay per lot from weekly phone photos, projects when each lot will cross to yellow, and hands the GM and foremen a ranked pack list every Monday. It also records what actually happened to each lot at pack-out, which is how we prove value and get labels for season two.

Not a sensor product. Not an ERP. Not a native app.

## Stack

Same stack as GroveMaster so we do not learn anything new mid-season. Check the GroveMaster repo first and copy its auth, settings, deploy and Supabase conventions. New repo, not an app inside GroveMaster.

| Layer | Choice |
|---|---|
| Backend | Django 5, Python 3.12, Django REST not needed in v1 (server-rendered) |
| DB | Supabase Postgres via Django ORM |
| Files | Supabase Storage bucket for photos, signed URLs |
| Frontend | Django templates + HTMX + Tailwind. Mobile first for the capture screens. Installable PWA manifest so it sits on the foreman's home screen |
| Camera | `<input type="file" accept="image/*" capture="environment">`. No custom camera UI |
| Image processing | OpenCV (cv2), numpy, Pillow. Runs in a Django management command or Celery task, not in the request |
| Jobs | Celery + Redis if GroveMaster already has it, otherwise Django management commands on a cron. Two jobs: score photos, build Monday report |
| Auth | Django auth, three groups: foreman, gm, admin |
| Email | Whatever GroveMaster uses. Report is HTML email plus a link |

## Non-goals for v1

No Famous API integration (CSV in, CSV out). No room sensors. No per-fruit spectroscopy. No multi-tenant or billing. No offline mode (see v1.1). No oranges or mandarins. No user-configurable models.

## Data model

```
Plant        id, name, code (SLA1, SLA3, SLA4), city
Room         id, plant, name, room_type (storage|degreening), target_temp_f
Grower       id, name, sunkist_grower_no
Lot          id, lot_no (Famous lot id, unique per plant), plant, grower, block,
             variety (Eureka|Lisbon|Other), receive_date, receiving_color (DG|LG|S|Y),
             bins_received, current_room (FK Room, nullable), status (in_storage|packed|dumped),
             packed_date (nullable), notes
LotRoomMove  id, lot, room, moved_at, moved_by
Sample       id, lot, sampled_at, sampled_by (User), foreman_color (DG|LG|S|Y),
             foreman_pack_within_weeks (1..8), decay_count (int), fruit_count (int, default 10),
             notes
SamplePhoto  id, sample, storage_path, uploaded_at, processed_at (nullable),
             card_detected (bool), fruit_detected (int), per_fruit_lab (json),
             per_fruit_cci (json), mean_cci (float), status (pending|scored|failed), error
Prediction   id, lot, as_of_date, cci_now, drift_per_day, predicted_yellow_date,
             pack_by_date, decay_rate, decay_flag (bool), confidence (low|med|high),
             model_version (str), inputs (json)
Packout      id, lot, packed_date, cartons_fancy, cartons_choice, cartons_standard,
             cartons_products, cartons_total, fresh_pct (computed), source_batch
ImportBatch  id, kind (receiving|packout|room_moves), file, uploaded_by, uploaded_at,
             rows_ok, rows_failed, error_report (json)
```

Indexes on Lot(plant, lot_no), Sample(lot, sampled_at), Prediction(lot, as_of_date). Never delete lots; use status.

## CSV imports

Saticoy will export from Famous. We define the templates; they map their export to ours once. Import is idempotent on (plant code, lot_no). Every import writes an ImportBatch and shows a per-row error report. Provide downloadable blank templates.

Receiving CSV: `plant_code, lot_no, grower_no, grower_name, block, variety, receive_date (YYYY-MM-DD), receiving_color (DG|LG|S|Y), bins_received, room`

Packout CSV: `plant_code, lot_no, packed_date, cartons_fancy, cartons_choice, cartons_standard, cartons_products`

Room moves CSV (optional): `plant_code, lot_no, room, moved_at`

Importing a packout row sets Lot.status to packed and Lot.packed_date.

## Foreman capture flow

Must take under 90 seconds per lot on a phone in a cold room.

1. Log in (session persists 30 days). Plant is fixed per user.
2. Lot picker: search by lot number, filtered to in_storage at this plant, sorted by weeks in storage descending. Recent lots at top.
3. Photo: 10 fruit laid on the reference board (see hardware). Take one photo. Optional second photo.
4. Three taps: foreman color (DG / LG / S / Y), pack within (1 to 8 weeks), decay count (0 to 10).
5. Submit. Show "saved, scoring" and return to the lot picker. Scoring happens in the background.

If a photo fails scoring (no card found, fewer than 6 fruit found), the lot shows a warning on the dashboard and the foreman is asked to retake next visit. Never block submission on scoring.

## Color scoring pipeline

Runs per SamplePhoto in a background job. Store everything raw so we can re-score later with a better pipeline.

1. Detect the reference board using four ArUco markers (DICT_4X4_50, ids 0 to 3) printed at the board corners. Perspective-warp to a fixed canvas. If not found, mark card_detected false and stop.
2. Color correction: the board has six grey patches and three color patches (printed green, silver-yellow, yellow) at known positions. Fit a 3x3 linear correction from measured to reference sRGB using the grey and color patches. Apply to the whole warped image.
3. Fruit segmentation: the board is matte black. Threshold in HSV on saturation and value, morphological open, connected components, keep blobs within a size range, cap at 10. Record fruit_detected.
4. Per fruit: erode the mask 15 percent to drop edges and specular highlights, convert to CIELAB (D65), take median L, a, b.
5. Citrus Color Index per fruit: `CCI = 1000 * a / (L * b)`. Mean and standard deviation across fruit. Store per_fruit_lab, per_fruit_cci, mean_cci.

Stage thresholds on mean CCI, initial values to be calibrated in weeks 1 to 3 against foreman calls: DG below -7, LG -7 to -3, S -3 to +2, Y above +2. Keep thresholds in a settings table, not in code.

## Drift and prediction

Runs nightly and after every scored sample. One Prediction row per lot per as_of_date.

1. Points: (days since receive_date, mean_cci) for every scored sample of the lot.
2. Fewer than 2 points: use a prior drift rate by receiving_color from the settings table (initial guesses: DG 0.10 CCI per day, LG 0.15, S 0.25 at 55 F storage). confidence = low.
3. Two or more points: ordinary least squares on the last 5 points. confidence = med with 2 to 3 points, high with 4 or more and R squared above 0.7.
4. predicted_yellow_date = date when the line crosses the Y threshold. pack_by_date = predicted_yellow_date minus buffer_days (settings, default 7).
5. Decay: decay_rate = sum(decay_count) / sum(fruit_count) over the last two samples. decay_flag if above 2 percent or if the latest sample is higher than the previous.
6. model_version = "v1-linear-cci". inputs json stores the points and thresholds used.

Foreman calls are never used as model inputs. They are the baseline we compare against.

## Screens

| Screen | Who | What |
|---|---|---|
| Capture | foreman | The flow above |
| Plant board | foreman, gm | All in_storage lots at the plant, ranked by pack_by_date. Columns: lot, grower, room, weeks in storage, stage, mean CCI, drift per day, pack by, decay flag, foreman call, last sampled, photo thumbnail. Filter by room. Red if pack_by is within 7 days, amber within 14 |
| Lot detail | all | CCI over time chart with the fitted line and thresholds, photos, samples, predictions history, packout if packed |
| Imports | gm, admin | Upload receiving, packout, room moves. Batch history and error reports |
| Accuracy | gm, admin | For packed lots: model pack_by vs foreman pack-within vs actual packed_date, mean absolute error in days for each. Fresh percent for lots packed on or before model pack_by vs after. Updates as packouts import |
| Settings | admin | Thresholds, prior drift rates, buffer days, report recipients |

## Monday report

Job runs Monday 05:30 Pacific per plant. HTML email to plant foreman and GM, plus the Plant board link.

Sections: lots to pack this week (pack_by within 7 days), new decay flags, lots that moved up more than 7 days since last week, lots not sampled in 10 or more days, import gaps (in_storage lots older than 120 days with no packout).

## Hardware per plant

One matte black board 24 by 18 inches with the four ArUco markers and the nine reference patches printed and laminated in the corners, mounted at a fixed sampling spot near the storage room door under a fixed LED light. One phone mount at a fixed height so framing is consistent. The board design file lives in the repo under `hardware/board.svg`; generate the ArUco markers with cv2.aruco.

## Milestones

| Week | Deliverable |
|---|---|
| 1 | Repo, Django project, models, migrations, auth groups, Supabase storage wired, seed the three plants |
| 2 | Receiving and packout import with error reports, Plant board (no predictions yet) |
| 3 | Capture flow end to end, photos landing in storage, background scoring job with card detection and CCI |
| 4 | Drift and prediction job, Lot detail chart, settings table |
| 5 | Monday report, Accuracy page, board.svg and hardware list |
| 6 | Field test at one plant with one foreman. Calibrate thresholds and priors against the first three weeks of calls |
| 7 | Fix what the foreman hated. Retake handling, lot picker speed, low-light behavior |
| 8 | Roll to all three plants. GM receives first full report |

## Acceptance

Import of a 2,000 row receiving CSV completes in under 60 seconds with a row-level error report. Capture flow completes in under 90 seconds on an iPhone in a cold room. Photo scored within 2 minutes of upload. Card detection succeeds on 95 percent of photos taken at the fixed station. Every Prediction stores model_version and inputs. Monday report arrives by 06:00 Pacific. Accuracy page shows MAE in days for model and foreman once 20 lots have packouts.

## v1.1 candidates, do not build now

Offline capture queue with a service worker. QR labels on bins for the lot picker. Room temperature CSV or sensor feed as a drift covariate. Per-lot photo of the bin face as a second sample. Famous API pull instead of CSV.

## Decisions Bird owns

Which plant goes first. Buffer days default. Who at Saticoy exports from Famous and how often. Whether the GM gets the report Monday or Sunday night.
