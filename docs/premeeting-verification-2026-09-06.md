# Pre-meeting preparation and verification — 6 September 2026

The platform is better supported as a demonstration of lemon storage monitoring and reviewed packing priorities. Its software behavior has been strengthened and tested. Phone measurement accuracy, remaining marketable life, plant workflow fit and economic benefit still need independent observations.

This work follows the [independent evaluation](independent-evaluation-2026-09-05.md). That evaluation describes the code and evidence available before these changes; its implementation findings should be read alongside this record. No customer data, customer interviews or field measurements were added during this work.

## Changes completed

| Evaluation finding | Implemented behavior |
|---|---|
| Old observations could retain high confidence | Current-model and forecast-age checks, two distinct routine observation days, and a fresh usable sample now gate packing-date actions. The board, reports and new published plans share these checks. Trend support describes the observed fit, not a calibrated probability of correctness. |
| Already-yellow dates moved forward every day | The crossing estimate stays anchored to receipt or observations. Rebuilding without new evidence no longer resets a past crossing to today. Same-day visits contribute one averaged point; future observations are excluded. |
| Human benchmark could not say “pack today” | Capture accepts **Today**, as well as one to eight weeks. Human calls remain separate from color-model inputs. Finer daily horizons and an explicit uncertainty response remain possible future improvements. |
| Holdouts could contaminate routine forecasts | Holdout observations do not rebuild operational forecasts or refresh the sampling route. Packed lots can accept holdout assessments; routine sampling remains closed. |
| Physical calibration had no versioned record | Admin can register measured board/phone/light setups. Capture copies the setup and reference values to each photo; scoring and rescoring use that snapshot. Records can be retired, but their measurement details cannot be rewritten. Nominal references are labelled uncalibrated. |
| Room history lacked intraday precision | Imports accept actual timestamps, including return visits to the same room on one day. Existing date-only moves remain approximate. Exposure uses the available precision and does not manufacture earlier history from a current location. |
| Data quality could be obscured by successful uploads | Fractional and non-finite bin counts are rejected. Receiving updates cannot silently rewrite a known room. Updating all 2,000 lots in one receiving import is covered by a regression test and bounded database batches. |
| Preparation was difficult to assess | The new **Readiness** page shows forecast evidence, calibration records, direct outcome labels, holdout coverage, room precision and upload age, with the meaning and limits of each count. |
| Access and demonstration claims needed tightening | Foremen without a plant cannot bypass assignment through a direct capture URL. Demonstration and advisory labels are visible. Capture-time and biological-confidence claims were removed. |

Observed decay can still request inspection when color-date evidence is insufficient. A suppressed date does not mean that a lot is healthy. Capacity totals exclude dates that fail the evidence checks, but still do not incorporate customer orders or all production constraints.

## Verification actually performed

- All **108 tests** passed on local SQLite in 45.601 seconds. The suite covers imports, stock handling, access, photo processing, forecasting, plans and reports, including the new regression cases.
- After the final calibration timestamp normalization, all **14 capture-flow tests** passed again, including retirement of a calibration entered in local time.
- Django system checks found no issues; `makemigrations --check --dry-run` found no missing migrations.
- New migrations were applied to the local demonstration database. A pre-migration SQLite backup is retained at `artifacts/premeeting-before-migrations.sqlite3`.
- Static assets built successfully. The Monday report dry run completed without sending email; output is at `artifacts/premeeting-report-preview.txt`.
- Browser checks covered the desktop Readiness page and capture form, including a 390 × 844 phone viewport and the **Today** input. This is browser layout verification, not a test of an actual phone camera, plant connectivity or operator speed.
- CI now includes SQLite and PostgreSQL test jobs. **The PostgreSQL job and production container were not run in this local verification; Docker was unavailable.** Production service integration, concurrent workers and restoration of a production backup remain unverified here.

Local test output is retained in `artifacts/premeeting-tests.log`. These artifacts are local and excluded from source control. A test pass supports the specified software behavior; it does not estimate field prediction accuracy.

## Rehearse the meeting

Start the application using the README instructions. Keep `DEMO_MODE=1` for the demonstration. Rebuild predictions before rehearsal using `manage.py build_predictions`; run `manage.py score_photos` after uploading sample photographs. Do not relabel existing synthetic records as real observations.

1. **Open Readiness.** Explain which evidence is present and which remains absent. Zero calibration or direct-outcome records is an honest finding, not something to fill with invented measurements.
2. **Follow one lot.** Show receiving identity and quantity, room history, routine observations, photo provenance and color trajectory. Explain what the application records and what must come from the source inventory system.
3. **Show the exception path.** Use a lot with stale or insufficient evidence to show a sampling, retake or refresh action. Then show a lot with sufficient recent observations and its indicative color date.
4. **Show accountable decisions.** Review a newly published demonstration plan and its accept/defer/override record. Existing frozen plans retain their original history; publish a new version when demonstrating the revised logic.
5. **Close the record.** Show a partial packout, remaining bins and a final observed outcome. Explain how a retained holdout can be assessed after commercial packing, and why a packing date alone does not prove biological accuracy.

Practice imports and plan changes only on demonstration data. Preview reports before configuring external recipients. Verify the login and worker process on the machine used for the meeting.

## Evidence that can be prepared before customer access

The most useful next activity is a documented bench trial using real lemons and the intended capture setup. It can establish whether the measurement workflow is repeatable before asking a packinghouse to invest staff time.

- Assign fruit and station identifiers. Repeat photographs of the same fruit after repositioning, with more than one operator where practical. Retain raw images, failures and setup details.
- Compare photographs with independent instrument readings of the corresponding peel regions. Register actual measured references through Admin; synthetic test values and nominal print colors are not calibration measurements.
- Report repeated-measurement spread, differences from the reference instrument, failed-photo frequency and complete elapsed workflow time, including setup and retakes. Choose tolerances before reviewing results, tied to the decision the measurement is intended to support.
- Keep the bench results separate from packinghouse outcomes. Repeated photos can test measurement consistency; they cannot establish lot representativeness, future quality, reduced loss or willingness to pay.

Use the [calibration protocol](pilot-calibration-protocol.md) for field preparation. An independent postharvest or quality specialist should review the sampling design, quality definitions and acceptable errors before predictions guide live packing decisions.

## Remaining limits to settle for a pilot

**Inventory integration:** imports currently expect one aggregate packout row per lot per day. Multiple shifts or runs must be combined using an agreed source rule. Stock counts still need reconciliation with the inventory owner. A lot has one current room; splitting a physical lot across rooms or merging cohorts requires an explicit identity and quantity design.

**Biological evidence:** color thresholds and a fixed buffer are an exploratory benchmark. Direct quality labels and prospectively tracked outcomes are needed before making a remaining-life claim. Holdout fruit needs its own documented identity and handling history; the current lot-linked assessment does not model an independent holdout environment or establish equivalence to the commercial lot.

**Historical validation:** training exports reconstruct data by event date. Audit late-entered facts, same-day timing, independent human calls and holdout separation before treating an export as what was known at the time. Reserve entire lots and a later time period for evaluation, following the [V2 protocol](prediction-v2-data-protocol.md).

**Operations and value:** real-phone performance, total staff burden, source-system fit, feasible changes to packing decisions, net benefits and a buyer's budget remain to be measured. Complete the [production runbook](production-deployment.md), including PostgreSQL, private photo storage, jobs and backup restoration, before live deployment.

An accurate first-meeting statement is: **“This is a working storage-monitoring and decision-recording platform with tested software controls. We can show how it handles weak evidence. The pilot would determine whether its measurements and recommendations improve your actual operation.”**
