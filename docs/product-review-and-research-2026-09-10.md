# Product review and outside research — 10 September 2026

**Scope.** Review of the uncommitted pre-launch work on branch `prelaunch-items` (41 files, +1,218 / −366; items A1–A10 from the 7 September plan), a browser walk-through as GM and as foreman (Spanish) on desktop and phone, an independent code review of the diff, and three outside-research passes on ground the August and 7 September research did not cover: (1) storage physiology and postharvest treatments, (2) packinghouse inventory processes and grade standards, (3) quality-based rotation science and how to validate the forecast. Research was done 10 September 2026 by web search; every claim carries its source in `docs/research-appendix-2026-09-10.md`, and inferences are marked.

**Verdict.** The pre-launch branch closes seven of the ten 7 September items cleanly and the plumbing is sound: 133 tests pass, every new endpoint is role-gated and plant-pinned, migrations are additive, the Spanish catalogue is complete. Two things stand between it and launch. First, the new temperature prior is applied to days already spent, keyed to the lot's current room, so a room move silently rewrites a lot's colour history and can erase its pack date. Second, the product's headline number is fragile: on 10 September not one of the 28 demo lots shows a pack date, because a forecast older than a day or a sample older than ten days blanks the date outright instead of degrading it. The outside research changes the science more than the UI: the decay thresholds should follow the USDA grade ladder (1 % at shipping point, 3 % at destination) rather than a single 2 % flag; the storage-temperature band is colour-class dependent and has a cold-side boundary the app does not watch; lots already at yellow need a hold budget, not a pack-by date in the past; and the pilot evaluation must be pre-registered around forecast skill with censoring handled, because a one-to-two-month pilot cannot statistically show a 10–20 % reduction in dump rate.

---

## 1. State of the product

### Verified today

| Check | Result |
|---|---|
| Tests | 133 pass (`lots sampling forecast`, SQLite, after `collectstatic`) |
| Django checks / migrations | No issues; no missing migrations; `django.mo` matches the `.po` |
| Board, plan list, plan detail, lot detail, readiness, validation | Rendered as GM on desktop and 375 px |
| Picker, capture | Rendered as foreman in Spanish on desktop and 375 px |
| One-tap Accept | Click on lot 26-1022 wrote an `accepted` decision and updated the row and counters in place |
| Empty capture submit | Step 1 outlined red with "Tome la foto antes de guardar." and scrolled into view (B4 closed) |
| Lot detail | Overdue tile toned red with "87 days overdue" (B2), whole bins (B6), key/value metadata grid (P4) |
| Settings page | 403 for the GM (admin-only) and not linked from the GM menu |

### What the pre-launch branch got right

- Plan detail is now a one-screen Monday task: Accept per row, "Accept all remaining (n)", market-regime select, phone cards with the decision block last, fetch save with CSRF.
- Capture: 25-fruit default with a 50-fruit "muestra doble" option, decayed-fruit stepper, visible step errors, capture timer to `Sample.capture_seconds`, station select, quality and holdout sections collapsed by default.
- Foreman sessions default to Spanish through middleware; the picker and capture pages are fully translated.
- Room setpoints are in the data, the lot page shows setpoint and a rot-risk clock, and every prediction carries its model version so old and new forecasts can be told apart.

### Findings from the walk-through

**F1 — On 10 September no lot on the board has a pack date.** All 28 lots read "Indicative pack date · Not available" and the "Known bins due · 7 days" tile is 0. Two rules in `Prediction.review_blockers` suppress the date entirely: a forecast older than one day, and a latest usable sample ten or more days old. Running `build_predictions` cleared the first; the second still blanks 27 of 28 lots because the demo samples are 9–14 days old. In production a missed sampling week erases every forecast the GM plans against, and the nightly command becomes a single point of failure for the headline number. The date should degrade, not vanish: show the last usable date greyed with "from a sample 13 days ago", keep the bins-due tile counting it, and reserve "Not available" for lots with no forecast at all.

**F2 — Lots already yellow get a pack-by date in the past and no forward guidance.** Lot 26-1021 crossed CCI 2.0 around 22 June. Under model v1 (1 Sep) the record said "pack by Aug 25"; under v1.2 it says "pack by June 15", so the same lot went from 16 to 87 days overdue between plan v1 and today with no new evidence. The v1.2 behaviour is the honest one (the crossing is retained rather than moved to today), but a date months in the past tells the GM nothing about how long the fruit can still be held. The hold-budget ladder from the August research is still not implemented. For lots at or past a band, the operative number should be "days of hold budget remaining", driven by weeks since the crossing, decay trend and the storage clock, with the crossing date as context. The same 15 points also went from "Strong trend fit" (v1.1) to "Low trend support" (v1.2) because the staleness rule now forces confidence low: a labelling change, not a fit change.

**F3 — The board and the plan disagree on open decisions.** The board says "7 recommendations awaiting a decision"; the plan page says 15 (14 after the test Accept). The board counts live rows whose current action requires a decision; the plan counts frozen recommendations. Show the plan's number on the board (it is what the scorecard measures) and explain any difference ("8 recommendations changed since the plan was published").

**F4 — The rot-risk clock sits on a knife edge and prints noise.** The clock counts weeks at or above 13.0 °C. Saticoy's cold rooms are seeded at 55 °F, which is 12.8 °C, so a setpoint one degree Fahrenheit higher flips a lot from "0.0 wk" to counting its whole life. Saticoy's own published storage setting is 50–52 °F (10–11 °C), so the clock as tuned would never trip at the real plant; and the literature's boundary is a life-shortening gradient (1–2 months at 13 °C versus 4–6 at 10 °C), not a step. Today "0.0 wk warm storage" appears on all 28 rows, every phone card and the lot page, which trains the GM to ignore it. See S2 below for the science-based redesign.

**F5 — The capture screen contradicts itself on the fruit count.** Step 1 reads "Fotografíe 10 frutas / Diez limones en el tablero" (hardcoded in the template and the catalogue) while step 4 reads "Frutas podridas de 25". The board holds ten lemons and the second photo is optional, so a foreman cannot photograph 25. Say it plainly: colour from the 10 photographed fruit, decay from 25 inspected, or move to three photos. As built, the 25-fruit statistical argument applies only to the decay count, and every photo still records "10 fruit".

**F6 — Spanish stops at the foreman's own screens.** The foreman's board mixes languages ("Prioridades del inventario" beside "Lot / grower", "Deferred", "observed decay", "16 days overdue"); lot detail and plan detail have no translation tags, and the foreman can open all three.

**F7 — Smaller items.** Photo cards print "no image file" for every demo photo (show a placeholder). The samples table shows the foreman answering "Yellow · pack within 1 wk" ten weeks running on lot 26-1021 while it stayed in storage; the plan should surface "foreman has said pack-this-week for n weeks" as its own flag. Validation reports 0 of 14 packed lots labelled, and the new per-packout quality form is only a collapsed row on the lot page; link to it from Validation. Readiness shows 0 timestamped room moves and 0 temperature readings, so the temperature-band model runs on setpoints alone.

### Independent code review of the diff

Two blockers, five should-fix items and a dozen smaller ones; the full list with file and line references is in the appendix.

1. **Blocker: the temperature prior is applied retroactively, keyed to the current room.** `predict()` scales the prior by the current room setpoint and then, on the one-point and receiving-colour paths, computes `cci_now = anchor + prior × elapsed_days` with that scaled prior. Moving a 30-day-old dark-green lot from a 55 °F room into a 41 °F room drops the factor to about 0.14, re-stages the lot and pushes the crossing past the horizon, so the pack-by date disappears with no new observation. This contradicts the model's own stated invariant. Fix: integrate the rate factor over the room-exposure intervals (already computed by `room_exposure_intervals()`) for the elapsed term, and use the current room's factor only from today forward; add a test that a room move with no new sample leaves `cci_now` unchanged. Verified by hand against `forecast/model.py:85-121` and `forecast/services.py:82`.
2. **Blocker: the `MODEL_VERSION` bump blanks every board until the nightly rebuild.** Neither the Dockerfile nor `scripts/web.sh` runs `build_predictions`. Run it as a release step after `migrate`.
3. **Should-fix: `LANGUAGE_CODE` never reaches templates.** The i18n context processor is missing, so `<html lang>` is "en" on Spanish pages and both toggle buttons show unpressed. The existing test passes only because it matches a `<button lang="es">`. Verified against `config/settings.py:134-139`.
4. Publishing with market "Not set" silently inherits the previous plan's regime; the language cookie lacks Secure/HttpOnly/SameSite and outlives logout; capture has no recovery when the POST fails (button stays disabled on back-navigation); frozen evidence notes are written in the publisher's language.

---

## 2. What the outside research says

### 2.1 Storage physiology and treatments (agent 1)

- **Decay thresholds are regulatory, not folklore.** U.S. No. 1 and No. 2 lemons allow at most 1 % decay at shipping point and 3 % en route or at destination, inside 5 % serious damage and 10 % total defects; decay is serious damage "in any amount" and contact spot scores the same ([USDA lemon standard](https://www.ams.usda.gov/sites/default/files/media/Lemon_Standard%5B1%5D.pdf), [inspection instructions](https://www.ams.usda.gov/sites/default/files/media/Lemons_Inspection_Instructions%5B1%5D.pdf)). The "5 % dump" rule appears only in secondary sources; treat it as a house parameter.
- **Sour rot is the California long-storage problem.** A 2020–23 packinghouse survey was triggered by high sour rot on propiconazole-treated lemons stored for extended times; resistant *Geotrichum* strains carry no fitness cost, and senescent tissue raised sour rot from 5 % to 68 % ([Nguyen, Förster, Adaskaveg 2025](https://pubmed.ncbi.nlm.nih.gov/39441531/)). Imazalil, TBZ, pyrimethanil and fludioxonil do not control it; natamycin does, with no resistance documented ([Chen et al. 2021](https://pubmed.ncbi.nlm.nih.gov/33320038/)). Old lots rot from sour rot even with good sanitation, so decay type matters, not just decay count.
- **The temperature window has two walls.** Chilling injury (pitting, membranous stain, red blotch) appears below about 10 °C over months and below 5 °C quickly; 3–4 weeks at 3–5 °C is tolerated ([UC Davis](https://postharvest.ucdavis.edu/produce-facts-sheets/lemon), [Cargo Handbook](https://www.cargohandbook.com/Lemons)). At 13 °C, three months and longer gave high rot ([Cohen 1988](https://doi.org/10.21273/hortsci.23.2.400)). Sources disagree on the optimum (UC Davis 12–14 °C; Cargo Handbook 10–11 °C yellow / 12–14 °C green; Saticoy publishes 50–52 °F); the reconciling reading is a colour-class-dependent band, greener fruit warmer.
- **Peteca and ethylene.** Peteca (oil-gland collapse) can appear 3–5 days after harvest; yellow fruit is more susceptible than silver, 100 % RH raises it, and polyethylene waxes induced more than carnauba. Storage rooms should stay at or below 0.1 ppm ethylene ([Alhassan et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6351945/)); button senescence is the entry for *Alternaria*. One study found 3 ppm ethylene prevented peteca, a cultivar-specific result not to generalise.
- **Weight loss.** About 1.2 % per week at 8 °C and 85–90 % RH in air ([Ma et al. 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6601498/)); the "5 % = shrivel" line is a rule of thumb from engineering sources. Softening tracks water loss, which is why storage wax is applied before the hold and pack wax after.
- **Treatment timing and residues.** Treat within 24 h of harvest in warm weather; 2,4-D for button retention is prohibited in many export markets; Japan regulates postharvest fungicides as labelled food additives; Korea runs a positive list with a 0.01 ppm default. Export lots therefore carry higher sour-rot exposure in long storage because the export-friendly chemistry does not control it.
- **CA, 1-MCP, ozone** all slow colouring, the opposite of a Ventura house's goal; none is in Californian lemon use.

### 2.2 Packinghouse processes and standards (agent 2)

- **No citrus body publishes a rotation rule.** The consistent principle is quality-based: colour stage at harvest sets storability (green Eureka stores about 90 days at 10 °C, yellow about 30), and juice and acid actually rise during storage, so green fruit gains value for weeks before it loses it. How a house picks the next lot when colour, age, decay and customer spec conflict is tacit knowledge nobody has written down.
- **Saticoy's own flow** is two-pass: wash and Sunsort pre-grade, storage by size and grade at 50–52 °F and 90–95 % RH, then re-wash, pack wax, second optical grade and hand inspection, pack, pre-cool at 40–45 °F ([Saticoy](https://saticoylemon.com/operations/)). The inventory unit is therefore the pre-graded bin: size and colour known, final grade unknown until it runs.
- **Why true FEFO is hard.** Bins are stacked several high and the oldest is often at the back or bottom; blocked aisles are a documented decay cause. Bin position is a planning input, not a detail.
- **Grades encode "ready" and "no longer saleable".** The USDA standard (effective 13 May 2026 after the seedless amendment) separates colour (a 10 % tolerance), firmness, and the decay ladder; the California standard adds a 15 % aggregate. Export eligibility (Korea, China, Japan) is set by grove and packinghouse programs, not fruit quality.
- **Traceability.** Fresh citrus is not on the FSMA 204 Food Traceability List, and the compliance date for listed foods is 20 July 2028; PTI GS1-128 labels (GTIN, lot AI 10, pack date) are the retailer-driven norm.
- **Pool accounting.** Under the Sunkist packinghouse licence, growers are paid the pool's average realisation for the grade, size and period in which their fruit was packed and sold; the pack date, not the receipt date, decides which pool a bin lands in ([licence agreement](https://contracts.justia.com/companies/limoneira-co-2897/contract/1329782/)). A hold decision therefore moves grower money between pools, which is the argument for the decision record.
- **No public lemon benchmarks** exist for repack loss, dump %, days in storage or room fill; the house sets its own targets.

### 2.3 Rotation science and validation (agent 3)

- **FEFO evidence is real but not citrus.** Pilot studies on strawberries and bananas cut losses by 8–14 % of volume by scheduling on remaining shelf life ([Jedermann et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4006168/), 2021); dynamic shelf life extended usable life 13.8 % for fruit in a 2025 Monte-Carlo LCA. Per-box shelf life carried a ±5-day SD, so lot-average forecasts are the realistic ambition. Set the pitch claim at the conservative end.
- **Kiwifruit is the commercial analogue.** Zespri releases coolstore lines by the firmness of the third-softest of 90 fruit, sets ship-by weeks by storage characteristic, and pays growers for storage potential. A "ship-by week" per lot is the hold budget the app is missing.
- **What 25 fruit can and cannot say.** The lot mean is known to ±0.39 s (95 %); with a within-lot SD of 2 CCI that is ±0.8. Percentiles are a different matter: with 25 fruit the second-lowest is roughly the 8th percentile and nothing below the 4th is observable. The app's P10/P90 from 10 fruit is the minimum and maximum. Report mean ± SE or a one-sided tolerance bound (k ≈ 1.84 for 90 % coverage), and measure within-lot SD on a few 50–100-fruit samples in the first two weeks.
- **Validation protocol.** Because repeated samples within a lot are correlated, random splits inflate skill: use leave-one-lot-out and forward-chaining hindcast, report RMSE in days against a naive "all lots at the mean rate" baseline, and check calibration. Lots packed or juiced before reaching the band are right-censored; evaluating only lots that reached it is selection bias. Survival-analysis methods (Hough et al. 2003) handle this.
- **Power.** With α 0.05 and 80 % power, showing a 20 % relative reduction in a 20 % lot dump rate needs about 1,447 lots per arm; a 50 % reduction still needs 199. A continuous per-lot outcome (percent downgraded, SD 5) needs about 44 lots per arm for a 3-point drop. Interleave weeks or rooms rather than pre/post, because October-to-December colour behaviour drifts.
- **Temperature.** ±1 °C of temperature error is ±7–13 % of days depending on Q10, and temperature variability tripled prediction uncertainty relative to kinetic-parameter uncertainty; commercial rooms swing about 3 °C daily and run warmer near doors ([Badia-Melis et al. 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4435195/)). Logger data at the pallet zone beat setpoints.
- **Decision rules and people.** Act when P(event) exceeds the cost–loss ratio; uncertainty forecasts improved decisions and preserved trust after misses ([Joslyn & LeClerc 2012](https://www.apa.org/pubs/journals/features/xap-18-1-126.pdf)); 75–80 % of system forecasts get manually adjusted in practice, and people use an algorithm far more when they can modify it. The override log is pilot evidence, and an "accepted %" target would be the wrong scorecard.
- **Standards.** Store the lot key as the GS1 lot string; EPCIS 2.0 JSON for temperature events; ingest loggers as CSV and keep the raw files.

---

## 3. Ranked improvements

Effort: S = under a day, M = a few days, L = a sprint or more. Items reference the walk-through findings (F), code review (CR) and research (2.x).

### A. Before the mid-October go-live

| # | Improvement | Why now | Effort |
|---|---|---|---|
| A1 | **Fix the retroactive temperature prior** (CR-1): integrate the rate factor over room-exposure intervals for elapsed days, current room only from today forward; test that a room move without a sample leaves `cci_now` unchanged. | Lots will jump around the board on the first room move after deploy. | M |
| A2 | **Degrade, don't erase** (F1, CR-2): show the last usable date greyed with its sample age; keep bins-due counting it; add `build_predictions` to the release steps. | On any day the nightly job or the sampling route slips, the product's headline number is blank. | S |
| A3 | **Hold budget for lots at or past a band** (F2, 2.2, 2.3): "days of hold remaining" from weeks since crossing, decay trend and storage clock; crossing date as context; a ship-by week per lot. | The plan currently says "87 days overdue" for fruit the house is still selling. | M |
| A4 | **Storage clock with two walls** (F4, 2.1): degree-weeks above the colour-class band and a cold clock (days below 10 °C, any reading below 5 °C); hide when zero; readiness check "setpoint inside 10–14 °C for its colour class"; °F in the settings help. | 55 °F rooms never trip the current 13 °C clock, and chilling injury is not watched at all. | S–M |
| A5 | **Decay ladder from the USDA grade** (2.1): amber at 1 % (cannot pack No. 1 without regrade), red at 3 % (destination risk), house dump % as a parameter; decay type on the sample (green/blue mold, sour rot, button/Alternaria, brown rot) plus button loss and membranous stain counts. | Sour rot on treated long-storage lots is the documented Ventura failure mode and the app cannot see it. | M |
| A6 | **Fruit-count honesty** (F5, 2.3): legend "colour from 10 photographed, decay from 25 inspected", `Sample.fruit_count` default 25, replace P10/P90 with mean ± SE. | The screen contradicts itself and the percentiles are the min and max of ten fruit. | S |
| A7 | **i18n context processor, cookie flags, clear cookie on logout** (CR-3, CR-5). | `<html lang>` and the toggle are wrong on every Spanish page; the test hides it. | S |
| A8 | **One decision count** (F3) and **market "Not set" fix** (CR-4). | The GM reads two different numbers for the same Monday task. | S |
| A9 | **Capture POST failure recovery** (CR-6): re-enable Save on `pageshow`, keep the chosen file if the browser allows, say what to do. | Plant-floor Wi-Fi will fail a POST in week one. | S |
| A10 | **Spanish for the board and lot page** (F6), or hide GM-only columns from foremen. | Foremen open the board first. | M |

### B. During the pilot (weeks 3–10)

| # | Improvement | Why | Effort |
|---|---|---|---|
| B1 | **Temperature logger import** (CSV: logger id, timestamp, °C) and consume the trailing-temperature features the model already stores; carry ±1 °C into a forecast interval. | Room temperature variability dominates forecast error; the model runs on setpoints today. | M–L |
| B2 | **Show a date range and P(band by date)**, with the house's cost–loss threshold as a setting; keep the point date for the report. | Uncertainty forecasts improve decisions and survive misses. | M |
| B3 | **Treatment events and market tags**: a.i., ppm, temperature, method, hours since harvest; export-market tags per lot; alarms for >24 h to treatment, non-permitted a.i. for a tagged market, sour rot on propiconazole lots, >12 weeks without a sour-rot treatment. | Treatment history is a stronger covariate than wax alone, and export eligibility is a program property. | M |
| B4 | **Weight-loss reference bin and firmness spot check** for lots past 12 weeks (fields exist). | Colour is a late indicator; softening tracks water loss at ~1.2 %/week. | S |
| B5 | **Bin position / stack depth** on the lot, with a "oldest lot is buried" flag on the plan. | The physical reason FEFO fails in a lemon room. | M |
| B6 | **Pack events with pool period**, pre-grade vs final-grade delta, and the KPI set: fresh packout %, repack/downgrade %, dump %, estimated weight loss, days in storage by colour class, room fill %. | Pool accounting is why a hold decision moves grower money; no industry benchmarks exist so the house sets targets. | M |
| B7 | **GS1 lot string as the lot key**; EPCIS 2.0 export later. | Joins to PTI case labels and the Famous export. | S |

### C. Evaluation and house questions (no code)

| # | Action | When |
|---|---|---|
| C1 | **Pre-register the pilot evaluation** in `docs/pilot-calibration-protocol.md`: primary endpoint forecast skill (RMSE-days vs naive baseline, leave-one-lot-out, forward-chaining hindcast, calibration with censoring handled); secondary a continuous per-lot outcome with ≥45 lots per arm, interleaved weeks or rooms. Drop any binary dump-rate claim. | Before go-live |
| C2 | **Measure within-lot CCI SD** on three to five 50–100-fruit samples to decide whether 25 is enough for the mean and what the tolerance bound looks like. | Weeks 1–2 |
| C3 | **House questions**: which setpoint per colour class per room; storage-wax formulation and fungicide in it; sour-rot incidence on propiconazole lots last season; treatment-timing records; export program tags per grove; pool definitions and periods; can the Sunsort pre-grade export per lot. | House meeting |
| C4 | **Pitch calibration**: cite the 8–14 % FEFO range for short-life produce, claim the conservative end on a lot-average basis, and lead with "protecting fresh share in an oversupplied market". | Before the pitch |
| C5 | CDFA SCBGP 2027 concept proposal still closes **21 September 2026, 9 a.m. PT** (from the 7 September review). | This week |

---

## 4. Caveats on the research

- Several primary PDFs were blocked to automated reading (NSW DPI lemon manual, Argentine protocol, PrimusGFS Module 5, CRI Toolkit 6.4, Zespri SLA, Hertog 2014 full text); facts from them come from abstracts, snippets or secondary citations and are marked in the appendix.
- No published lot-level decay curve, rotation rule, inspection interval or shrink benchmark exists for commercial lemon storage anywhere; the alarm thresholds above are assembled from grade standards and single studies and should be house-configurable.
- The USDA lemon standard changed on 13 May 2026 (seedless amendment); tolerances quoted are from the current text.
- Sample-size and power figures were computed from standard formulas, not taken from a lemon study.
- The full agent reports, the code review and every citation are in `docs/research-appendix-2026-09-10.md`.
