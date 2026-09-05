# Pilot and calibration protocol

The application now records the labels needed to validate the forecast. Do not use the ranked list as an automatic packing instruction until this protocol is complete.

This is the short field-startup checklist. Use the [Prediction V2 data and validation protocol](prediction-v2-data-protocol.md) for sensor, treatment, holdout, label and model-promotion definitions.

## Before the first live sample

1. Give every physical board a permanent board ID and keep one board at one station.
2. Measure every grey and color patch with a colorimeter or spectrophotometer under D65-compatible illumination. Do not use the same phone photograph as both the measurement and its reference.
3. Confirm a fixed 5000 K, CRI 90+ light, matte patches, a clean lens, no flash, and no mixed daylight.
4. Photograph known green, silver and yellow lemons with each phone/board combination. Compare application CCI with a handheld colorimeter and retain the paired readings.
5. Confirm Wi-Fi/cellular upload and run the scoring worker while the sampler is still at the station.

## Representative lot sample

The main risk is selection bias, not image processing. For each lot, select ten fruit from at least five bins or field containers: two fruit per container, distributed across accessible front/middle/back positions and not only the visible top layer. Do not choose fruit because it looks especially green, yellow, clean or damaged.

Record the actual selection method and number of bins represented in the capture form. Also record observed decay, softness, shrivel, chilling injury and rind breakdown as counts out of ten. Treat these as “observed in the sample,” not as precise estimates of low-percent lot-level rates. A separate larger QC sample is required if management needs a statistically defensible low-percent defect estimate.

## Weekly pilot

- Start with 30–50 lots at one plant.
- Sample on the same weekday and approximately the same time.
- Retake failed or low-quality photos during the same visit using the post-capture status screen.
- Import raw room temperature/humidity readings and actual room-move timestamps; add gas measurements where sensors exist.
- Import harvest dates and every lot-level treatment event instead of reconstructing either later.
- Record every partial packout with `bins_packed` and `is_final=no`.
- On the final run, use `is_final=yes` and record direct packout color, decay, softness, shrivel, chilling injury, specification result and a structured downgrade reason where known.
- Maintain representative shelf-life holdouts past the commercial pack date and record the first assessment that fails the written specification.
- Record plant weekly capacity in Settings so the board exposes overload weeks.
- Review the Monday plan version with the GM before the schedule is locked. Record accepted, deferred or overridden on every pack and decay recommendation at `/plans/`, with the structured reason for each deferral or override, then lock the schedule. Decisions recorded after the lock are flagged.

## Validation gates

Do not change thresholds by looking at the evaluation lots and then report accuracy on those same lots. Split by lot (and preferably by grower/block): use one group for calibration and a held-out group for validation.

Minimum gates before operational use:

- At least 30 lots with two or more usable CCI samples.
- At least 20 final packouts with direct observed quality labels for a basic benchmark check. This is not enough to fit a reliable multi-variable V2 model.
- Holdout outcomes across the important plant, room, variety and treatment combinations. Increase the dataset until subgroup and interval estimates stabilize; do not promote from a universal lot-count rule alone.
- Board/phone repeatability measured from repeated photographs of the same fruit.
- Errors reviewed separately by plant, room, variety and phone/board combination.
- Predictions evaluated from fixed lead times (7, 14 and 28 days), not only from the last prediction before management packed the lot.
- Entire lots kept within one split, with a future time or season block reserved for the final test.
- A documented override process: the GM remains responsible for the schedule and records why a recommendation was overridden. The application enforces this: a deferral or override cannot be saved without a structured reason, and the `/plans/` scorecard reports decision coverage, reason completion and decided-before-lock against the 95 percent targets.

## Next model decision

Keep the linear model during the pilot. The application now records point-in-time room exposure, treatment history, fruit-level CCI distribution and quality outcomes without changing the v1 recommendation. After enough labels exist, evaluate color/readiness and remaining-marketability challengers using held-out lots. Adopt a replacement only when it improves fixed-horizon and inventory-decision validation and produces calibrated uncertainty intervals.
