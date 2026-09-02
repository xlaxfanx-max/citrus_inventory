# Prediction V2 data and validation protocol

## Decision target

The production model should estimate **remaining marketable life** for each lot: the number of days from a stated prediction date until the lot no longer meets the packing house's saleable specification. It should eventually return a distribution, not a single date:

- P10: an early-failure / conservative date for protecting service levels.
- P50: the most likely failure date.
- P90: a late-failure date that communicates the uncertainty range.

Color readiness and quality failure are related but distinct outcomes. Track both. A lot can be yellow enough to pack while still marketable, or fail from decay, shrivel, softness, chilling injury or rind breakdown before color is limiting. The packing date is a management decision and must not be treated as proof that fruit failed biologically.

The existing linear CCI forecast remains the operational benchmark until a replacement beats it on held-out lots. Environment and treatment data are stored with every new prediction for audit, but they do not silently change today's pack recommendation.

## Lot intake

Import receiving before all other files. In addition to the existing required fields, capture these whenever available:

| Field | Meaning |
|---|---|
| `harvest_date` | Calendar date fruit was harvested; never infer it from receiving. |
| `intake_cci_mean` | Mean Citrus Color Index from a representative intake sample. |
| `intake_cci_std` | Standard deviation of the same fruit-level CCI observations. |

Keep the fruit-level measurements in the originating QC system if it supports them. The tracker currently imports the intake mean and standard deviation.

## Room conditions

Import raw condition readings with:

`plant_code,room,recorded_at,temperature_f,relative_humidity_pct,ethylene_ppm,co2_pct,source`

Requirements:

- Use a stable `source` name for each logger or integration. A reading is idempotent on room, timestamp and source.
- Include a UTC offset in timestamps when possible, for example `2026-09-02T14:30:00-07:00`. A local `YYYY-MM-DD HH:MM` timestamp is accepted and interpreted in the configured application timezone.
- Temperature is required. Relative humidity, ethylene and CO2 are optional, but record them where sensors exist.
- Preserve raw readings. A 15-minute cadence is preferred and hourly is acceptable for an initial deployment. Do not upload daily averages in place of raw readings.
- Position and maintain probes according to the room's monitoring plan; document calibration, replacements and outages outside the application.
- Import room moves at their actual time. The feature builder assigns each condition reading only to lots that were in that room at that point in time.

The readiness page reports observed-day coverage. Low coverage is a data-quality flag, not zero exposure.

## Treatments

Import each lot-level treatment event with:

`plant_code,lot_no,applied_at,treatment_type,product,concentration,concentration_unit,duration_hours,notes`

Supported treatment types are `ethylene`, `wax`, `fungicide`, `1_mcp`, `ga3`, `2_4_d` and `other`. Record the commercial product and units rather than assuming that equal numeric concentrations across products are comparable. Never infer a treatment from room conditions alone.

## Routine weekly sample

The greatest avoidable risk is selection bias. For every sampled lot:

1. Select ten fruit across at least five bins or field containers when the lot layout permits it.
2. Spread selection across accessible front, middle and back positions and below the visible top layer. Do not choose by color or appearance.
3. In the capture form, record **Random fruit across bins** and the actual number of bins represented. If the procedure was not followed, record **Convenience sample** rather than upgrading the sample after the fact.
4. Photograph all ten fruit on the calibrated board.
5. Record counts out of ten for decay, softness, shrivel, chilling injury and rind breakdown. Record firmness on the defined 1–5 field scale when trained staff can apply it consistently.

The model export keeps fruit-level CCI distribution summaries (P10, median, P90 and standard deviation), not only the mean. This lets a future model distinguish a uniformly changing lot from a mixed lot with an early-failing tail.

## Shelf-life holdout

A holdout supplies the biological outcome that an ordinary pack date cannot.

1. At intake, designate a documented, representative group from the lot and keep it under the same storage and treatment history as the commercial lot. Use enough fruit for the site's QC specification; ten is the application's minimum assessment unit, not a statistical claim about the whole lot.
2. Mark every assessment as **Fixed holdout group** and **Shelf-life holdout assessment**.
3. Assess on a fixed cadence, preferably at least weekly and more frequently near expected failure. Do not replace poor fruit or stop observing the group because the commercial lot packed early.
4. Record **Meets pack specification** or **Failed pack specification** against a written site specification.
5. On first failure, record the limiting reason: color, decay, shrivel, softness, chilling injury, rind breakdown or other. The first failed assessment becomes the current time-to-failure label.
6. Do not enter a failure result retrospectively from memory. If the interval is too wide, shorten the cadence for later lots.

For true out-of-storage shelf-life prediction, create a separate, controlled shelf-life phase and record its temperature and humidity. The current implementation models storage history and captures the first observed holdout failure; it does not yet represent a second environment phase.

## Packout outcome

For each partial packout, record bins and grade carton counts. On the final packout, add as many direct quality labels as the line can measure:

`packout_color,decay_pct,soft_pct,shrivel_pct,chilling_injury_pct,meets_spec,downgrade_reason`

Use measured percentages from the line or QC sample. Do not translate grade yield into a defect percentage. `fresh_pct` is useful economically, while direct defects and `meets_spec` are the quality labels.

## Leakage-safe model data

Each prediction and exported training row is an as-of snapshot. Predictors may include only facts known on that date: identity, intake, room exposure, treatments and sample measurements. Final packout and later holdout failure appear only as labels.

Export the current dataset with:

```powershell
.venv\Scripts\python.exe manage.py export_training_data --output artifacts\prediction-training.csv
```

Use `--plant SLA1` to restrict an export. Treat the CSV as sensitive operational data and do not commit it.

## Model development and promotion gate

Start with two coordinated models when label volume permits:

- A longitudinal color/readiness model using the fruit-level CCI distribution and lot history.
- A time-to-first-quality-failure survival model that can handle right-censored holdouts and competing failure reasons.

Plant, variety, grower/block, room and season should be modeled as effects or grouped features; temperature, humidity, gas exposure and treatments should be time-aware. A calibrated gradient-boosting survival model is a useful practical challenger, while a hierarchical survival model is preferable when sparse growers and rooms require partial pooling. Choose by measured validation, not model novelty.

Validation must split entire lots, and the final test should hold out a future season or time block. Never put observations from the same lot in both train and test. Report at least:

- Error and calibration at 7-, 14- and 28-day prediction horizons.
- Coverage of P10–P90 intervals.
- Early-failure recall and false-alert rate.
- Performance by plant, variety, room, season and data-coverage tier.
- Operational simulation: avoidable emergency packs, late failures, storage days and fresh yield compared with the current v1 rule and the actual plan.

Do not promote V2 until it beats the current benchmark on unseen lots, uncertainty is acceptably calibrated, and no important subgroup has a hidden safety failure. Keep an auditable model version and rollback path.

## Recommended rollout order

1. Make selection method, sampled-bin count and direct quality counts routine at one plant.
2. Connect room temperature and humidity logs; audit timestamp and room-move completeness weekly.
3. Capture treatment events and harvest date consistently.
4. Run holdouts across the expected varieties, rooms, growers and treatment regimes for at least one season segment.
5. Freeze definitions, export a versioned dataset, train challengers and backtest the inventory decisions.
6. Shadow V2 beside the current recommendation before allowing it to affect the ranked pack list.

