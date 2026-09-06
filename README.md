# Saticoy lemon storage decision support

Tracks color and quality per lemon lot, reconstructs room and treatment exposure, projects when each lot will cross to yellow, and gives the GM and foremen a ranked pack list every Monday. Each published plan is a frozen version the GM records accepted, deferred or overridden decisions against, so every recommendation can be tied to what management did and to the lot's eventual outcome. It records direct packout and shelf-life outcomes so a remaining-marketable-life model can be developed and validated without losing the current benchmark.

- Spec: [docs/v1-build-spec.md](docs/v1-build-spec.md)
- Business validation and product action plan: [docs/business-action-plan.md](docs/business-action-plan.md)
- Pre-meeting preparation and verification: [docs/premeeting-verification-2026-09-06.md](docs/premeeting-verification-2026-09-06.md)
- Review, decisions and deviations: [docs/spec-review-2026-09-01.md](docs/spec-review-2026-09-01.md)
- Field pilot and calibration gate: [docs/pilot-calibration-protocol.md](docs/pilot-calibration-protocol.md)
- Prediction V2 data and validation protocol: [docs/prediction-v2-data-protocol.md](docs/prediction-v2-data-protocol.md)
- Production deployment runbook: [docs/production-deployment.md](docs/production-deployment.md)
- Hardware per plant: [hardware/README.md](hardware/README.md), print file `hardware/board.svg`

## Run it locally

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py setup_roles
.venv\Scripts\python manage.py seed_plants
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py runserver
```

For a demo season with samples, predictions and packouts across all three plants (also creates users `foreman1`, `gm1`, and `admin1` and prints a random local-only password):

```
.venv\Scripts\python manage.py seed_demo --with-users
```

Tests:

```
.venv\Scripts\python manage.py test lots sampling forecast
```

Health checks: `/healthz/` reports process liveness and `/readyz/` verifies database readiness.

## Deploy it

The repository includes a portable production container, release/web scripts, static-file serving, health checks, CI, a tested dependency lock, and dependency updates. Production requires Postgres, private S3-compatible photo storage, SMTP and HTTPS; it refuses to fall back to local services.

```sh
docker build -t citrus-inventory:release .
docker run --rm citrus-inventory:release python manage.py check
```

Use `sh scripts/release.sh` as the host's release command and `sh scripts/web.sh` as the web command. Configure scheduled jobs from the Jobs section below. Follow [the production runbook](docs/production-deployment.md) for service provisioning, secrets, staging acceptance, backup restoration and rollback.

## Screens

| URL | Who | What |
|---|---|---|
| `/` | everyone logged in | Packing plan ranked by next action, with search, room/plant controls and attention filters; responsive cards on phones |
| `/lot/<id>/` | everyone | CCI chart, intake data, room exposure, treatments, sample quality, plan decisions, prediction history and packout outcomes |
| `/plans/` | everyone (decide: gm, admin) | Every published plan version with the decision scorecard; `/plans/<id>/` records accepted / deferred / overridden per recommendation and locks the week's schedule |
| `/capture/` | foreman, gm, admin | Prioritized daily sample route, live search and phone capture flow |
| `/imports/` | gm, admin | Upload receiving, packout, room-move, room-condition and treatment CSVs; download templates and inspect row errors |
| `/accuracy/` | gm, admin | Forecast validation plus per-lot readiness for intake, environment, representative sampling, packout and holdout labels |
| `/readiness/` | gm, admin | Current evidence coverage, station calibrations, direct outcomes, source upload age and lots awaiting evidence; coverage is distinct from accuracy |
| `/settings/` | admin | Stage thresholds, priors, buffers, plant weekly capacity and report recipients |
| `/report/<plant code>/` | gm, admin | Preview of the Monday report email |
| `/admin/` | staff | Django admin for everything else (users, plants, rooms, growers) |

## Roles and plants

`setup_roles` creates three groups: `foreman`, `gm`, `admin`. GM implies foreman, admin implies GM, superusers pass everything. A user's plant lives on `UserProfile` (admin: Plants, lots and imports, then User profiles). Foremen must have a plant and see nothing else; GM/admin with no plant see all plants and switch with a dropdown. Sessions last 30 days.

## Jobs

Three management commands, scheduled with cron or Windows Task Scheduler in `America/Los_Angeles`:

```
* * * * *    manage.py score_photos            # photos scored within ~1 minute of upload
15 2 * * *   manage.py build_predictions       # nightly rebuild for every in-storage lot
30 5 * * 1   manage.py send_monday_report      # per-plant HTML email, Monday 05:30; publishes the week's plan version
```

`publish_plan [--plant SLA1] [--date YYYY-MM-DD]` freezes the current ranked board as a new plan version without emailing; the Monday report does the same automatically and links to the version it sent.

`score_photos` also rebuilds the lot's prediction immediately after a usable photo scores. Pending photos are claimed transactionally, abandoned claims recover after 20 minutes, and transient storage reads retry up to three times. `score_photos --rescore` re-runs every stored photo by default. `send_monday_report --dry-run` prints the text version; successful plant/date deliveries are idempotent unless `--force` is supplied.

## CSV imports

Download the current templates from `/imports/`. Required headers must be present and optional measurements may be left blank. Dates use `YYYY-MM-DD` (US `M/D/YYYY` is tolerated). Timestamps accept `YYYY-MM-DD HH:MM` or ISO 8601 with an offset. Colors use `DG`, `LG`, `S`, `Y`.

- Receiving required columns: `plant_code,lot_no,grower_no,grower_name,block,variety,receive_date,receiving_color,bins_received,room`. Optional: `harvest_date,intake_cci_mean,intake_cci_std`.
- Packout required columns: `plant_code,lot_no,packed_date,cartons_fancy,cartons_choice,cartons_standard,cartons_products`. Optional: `bins_packed,is_final,packout_color,decay_pct,downgrade_reason,soft_pct,shrivel_pct,chilling_injury_pct,meets_spec`. A partial row (`is_final=no`) keeps the lot open; a final row closes it.
- Room moves: `plant_code, lot_no, room, moved_at`
- Room conditions: `plant_code,room,recorded_at,temperature_f,relative_humidity_pct,ethylene_ppm,co2_pct,source`
- Treatments: `plant_code,lot_no,applied_at,treatment_type,product,concentration,concentration_unit,duration_hours,notes`

Imports are idempotent on plant code + lot number. Bad rows are skipped and listed with their spreadsheet row number; good rows go in. Every upload is recorded as an `ImportBatch`.

Room moves accept ISO timestamps with offsets, local timestamps, or date-only values. Exact times are preserved in `occurred_at`; the legacy date stays in `moved_at`. Date-only history is labelled approximate. Receiving re-imports cannot change a known current room: import the actual room movement first. Packout files must contain complete **daily totals per lot**, not individual same-day run rows. Whole-number counts reject fractional, NaN and infinite values.

## Scoring pipeline

`sampling/scoring.py`, run by `score_photos`, never in a request:

1. Find the four ArUco markers (DICT_4X4_50, ids 0 to 3) and warp the photo to a 1200 x 900 canvas (50 px per inch).
2. Fit a 3x3 color correction in linear light from the six grey and three color patches to their reference values, apply to the whole canvas.
3. Segment fruit against the black board (HSV saturation and value), open, connected components, size-filter, cap at 10.
4. Per fruit: erode 15 percent, median CIELAB, `CCI = 1000 * a / (L * b)`.
5. Store per-fruit Lab and CCI, mean and standard deviation, correction matrix, patch diagnostics, marker IDs and blob centers on the `SamplePhoto`. Unreliable color correction is retained for audit but excluded from forecasting. Fewer than 6 fruit or no board: status `failed` with the reason; the post-capture screen asks for a same-visit retake.

Board geometry is defined once in `sampling/board.py` and shared by the detector, the print file and the synthetic test photos.

## Prediction

`forecast/model.py` is the `v1.1-linear-cci` benchmark, with one `Prediction` per lot per day. Points come only from usable, non-void **routine** samples; multiple visits on the same day are averaged into one point. Fewer than two days uses a receiving-color prior; otherwise the last five days fit a line. Four points and R² above 0.7 describe strong trend fit, not a calibrated probability of biological accuracy. Stale observations lower support. Flat/negative fits use the prior. Yellow crossing dates remain anchored to observations as time passes, including crossings in the past. Beyond-horizon estimates have no date. Pack-by remains an indicative color date minus a buffer, not a validated quality deadline.

The board, plan publication and report share an evidence gate: forecasts must use the current model, be no more than one day old, have observations on two separate routine sample days, and have a usable sample newer than the configured resampling interval. Failed latest photos require a retake. Dates that fail these checks do not contribute to due-date or capacity totals. Observed decay still requests inspection. Foremen can record **Today** or one to eight weeks; these observations never enter the color model. Holdouts remain available after final packing and do not rebuild the operational forecast or reset the routine sample route.

Register instrument-measured board/phone/light versions under **Admin → Board calibrations**. Select the matching setup during capture. Its references are copied onto each photo and used when scoring or rescoring; calibration records are immutable except for retirement. Without measured references, the nominal targets remain available for exploratory demonstrations, with an uncalibrated label. Physical calibration, independent instrument agreement and forecast validation are separate steps.

Every prediction stores its model version, settings, sample/photo provenance, per-fruit CCI distribution, and the room/treatment/intake feature snapshot that was knowable that day. These new features are deliberately not applied to pack dates until a challenger model passes held-out validation.

## Plans and management decisions

The ranked board is advisory. Publishing a plan (from the board, the Monday report, or `publish_plan`) freezes it as a numbered version per plant with the prediction, pack-by date, stage, confidence, bins and room each recommendation rested on, plus the model version and settings in force. Recommendations that ask for a pack this week, flag an overdue lot, or flag decay require a decision; the rest are monitoring and sampling actions and do not.

The GM records one of three decisions per recommendation on `/plans/<id>/`: **accepted**, **deferred** (needs a structured reason and the planned pack date), or **overridden** (needs a structured reason). Reasons are customer order, size/grade demand, capacity, changeover, disagreement with the model call, holding for color, logistics, data issue, or other with notes. Decisions are add-only: a change of mind is a new row and the previous one stays in the history. Locking the schedule stamps the plan; decisions recorded afterwards are flagged as after the lock. The plan screen also shows each lot's eventual outcome (packed date versus pack-by, or days past pack-by while still in storage).

`/plans/` shows the pilot scorecard over all versions: recommendations with a recorded decision, deferral and override reasons complete, and decisions made before the schedule lock, each against the 95 percent target in the action plan. The live board shows the current plan's decision beside each lot's priority.

## Training export

Export one leakage-safe feature row per non-void sample:

```powershell
.venv\Scripts\python.exe manage.py export_training_data --output artifacts\prediction-training.csv
```

Add `--plant SLA1` to restrict the export. Rows reconstruct features by event date; later final packout and first holdout failure are label columns. This is not yet a guarantee that every input was available when a historical prediction was made. Audit late entries, same-day timing and holdout separation, keep exports out of source control, and follow the [V2 protocol](docs/prediction-v2-data-protocol.md) before training or promoting a replacement model.

## Configuration

All configuration comes from environment variables; nothing set means the development profile with SQLite, local files and console email. `DJANGO_ENV=production` fails closed unless debug is off and explicit HTTPS, host/origin, Postgres, private storage, secret, and SMTP settings are present.

| Variable | Purpose |
|---|---|
| `DJANGO_ENV`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Standard Django. Production fails closed without explicit hosts/origins and a real secret, and enables HTTPS/HSTS/secure cookies |
| `SITE_URL` | Absolute base URL used for links in the report email |
| `SUPABASE_DB_HOST`, `SUPABASE_DB_PASSWORD` (+ `_PORT`, `_NAME`, `_USER`) | Supabase Postgres; needs `pip install psycopg[binary]` |
| `SUPABASE_S3_ENDPOINT`, `SUPABASE_S3_BUCKET`, `SUPABASE_S3_ACCESS_KEY`, `SUPABASE_S3_SECRET_KEY`, `SUPABASE_S3_REGION` | Supabase Storage through its S3 endpoint, private bucket, signed URLs; needs `pip install django-storages[s3]` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP for the Monday report |
| `PORT`, `WEB_CONCURRENCY`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `DJANGO_LOG_LEVEL` | Container web process and logging tuning |
| `DEMO_MODE` | Defaults to debug mode. Displays a demonstration notice in the app and reports; use a separate clean database for real pilot data |
| `DATABASE_SSLMODE` | Development/CI database transport setting; production always requires SSL |

## Layout

```
config/      settings, urls
lots/        Plant, Room, RoomCondition, Grower, Lot, LotRoomMove, LotTreatment, Packout, ImportBatch,
             UserProfile, ModelSettings;
             importers/, planning.py (ranked actions shared by the board and plan snapshots),
             board + lot detail + imports + settings views, seed and role commands
sampling/    Sample, SamplePhoto; board geometry, scoring pipeline, capture flow, score_photos
forecast/    Prediction, ReportDelivery, PackPlan, PlanRecommendation, PlanDecision; drift model,
             point-in-time features, training export, SVG chart, Monday report, validation view,
             versioned plans + decision record (plans.py), build_predictions, send_monday_report, publish_plan
templates/   base layout and login
static/      PWA manifest and icons
hardware/    board.svg, make_board.py, station notes
docs/        spec, review, earlier research
```

`_legacy_scaffold/` holds the pre-spec scaffold from August for reference and is gitignored.
